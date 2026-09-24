"""
In-game features: live second-screen stats and personal match history.

SAFETY - what this module does and does not do
  Reads ONLY:
    * Riot's official Live Client Data API (https://127.0.0.1:2999), which the
      game itself serves for third-party apps, and
    * the League client's end-of-game stats (after the game).
  It never reads game memory, injects into or draws over the game, or sends
  keyboard/mouse input - the things Vanguard looks for.
  It also deliberately shows nothing you couldn't see yourself in game (Tab
  scoreboard + kill feed): no enemy cooldown / ultimate / summoner spell
  timers, no jungle or enemy respawn timers, no enemy gold estimates.
"""

import json
import ssl
import time
import urllib.error
import urllib.request

LIVE_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"

_INSECURE = ssl.create_default_context()  # the game uses a self-signed cert on 127.0.0.1
_INSECURE.check_hostname = False
_INSECURE.verify_mode = ssl.CERT_NONE


def fetch_live(timeout=1.0):
    """All live game data, or None when no game is running (or the mode has no live API)."""
    try:
        with urllib.request.urlopen(LIVE_URL, context=_INSECURE, timeout=timeout) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, OSError, ValueError):
        return None


def mmss(seconds):
    seconds = int(seconds or 0)
    return f"{seconds // 60}:{seconds % 60:02d}"


# ------------------------------------------------------------------ live summary

def _key(p):
    return p.get("riotId") or p.get("summonerName") or ""


def _short(p):
    return p.get("riotIdGameName") or (p.get("summonerName") or "").split("#")[0]


def _team_of_structure(name):
    """Turret_T1_... / Barracks_T2_... -> the team that OWNED the structure."""
    if "_T1_" in name:
        return "ORDER"
    if "_T2_" in name:
        return "CHAOS"
    return None


MULTI = {2: "Double kill", 3: "Triple kill", 4: "QUADRA KILL", 5: "PENTAKILL"}


def summarize(data, champ_id=lambda p: 0):
    """Turn raw live data into what the phone page shows (Tab-scoreboard equivalent)."""
    gd = data.get("gameData") or {}
    t = gd.get("gameTime") or 0
    ap = data.get("activePlayer") or {}
    players = data.get("allPlayers") or []

    me = next((p for p in players if _key(p) and _key(p) == _key(ap)), None)
    if me is None:
        short = ap.get("riotIdGameName") or (ap.get("summonerName") or "").split("#")[0]
        me = next((p for p in players if _short(p) == short), None)
    my_team = (me or {}).get("team", "ORDER")

    def row(p):
        s = p.get("scores") or {}
        items = sorted(p.get("items") or [], key=lambda i: i.get("slot", 9))
        ally = p.get("team") == my_team
        return {
            "name": _short(p),
            "champ": p.get("championName") or "",
            "champ_id": champ_id(p),
            "level": p.get("level") or 0,
            "k": s.get("kills", 0), "d": s.get("deaths", 0), "a": s.get("assists", 0),
            "cs": s.get("creepScore", 0),
            "ward": round(s.get("wardScore", 0) or 0),
            "items": [i.get("itemID") for i in items if i.get("itemID")],
            # dead/alive only for allies - no enemy respawn info at all
            "dead": bool(p.get("isDead")) if ally else None,
            "me": p is me,
        }

    ally = [row(p) for p in players if p.get("team") == my_team]
    enemy = [row(p) for p in players if p.get("team") != my_team]
    ally_kills = sum(r["k"] for r in ally)

    mine = None
    if me is not None:
        mine = row(me)
        mins = t / 60
        mine.update({
            "cs_min": round(mine["cs"] / mins, 1) if mins >= 1 else None,
            "kp": min(100, round(100 * (mine["k"] + mine["a"]) / ally_kills)) if ally_kills else None,
            "kda": round((mine["k"] + mine["a"]) / max(mine["d"], 1), 2),
            "gold": int(ap.get("currentGold") or 0),
            "respawn": round(me.get("respawnTimer") or 0) if me.get("isDead") else 0,
        })

    events = (data.get("events") or {}).get("Events") or []
    result = next((e.get("Result") for e in events if e.get("EventName") == "GameEnd"), None)
    return {
        "time": t,
        "clock": mmss(t),
        "mode": gd.get("gameMode") or "",
        "me": mine,
        "ally": ally,
        "enemy": enemy,
        "score": [ally_kills, sum(r["k"] for r in enemy)],
        "feed": feed(events, players, my_team, me)[-8:],
        "result": result,
    }


def feed(events, players, my_team, me):
    """Kill feed / announcer events, with champion names instead of player names."""
    who = {}
    for p in players:
        for k in (p.get("summonerName"), p.get("riotId"), p.get("riotIdGameName")):
            if k:
                who[k] = (p.get("championName") or k, p.get("team"), p is me)

    def name(n):
        if n in who:
            return who[n][0] + (" (you)" if who[n][2] else "")
        if not n:
            return "?"
        if n.startswith("Turret"):
            return "A turret"
        if n.startswith("Minion"):
            return "Minions"
        if n.startswith("SRU") or n.startswith("Jade"):
            return "A monster"
        return n

    def side(n):
        return who.get(n, (None, None, False))[1]

    def team_word(team):
        return "Your team" if team == my_team else "Enemy team"

    out = []
    for e in events:
        ev, n = e.get("EventName"), None
        k = e.get("KillerName")
        kind = "ally" if side(k) == my_team else "enemy" if side(k) else "neutral"
        if ev == "ChampionKill":
            n = f"{name(k)} killed {name(e.get('VictimName'))}"
            if who.get(e.get("VictimName"), (0, 0, False))[2]:
                kind = "me-dead"
            elif who.get(k, (0, 0, False))[2] or me is not None and any(
                    who.get(a, (0, 0, False))[2] for a in e.get("Assisters") or []):
                kind = "me"
        elif ev == "Multikill":
            n = f"{name(k)}: {MULTI.get(e.get('KillStreak'), 'Multikill')}!"
        elif ev == "FirstBlood":
            n = f"First blood: {name(e.get('Recipient'))}"
            kind = "ally" if side(e.get("Recipient")) == my_team else "enemy"
        elif ev == "Ace":
            n = f"ACE by {team_word(e.get('AcingTeam'))}"
            kind = "ally" if e.get("AcingTeam") == my_team else "enemy"
        elif ev in ("DragonKill", "HeraldKill", "BaronKill"):
            what = {"DragonKill": f"{e.get('DragonType') or ''} dragon".strip(),
                    "HeraldKill": "Rift Herald", "BaronKill": "Baron"}[ev]
            stolen = " (STOLEN)" if str(e.get("Stolen")).lower() == "true" else ""
            n = f"{team_word(side(k)) if side(k) else name(k)} took {what}{stolen}"
        elif ev in ("TurretKilled", "InhibKilled"):
            owner = _team_of_structure(e.get("TurretKilled") or e.get("InhibKilled") or "")
            thing = "turret" if ev == "TurretKilled" else "inhibitor"
            if owner:
                n = f"{'Enemy' if owner == my_team else 'Your team'} destroyed a {thing}"
                kind = "enemy" if owner == my_team else "ally"
        elif ev == "GameStart":
            n, kind = "Game started", "neutral"
        elif ev == "MinionsSpawning":
            n, kind = "Minions spawned", "neutral"
        elif ev == "GameEnd":
            n, kind = ("VICTORY" if e.get("Result") == "Win" else "DEFEAT"), "neutral"
        if n:
            out.append({"t": mmss(e.get("EventTime")), "text": n, "kind": kind})
    return out


# ------------------------------------------------------------------ match history

def record_from_eog(eog, champ_name):
    """End-of-game stats block from the League client -> match record (or None)."""
    lp = eog.get("localPlayer") or {}
    s = lp.get("stats") or {}
    if not eog.get("gameId") or not lp:
        return None
    teams = eog.get("teams") or []
    mine = next((t for t in teams if t.get("isPlayerTeam")), None)
    if "WIN" in s or "LOSE" in s:
        win = bool(s.get("WIN"))
    else:
        win = bool(mine and mine.get("isWinningTeam"))
    team_kills = sum((p.get("stats") or {}).get("CHAMPIONS_KILLED", 0) for p in (mine or {}).get("players") or [])
    k, d, a = s.get("CHAMPIONS_KILLED", 0), s.get("NUM_DEATHS", 0), s.get("ASSISTS", 0)
    cs = s.get("MINIONS_KILLED", 0) + s.get("NEUTRAL_MINIONS_KILLED", 0)
    secs = eog.get("gameLength") or 0
    cid = lp.get("championId") or 0
    return _record(eog["gameId"], eog.get("gameMode") or "", champ_name(cid) or lp.get("championName") or "?",
                   cid, win, k, d, a, cs, secs, team_kills,
                   damage=s.get("TOTAL_DAMAGE_DEALT_TO_CHAMPIONS"), vision=s.get("VISION_SCORE"),
                   gold=s.get("GOLD_EARNED"), source="eog")


def record_from_live(game_id, summary, win=None):
    """Fallback when the client has no end-of-game stats: last live snapshot."""
    me = (summary or {}).get("me")
    if not me or not game_id:
        return None
    if win is None:
        win = summary.get("result") == "Win" if summary.get("result") else None
    return _record(game_id, summary.get("mode", ""), me["champ"], me.get("champ_id") or 0, win,
                   me["k"], me["d"], me["a"], me["cs"], summary.get("time") or 0,
                   summary["score"][0], vision=me.get("ward"), source="live")


def _record(game_id, mode, champ, champ_id, win, k, d, a, cs, secs, team_kills, damage=None,
            vision=None, gold=None, source=""):
    mins = secs / 60
    return {
        "id": str(game_id), "date": time.strftime("%Y-%m-%d %H:%M"), "mode": mode,
        "champ": champ, "champ_id": champ_id, "win": win,
        "k": k, "d": d, "a": a, "kda": round((k + a) / max(d, 1), 2),
        "cs": cs, "cs_min": round(cs / mins, 1) if mins >= 1 else 0, "minutes": round(mins, 1),
        "kp": min(100, round(100 * (k + a) / team_kills)) if team_kills else None,
        "damage": damage, "vision": vision, "gold": gold, "source": source,
    }


def records_from_history(resp, champ_name, team_kills=None):
    """The client's official match history -> records, oldest first.
    team_kills: optional {game_id: kills of my team} for kill participation."""
    games = ((resp or {}).get("games") or {}).get("games") or []
    out = []
    for g in games:
        parts = g.get("participants") or []
        secs = g.get("gameDuration") or 0
        if not parts or secs < 300:  # remakes
            continue
        p = parts[0]
        s = p.get("stats") or {}
        cid = p.get("championId") or 0
        gid = str(g.get("gameId"))
        rec = _record(gid, g.get("gameMode") or "", champ_name(cid) or "?", cid,
                      bool(s["win"]) if "win" in s else None,
                      s.get("kills", 0), s.get("deaths", 0), s.get("assists", 0),
                      s.get("totalMinionsKilled", 0) + s.get("neutralMinionsKilled", 0), secs,
                      (team_kills or {}).get(gid), damage=s.get("totalDamageDealtToChampions"),
                      vision=s.get("visionScore"), gold=s.get("goldEarned"), source="history")
        created = (g.get("gameCreation") or 0) / 1000
        rec["created"] = created
        rec["date"] = time.strftime("%Y-%m-%d %H:%M", time.localtime(created))
        rec["queue"] = g.get("queueId")
        out.append(rec)
    out.sort(key=lambda r: r["created"])
    return out


class HistoryCache:
    """The client only keeps your last 100 games. Keep every game seen so older
    ones aren't lost as new games push them out (history_cache.json, git-ignored)."""

    def __init__(self, path):
        self.path = path

    def load(self):
        try:
            with open(self.path, encoding="utf-8") as f:
                return {r["id"]: r for r in json.load(f)}
        except (OSError, ValueError, KeyError, TypeError):
            return {}

    def merge(self, records):
        """Add/refresh records; returns all known games, oldest first."""
        games = self.load()
        before = len(games)
        for r in records:
            old = games.get(r["id"])
            if old and r.get("kp") is None and old.get("kp") is not None:
                r = {**r, "kp": old["kp"]}  # keep kill participation once known
            games[r["id"]] = r
        out = sorted(games.values(), key=lambda r: r.get("created", 0))
        if len(games) != before or records:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(out, f)
        return out


def team_kills_from_game(game, participant_id):
    """Full game from /lol-match-history/v1/games/{id} -> kills of that player's team."""
    parts = (game or {}).get("participants") or []
    me = next((p for p in parts if p.get("participantId") == participant_id), None)
    if not me:
        return None
    return sum((p.get("stats") or {}).get("kills", 0) for p in parts if p.get("teamId") == me.get("teamId"))


def personal_bests(rec, games):
    """'New Pantheon best CS/min: 8.1 (was 7.6)' messages vs earlier games on the same champion."""
    same = [g for g in games if g["champ"] == rec["champ"] and g["id"] != rec["id"]]
    notes = []
    if len(same) >= 3:  # only brag once there's something to beat
        for key, label in (("cs_min", "CS/min"), ("kda", "KDA"), ("k", "kills"), ("kp", "kill participation")):
            best = max((g.get(key) or 0) for g in same)
            if (rec.get(key) or 0) > best:
                notes.append(f"New {rec['champ']} best {label}: {rec[key]} (was {best})")
    return notes


def compute_stats(games, favorites=()):
    """Aggregate records (oldest first) for the Stats page."""
    decided = [g for g in games if g.get("win") is not None]
    wins = sum(1 for g in decided if g["win"])

    streak, kind = 0, None
    for g in reversed(decided):
        if kind is None:
            kind = g["win"]
        if g["win"] != kind:
            break
        streak += 1

    today = time.strftime("%Y-%m-%d")
    todays = [g for g in decided if g["date"].startswith(today)]

    champs = {}
    for g in games:
        c = champs.setdefault(g["champ"], {"champ": g["champ"], "champ_id": g.get("champ_id") or 0,
                                           "games": 0, "wins": 0, "k": 0, "d": 0, "a": 0,
                                           "cs_min": [], "kp": [], "best": None})
        c["games"] += 1
        c["wins"] += 1 if g.get("win") else 0
        c["k"] += g["k"]; c["d"] += g["d"]; c["a"] += g["a"]
        c["cs_min"].append(g.get("cs_min") or 0)
        if g.get("kp") is not None:
            c["kp"].append(g["kp"])
        if c["best"] is None or g["kda"] > c["best"]["kda"]:
            c["best"] = {"kda": g["kda"], "score": f"{g['k']}/{g['d']}/{g['a']}", "date": g["date"]}

    fav_order = {n.lower(): i for i, n in enumerate(favorites)}
    rows = []
    for c in champs.values():
        rows.append({
            "champ": c["champ"], "champ_id": c["champ_id"], "games": c["games"], "wins": c["wins"],
            "wr": round(100 * c["wins"] / c["games"]),
            "kda": round((c["k"] + c["a"]) / max(c["d"], 1), 2),
            "avg": f"{c['k'] / c['games']:.1f}/{c['d'] / c['games']:.1f}/{c['a'] / c['games']:.1f}",
            "cs_min": round(sum(c["cs_min"]) / len(c["cs_min"]), 1),
            "kp": round(sum(c["kp"]) / len(c["kp"])) if c["kp"] else None,
            "best": c["best"],
            "fav": c["champ"].lower() in fav_order,
        })
    rows.sort(key=lambda r: (fav_order.get(r["champ"].lower(), 999), -r["games"]))

    return {
        "games": len(games),
        "wins": wins,
        "losses": len(decided) - wins,
        "wr": round(100 * wins / len(decided)) if decided else None,
        "streak": {"count": streak, "win": kind} if streak else None,
        "today": {"wins": sum(1 for g in todays if g["win"]), "losses": sum(1 for g in todays if not g["win"])},
        "champions": rows,
        "recent": list(reversed(games[-15:])),
        "trend": [g.get("cs_min") or 0 for g in games[-20:]],
    }
