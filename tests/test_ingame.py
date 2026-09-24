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

# ------------------------------------------------------------ match log
tmp = tempfile.mkdtemp()
log = ingame.MatchLog(os.path.join(tmp, "m.jsonl"))
check(log.stats()["games"] == 0 and log.stats()["wr"] is None, "empty history")


def rec(i, win, k=5, d=2, a=5, cs=150, secs=1500, champ="Pantheon", kills=15):
    return ingame._record(i, "JADE", champ, 60080, win, k, d, a, cs, secs, kills)


for i, w in enumerate([True, False, True]):
    log.add(rec(i, w))
check(log.add(rec(1, True)) == (False, []), "duplicate game ignored")
added, notes = log.add(rec(9, True, k=12, cs=250))
check(added and any("best CS/min" in n for n in notes) and any("best kills" in n for n in notes),
      f"personal best notes: {notes}")
log.add(rec(10, False, champ="Ahri"))
st = log.stats(["Pantheon"])
check(st["games"] == 5 and st["wins"] == 3 and st["wr"] == 60, "overall win rate")
check(st["streak"] == {"count": 1, "win": False}, "current streak")
check(st["champions"][0]["champ"] == "Pantheon" and st["champions"][0]["fav"], "favorite listed first")
pan = st["champions"][0]
check(pan["games"] == 4 and pan["wr"] == 75 and pan["best"]["score"] == "12/2/5", "per-champion stats")
check(st["recent"][0]["champ"] == "Ahri" and len(st["trend"]) == 5, "recent games newest first, trend")

eog = {"gameId": 777, "gameLength": 1800, "gameMode": "JADE",
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


class FakeLCU:
    def __init__(self):
        self.phase = "InProgress"
        self.eog = None
        self.calls = []

    def request(self, method, path, body=None):
        if method != "GET":
            self.calls.append((method, path))
        if path == "/lol-gameflow/v1/gameflow-phase":
            return self.phase
        if path == "/lol-gameflow/v1/session":
            return {"gameData": {"gameId": 555, "playerChampionSelections": [{"championId": 60080}]}}
        if path == "/lol-game-data/assets/v1/champion-summary.json":
            return [{"id": 80, "name": "Pantheon", "alias": "Pantheon"},
                    {"id": 60080, "name": "Pantheon", "alias": "Jade_Pantheon"},
                    {"id": 103, "name": "Ahri", "alias": "Ahri"}]
        if path == "/lol-game-data/assets/v1/items.json":
            return [{"id": 1001, "iconPath": "/lol-game-data/assets/ASSETS/Items/Icons2D/1001.png"}]
        if path == "/lol-end-of-game/v1/eog-stats-block":
            return self.eog
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
    w.match_log = ingame.MatchLog(os.path.join(tempfile.mkdtemp(), "m.jsonl"))
    return cfg, lcu, w, sent


LIVE = {"data": live_data()}
ingame.fetch_live = lambda timeout=1.0: copy.deepcopy(LIVE["data"])

cfg, lcu, w, sent = make()
w.tick()
st = w.snapshot()
check(st["game"]["me"]["champ_id"] == 60080, "live champion resolved to Classic Pantheon via alias")
check(st["live_ok"] and st["cs_goal"] == 7.0, "status has live data and CS goal")
check([t for t, *_ in sent] == ["GAME LOADED"], "game loaded alert")
w._live_at = 0
w.tick()
check(len(sent) == 1, "game loaded alert only once")

# game over with end-of-game stats
lcu.phase, lcu.eog = "EndOfGame", eog
w.tick()
check(sent[-1][0] == "VICTORY" and "Pantheon 8/2/10" in sent[-1][1] and "Today: 1W 0L" in sent[-1][1],
      f"victory alert: {sent[-1][:2]}")
check(sent[-1][2][0]["url"].endswith("/#stats"), "alert links to stats")
check(w.snapshot()["game"] is not None, "final scoreboard still visible after the game")
lcu.phase = "Lobby"
w.tick()
check(len(w.match_log.load()) == 1 and sum(t == "VICTORY" for t, *_ in sent) == 1, "recorded once, no fallback duplicate")

# no end-of-game stats -> fallback to last live snapshot
cfg, lcu, w, sent = make()
LIVE["data"] = live_data(end="Lose")
w.tick()
lcu.phase = "EndOfGame"
w.tick()
lcu.phase = "Lobby"
w.tick()
games = w.match_log.load()
check(len(games) == 1 and games[0]["source"] == "live" and games[0]["win"] is False and games[0]["id"] == "555",
      "fallback record from live data")
check(sent[-1][0] == "DEFEAT", "defeat alert")

# live API unavailable (e.g. mode without it) -> nothing breaks
cfg, lcu, w, sent = make()
ingame.fetch_live = lambda timeout=1.0: None
w.tick()
check(w.snapshot()["live_ok"] is False and w.snapshot()["game"] is None, "no live data handled gracefully")
lcu.phase = "Lobby"
w.tick()
check(w.match_log.load() == [], "nothing recorded without data")

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
w.match_log.add(rec(1, True))
code, body = req("GET", "/api/stats")
check(code == 200 and json.loads(body)["games"] == 1, "/api/stats")
srv.shutdown()

print("\nALL PASSED" if not failed else "\nSOME FAILED")
sys.exit(1 if failed else 0)
