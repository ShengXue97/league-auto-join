"""In-game features with simulated live data (no game needed).

Run: python tests/test_ingame.py
"""
import copy
import json
import os
import sys
import tempfile
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ingame
import league_remote as lr

failed = False


def check(cond, msg):
    global failed
    print(("PASS " if cond else "FAIL ") + msg)
    failed |= not cond


def player(name, champ, team, k=0, d=0, a=0, cs=0, dead=False, respawn=0.0, items=(), alias=None):
    return {
        "championName": champ, "rawChampionName": f"game_character_displayname_{alias or champ}",
        "riotId": f"{name}#EUW", "riotIdGameName": name, "summonerName": f"{name}#EUW",
        "team": team, "level": 9, "isDead": dead, "respawnTimer": respawn,
        "scores": {"kills": k, "deaths": d, "assists": a, "creepScore": cs, "wardScore": 11.6},
        "summonerSpells": {"summonerSpellOne": {"displayName": "Flash"}},
        "items": [{"itemID": i, "slot": s} for s, i in enumerate(items)],
    }


def live_data(t=900.0, end=None):
    ev = [
        {"EventID": 0, "EventName": "GameStart", "EventTime": 0.0},
        {"EventID": 1, "EventName": "FirstBlood", "EventTime": 190.0, "Recipient": "Me"},
        {"EventID": 2, "EventName": "ChampionKill", "EventTime": 190.0, "KillerName": "Me",
         "VictimName": "Foe1", "Assisters": []},
        {"EventID": 3, "EventName": "ChampionKill", "EventTime": 300.0, "KillerName": "Foe2",
         "VictimName": "Me", "Assisters": ["Foe1"]},
        {"EventID": 4, "EventName": "Multikill", "EventTime": 400.0, "KillerName": "Ally1", "KillStreak": 2},
        {"EventID": 5, "EventName": "DragonKill", "EventTime": 500.0, "KillerName": "Ally1",
         "DragonType": "Fire", "Stolen": "False"},
        {"EventID": 6, "EventName": "TurretKilled", "EventTime": 600.0, "KillerName": "Minion_T100",
         "TurretKilled": "Turret_T2_R_03_A"},
        {"EventID": 7, "EventName": "TurretKilled", "EventTime": 650.0, "KillerName": "Foe2",
         "TurretKilled": "Turret_T1_L_03_A"},
        {"EventID": 8, "EventName": "BaronKill", "EventTime": 800.0, "KillerName": "Foe1", "Stolen": "True"},
    ]
    if end:
        ev.append({"EventID": 9, "EventName": "GameEnd", "EventTime": t, "Result": end})
    return {
        "activePlayer": {"riotId": "Me#EUW", "riotIdGameName": "Me", "currentGold": 1234.7,
                         "summonerName": "Me#EUW"},
        "allPlayers": [
            player("Me", "Pantheon", "ORDER", 5, 2, 7, 105, items=(1001, 3068), alias="Jade_Pantheon"),
            player("Ally1", "Ahri", "ORDER", 6, 1, 3, 140, dead=True, respawn=12.4),
            player("Foe1", "Annie", "CHAOS", 2, 4, 1, 90, dead=True, respawn=20.0),
            player("Foe2", "Ezreal", "CHAOS", 3, 3, 2, 120),
        ],
        "events": {"Events": ev},
        "gameData": {"gameMode": "JADE", "gameTime": t},
    }


# ------------------------------------------------------------ summarize
aliases = {"jade_pantheon": 60080}
cid = lambda p: aliases.get(p["rawChampionName"].split("displayname_")[-1].lower(), 0)
s = ingame.summarize(live_data(), cid)
me = s["me"]
check(me["champ"] == "Pantheon" and me["champ_id"] == 60080, "finds me and my Classic champion id")
check((me["k"], me["d"], me["a"], me["cs"]) == (5, 2, 7, 105), "my scores")
check(me["cs_min"] == 7.0, f"CS/min 105 cs / 15 min = 7.0 (got {me['cs_min']})")
check(me["kp"] == 100 and me["kda"] == 6.0, "kill participation (capped at 100%) and KDA")
check(me["gold"] == 1234 and me["items"] == [1001, 3068], "my gold and items")
check(s["score"] == [11, 5] and s["clock"] == "15:00", "team score and clock")
check([r["champ"] for r in s["ally"]] == ["Pantheon", "Ahri"] and len(s["enemy"]) == 2, "teams split")
check(s["ally"][1]["dead"] is True, "ally death shown")

# safety: nothing beyond what the Tab scoreboard shows
blob = json.dumps(s)
check(all(r["dead"] is None for r in s["enemy"]), "SAFETY: no enemy dead/alive state")
check("respawn" not in json.dumps(s["enemy"]) and "20.0" not in json.dumps(s["enemy"]), "SAFETY: no enemy respawn timers")
check("Flash" not in blob and "summonerSpell" not in blob, "SAFETY: no summoner spell info")
check("gold" not in json.dumps(s["enemy"]) and "gold" not in json.dumps(s["ally"][1]), "SAFETY: no gold for other players")

texts = [f["text"] for f in s["feed"]]
check("Pantheon (you) killed Annie" in texts, "kill feed uses champion names")
check(any(f["text"] == "Ezreal killed Pantheon (you)" and f["kind"] == "me-dead" for f in s["feed"]), "my death marked")
check("Ahri: Double kill!" in texts and "Your team took Fire dragon" in texts, "multikill and dragon")
check("Your team destroyed a turret" in texts and "Enemy destroyed a turret" in texts, "turret owner logic")
check("Enemy team took Baron (STOLEN)" in texts, "stolen baron")
check(len(s["feed"]) == 8, "feed limited to last 8")
check(ingame.summarize(live_data(end="Win"))["result"] == "Win", "game result from GameEnd")
early = ingame.summarize(live_data(t=30))
check(early["me"]["cs_min"] is None, "no CS/min in the first minute")

# ------------------------------------------------------------ official match history
def hist_game(gid, champ, win, k=5, d=2, a=5, cs=150, secs=1500, created=1_700_000_000_000, queue=4310, pid=1):
    return {"gameId": gid, "gameMode": "JADE", "queueId": queue, "gameDuration": secs, "gameCreation": created,
            "participants": [{"participantId": pid, "championId": champ,
                              "stats": {"win": win, "kills": k, "deaths": d, "assists": a,
                                        "totalMinionsKilled": cs - 10, "neutralMinionsKilled": 10}}]}


names = {60080: "Pantheon", 60103: "Ahri"}.get
resp = {"games": {"games": [  # newest first, like the client
    hist_game(4, 60103, False, created=1_700_000_400_000),
    hist_game(3, 60080, True, k=12, cs=250, created=1_700_000_300_000),
    hist_game(99, 60080, False, secs=200, created=1_700_000_250_000),  # remake
    hist_game(2, 60080, False, created=1_700_000_200_000),
    hist_game(1, 60080, True, created=1_700_000_100_000),
    hist_game(0, 60080, True, created=1_700_000_000_000),
]}}
recs = ingame.records_from_history(resp, names, {"3": 20})
check([r["id"] for r in recs] == ["0", "1", "2", "3", "4"], "history oldest first, remake skipped")
check(recs[3]["kp"] == 85 and recs[0]["kp"] is None, "kill participation from team kills when known")
check(recs[3]["cs_min"] == 10.0 and recs[3]["queue"] == 4310, "history record fields")
notes = ingame.personal_bests(recs[3], recs)
check(any("best CS/min" in n for n in notes) and any("best kills" in n for n in notes), f"personal bests: {notes}")
check(ingame.personal_bests(recs[4], recs) == [], "no bests without 3 earlier games on that champion")
st = ingame.compute_stats(recs, ["Pantheon"])
check(st["games"] == 5 and st["wins"] == 3 and st["wr"] == 60, "overall win rate")
check(st["streak"] == {"count": 1, "win": False}, "current streak")
pan = st["champions"][0]
check(pan["champ"] == "Pantheon" and pan["fav"] and pan["games"] == 4 and pan["wr"] == 75, "per-champion, favorite first")
check(st["recent"][0]["champ"] == "Ahri" and len(st["trend"]) == 5, "recent newest first, trend")
check(ingame.compute_stats([])["wr"] is None, "empty history")
team = {"participants": [{"participantId": 1, "teamId": 100, "stats": {"kills": 5}},
                         {"participantId": 2, "teamId": 100, "stats": {"kills": 7}},
                         {"participantId": 6, "teamId": 200, "stats": {"kills": 9}}]}
check(ingame.team_kills_from_game(team, 1) == 12, "team kills from full game")

# history cache: games the client drops (100-game limit) are kept
hc = ingame.HistoryCache(os.path.join(tempfile.mkdtemp(), "h.json"))
all5 = hc.merge(recs)
later = ingame.records_from_history({"games": {"games": [hist_game(5, 60080, True, created=1_700_000_600_000),
                                                         hist_game(4, 60103, False, created=1_700_000_400_000)]}}, names)
merged = hc.merge(later)
check([r["id"] for r in merged] == ["0", "1", "2", "3", "4", "5"], "cache keeps games the client no longer returns")
check(next(r for r in hc.merge(ingame.records_from_history(resp, names)) if r["id"] == "3")["kp"] == 85,
      "cache keeps kill participation once known")

eog = {"gameId": 555, "gameLength": 1800, "gameMode": "JADE",
       "localPlayer": {"championId": 60080, "stats": {"CHAMPIONS_KILLED": 8, "NUM_DEATHS": 2, "ASSISTS": 10,
                                                      "MINIONS_KILLED": 180, "NEUTRAL_MINIONS_KILLED": 30,
                                                      "WIN": 1, "VISION_SCORE": 22}},
       "teams": [{"isPlayerTeam": True, "isWinningTeam": True,
                  "players": [{"stats": {"CHAMPIONS_KILLED": 8}}, {"stats": {"CHAMPIONS_KILLED": 16}}]}]}
r = ingame.record_from_eog(eog, lambda c: {60080: "Pantheon"}.get(c))
check(r["win"] and r["champ"] == "Pantheon" and r["cs"] == 210 and r["cs_min"] == 7.0 and r["kp"] == 75,
      "end-of-game stats parsed")
check(ingame.record_from_eog({}, lambda c: None) is None, "empty end-of-game block ignored")

# ------------------------------------------------------------ watcher integration
lr.capture = lambda *a, **k: None
lr.save_config = lambda c: None
_tmp = tempfile.mkdtemp()
lr.RANK_PATH, lr.HISTORY_CACHE_PATH = os.path.join(_tmp, "rank.jsonl"), os.path.join(_tmp, "history.json")


class FakeLCU:
    def __init__(self):
        self.phase = "InProgress"
        self.eog = None
        self.calls = []
        self.history = copy.deepcopy(resp)
        self.ranked = {"tier": "PLATINUM", "division": "I", "leaguePoints": 22, "wins": 60, "losses": 54,
                       "highestTier": "PLATINUM", "highestDivision": "I"}

    def request(self, method, path, body=None, timeout=3):
        if method != "GET":
            self.calls.append((method, path))
        if path == "/lol-gameflow/v1/gameflow-phase":
            return self.phase
        if path == "/lol-gameflow/v1/session":
            return {"gameData": {"gameId": 555, "playerChampionSelections": [{"championId": 60080}]}}
        if path == "/lol-game-data/assets/v1/champion-summary.json":
            return [{"id": 80, "name": "Pantheon", "alias": "Pantheon"},
                    {"id": 60080, "name": "Pantheon", "alias": "Jade_Pantheon"},
                    {"id": 60103, "name": "Ahri", "alias": "Jade_Ahri"}]
        if path == "/lol-game-data/assets/v1/items.json":
            return [{"id": 1001, "iconPath": "/lol-game-data/assets/ASSETS/Items/Icons2D/1001.png"}]
        if path == "/lol-end-of-game/v1/eog-stats-block":
            return self.eog
        if path.startswith("/lol-match-history/v1/products/lol/current-summoner/matches"):
            return self.history
        if path.startswith("/lol-match-history/v1/games/"):
            return team
        if path == "/lol-ranked/v1/current-ranked-stats":
            return {"queueMap": {"JADE_RANKED_SOLO_5x5": dict(self.ranked)}}
        if path == "/lol-summoner/v1/current-summoner":
            return {"puuid": "me"}
        if path.startswith("/lol-ranked/v1/league-ladders/"):
            return [{"queueType": "JADE_RANKED_SOLO_5x5", "divisions": [
                {"standings": [{"puuid": f"p{i}"} for i in range(4)] + [{"puuid": "me", "position": 5}]
                 + [{"puuid": f"q{i}"} for i in range(12)]}]}]
        return None

    def raw(self, path):
        return b"\x89PNG " + path.encode(), "image/png"


def make():
    cfg = {"auto_accept": False, "favorite_picks": ["Pantheon"], "favorite_bans": [], "notify_game": True,
           "notify_champ_select": True, "notify_requeue": True, "notify_your_turn": True, "cs_goal": 7.0}
    sent = []
    lcu = FakeLCU()
    n = lr.Notifier(cfg, "http://pc:5000")
    n.send = lambda title, message, **kw: sent.append((title, message, kw.get("actions") or []))
    w = lr.Watcher(cfg, lcu, n)
    w.rank = __import__("rank").RankTracker(os.path.join(tempfile.mkdtemp(), "r.jsonl"))
    w.history_cache = ingame.HistoryCache(os.path.join(tempfile.mkdtemp(), "h.json"))
    return cfg, lcu, w, sent


LIVE = {"data": live_data()}
ingame.fetch_live = lambda timeout=1.0: copy.deepcopy(LIVE["data"])

cfg, lcu, w, sent = make()
w.refresh_history_and_rank()  # startup: history + rank before the game
check(w.snapshot()["rank_line"].startswith("Platinum I 22 SP"), "status shows current rank")
check(w.ladder == {"position": 5, "size": 17}, "league standing #5 of 17")
w.tick()
st = w.snapshot()
check(st["game"]["me"]["champ_id"] == 60080, "live champion resolved to Classic Pantheon via alias")
check(st["live_ok"] and st["cs_goal"] == 7.0, "status has live data and CS goal")
check([t for t, *_ in sent] == ["GAME LOADED"], "game loaded alert")
w._live_at = 0
w.tick()
check(len(sent) == 1, "game loaded alert only once")

# game over: result waits for the SP change, then one combined alert
lcu.phase, lcu.eog = "EndOfGame", eog
w.tick()
check(len(sent) == 1 and w.pending_result, "result held until SP change arrives")
check(w.snapshot()["game"] is not None, "final scoreboard still visible after the game")
lcu.ranked.update(leaguePoints=43, wins=61)
lcu.history["games"]["games"].insert(0, hist_game(555, 60080, True, k=8, d=2, a=10, cs=210, secs=1800,
                                                  created=1_700_000_500_000))
w.refresh_history_and_rank()
res = [x for x in sent if "VICTORY" in x[0]]
check(len(res) == 1 and res[0][0] == "VICTORY +21 SP", f"combined alert title: {[x[0] for x in sent]}")
check("Now Platinum I 43 SP" in res[0][1] and "Pantheon 8/2/10" in res[0][1], "alert has new rank and score")
check(res[0][2][0]["url"].endswith("/#stats"), "alert links to rank page")
changes = w.rank.changes()
check(len(changes) == 1 and changes[0]["delta"] == 21 and changes[0]["game_id"] == "555", "SP change recorded for the game")
payload = w.stats_payload()
check(payload["recent"][0]["id"] == "555" and payload["recent"][0]["sp"] == 21, "recent game shows +21 SP")
check(payload["rank"]["rank"]["text"] == "Platinum I 43 SP", "rank in stats payload")
check("presets" not in payload["rank"] and payload["rank"]["sp"]["win"] == 21 and payload["rank"]["sp"]["loss"] is None,
      "one tracked win: real +21 shown, no forecast until a loss is tracked")
check("games to" not in res[0][1], "alert makes no forecast without real SP data")
w.refresh_history_and_rank()
check(len(w.rank.changes()) == 1 and len([x for x in sent if "VICTORY" in x[0]]) == 1, "no duplicate on re-refresh")
lcu.phase = "Lobby"
w.tick()
check(len([x for x in sent if "VICTORY" in x[0]]) == 1, "no fallback duplicate after leaving the game")

# Aegis-role win: alert names the role and bonus
w.send_result(None, {"delta": 40, "win": True, "games": 1, "pref": 5, "role": "UTILITY", "after": {"pos": 1983}})
check("Aegis of Valor role (Support, your #5): up to +100%" in sent[-1][1] and sent[-1][0] == "VICTORY +40 SP",
      f"Aegis alert line: {sent[-1][:2]}")

# no SP change (e.g. not a ranked game) -> result sent after a timeout, without SP
cfg, lcu, w, sent = make()
w.refresh_history_and_rank()
LIVE["data"] = live_data(end="Lose")
w.tick()
lcu.phase = "EndOfGame"
w.tick()
lcu.phase = "Lobby"
w.tick()
check(w.pending_result and w.pending_result["rec"]["source"] == "live" and w.pending_result["rec"]["win"] is False,
      "fallback record from live data")
w.pending_result["at"] -= 1000
w.check_pending_timeout()
check(sent[-1][0] == "DEFEAT" and "SP" not in sent[-1][0], "defeat alert without SP after timeout")

# SP changed while League Remote wasn't running (several games) -> recorded, no per-game claim
cfg, lcu, w, sent = make()
w.refresh_history_and_rank()
w2 = lr.Watcher(cfg, lcu, w.notifier)
w2.rank, w2.history_cache = w.rank, w.history_cache
lcu.ranked.update(leaguePoints=10, division="II", wins=62, losses=55)
w2.refresh_history_and_rank()
c = w2.rank.changes()[-1]
check(c["games"] == 3 and c["win"] is None and c["game_id"] is None and c["delta"] == -112,
      "multi-game change across restarts recorded without guessing a single game")

# live API unavailable (e.g. mode without it) -> nothing breaks
cfg, lcu, w, sent = make()
ingame.fetch_live = lambda timeout=1.0: None
w.tick()
check(w.snapshot()["live_ok"] is False and w.snapshot()["game"] is None, "no live data handled gracefully")
lcu.phase = "Lobby"
w.tick()
check(w.pending_result is None, "nothing recorded without data")

# reconnect
cfg, lcu, w, sent = make()
lcu.phase = "Reconnect"
w.tick()
rc = [x for x in sent if x[0] == "RECONNECT NEEDED"]
check(rc and rc[0][2][0]["url"].endswith("/api/reconnect"), "reconnect alert with button")

# ------------------------------------------------------------ http
srv = ThreadingHTTPServer(("127.0.0.1", 5059), lr.make_handler(cfg, lcu, w))
threading.Thread(target=srv.serve_forever, daemon=True).start()


def req(method, path):
    try:
        with urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:5059" + path, method=method)) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


code, body = req("POST", "/api/reconnect")
check(code == 200 and ("POST", "/lol-gameflow/v1/reconnect") in lcu.calls, "phone reconnect button")
code, body = req("GET", "/item/1001")
check(code == 200 and b"1001.png" in body, "item icon proxied")
check(req("GET", "/item/42")[0] == 404, "unknown item 404")
w.refresh_history_and_rank()
code, body = req("GET", "/api/stats")
data = json.loads(body)
check(code == 200 and data["games"] == 5 and data["rank"]["rank"]["emblem"] == "Platinum" and data["loaded"], "/api/stats")
check(data["season"] == {"wins": 60, "losses": 54, "wr": 53} and data["games"] == 5,
      "stats separate the full season record (rank data) from games with details")
check(data["span"]["first"] <= data["span"]["last"], "stats say which dates the detailed games cover")
srv.shutdown()

print("\nALL PASSED" if not failed else "\nSOME FAILED")
sys.exit(1 if failed else 0)
