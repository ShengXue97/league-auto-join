"""
Run League Remote's real server with a scripted, fake League client - for UI work and screenshots.
Never talks to a real League client (except, with --icons, to read champion/item images).

  python tools/demo.py <scenario> [--port 8790] [--icons]

Scenarios: idle, queue, readycheck, champselect, ingame, postgame, offline
"""
import copy
import json
import os
import random
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
DATA = tempfile.mkdtemp(prefix="lr-demo-")
os.environ["LEAGUE_REMOTE_DATA"] = DATA
os.environ["LEAGUE_REMOTE_NO_CLIENT"] = "1"

import ingame  # noqa: E402
import league_remote as lr  # noqa: E402

CHAMPS = {60001: "Annie", 60002: "Olaf", 60003: "Galio", 60004: "Twisted Fate", 60005: "Xin Zhao",
          60080: "Pantheon", 60081: "Ezreal", 60103: "Ahri", 60016: "Garen", 60104: "Lux", 60105: "Nasus",
          60114: "Sion", 60040: "Janna", 60055: "Katarina", 60064: "Lee Sin", 60086: "Master Yi"}
T0 = time.time()


def champ_select_session():
    left = max(3000, 27000 - (time.time() - T0) * 1000)
    me = 2
    actions = [
        [{"id": 1, "actorCellId": 3, "type": "ban", "championId": 60086, "completed": True, "isInProgress": False},
         {"id": 2, "actorCellId": 8, "type": "ban", "championId": 60103, "completed": True, "isInProgress": False}],
        [{"id": 10, "actorCellId": 0, "type": "pick", "championId": 60005, "completed": True, "isInProgress": False},
         {"id": 11, "actorCellId": 5, "type": "pick", "championId": 60016, "completed": True, "isInProgress": False}],
        [{"id": 12, "actorCellId": 1, "type": "pick", "championId": 60040, "completed": False, "isInProgress": False},
         {"id": 13, "actorCellId": me, "type": "pick", "championId": 60080, "completed": False, "isInProgress": True}],
        [{"id": 14, "actorCellId": 3, "type": "pick", "championId": 0, "completed": False, "isInProgress": False},
         {"id": 15, "actorCellId": 4, "type": "pick", "championId": 0, "completed": False, "isInProgress": False}],
    ]
    pos = ["jungle", "utility", "top", "middle", "bottom"]
    team = [{"cellId": c, "championId": {0: 60005, me: 60080}.get(c, 0), "championPickIntent": {1: 60040}.get(c, 0),
             "assignedPosition": pos[c]} for c in range(5)]
    return {"localPlayerCellId": me, "actions": actions, "myTeam": team,
            "theirTeam": [{"cellId": 5 + i, "championId": [60016, 0, 0, 0, 0][i]} for i in range(5)],
            "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": left, "internalNowInEpochMs": time.time() * 1000},
            "pickOrderSwaps": [{"id": 100 + c, "cellId": c, "state": "AVAILABLE"} for c in (1, 3, 4)]}


def history(n=40):
    random.seed(7)
    games = []
    for i in range(n):
        champ = random.choice([60080] * 6 + [60005, 60002, 60003])
        win = random.random() < 0.56
        k, d, a = random.randint(2, 14), random.randint(1, 8), random.randint(2, 14)
        games.append({"gameId": 177000000 + i, "gameMode": "JADE", "queueId": 4310,
                      "gameDuration": random.randint(1300, 2200), "gameCreation": (T0 - (n - i) * 5400) * 1000,
                      "participants": [{"participantId": 1, "championId": champ,
                                        "stats": {"win": win, "kills": k, "deaths": d, "assists": a,
                                                  "totalMinionsKilled": random.randint(120, 230),
                                                  "neutralMinionsKilled": random.randint(0, 20)}}]})
    return {"games": {"games": list(reversed(games))}}


def live_data(result=None):
    def p(name, champ, team, k, d, a, cs, items, dead=False):
        return {"championName": champ, "rawChampionName": f"game_character_displayname_Jade_{champ.replace(' ', '')}",
                "riotId": f"{name}#DEMO", "riotIdGameName": name, "summonerName": f"{name}#DEMO", "team": team,
                "level": random.randint(11, 15), "isDead": dead, "respawnTimer": 14.0 if dead else 0,
                "scores": {"kills": k, "deaths": d, "assists": a, "creepScore": cs, "wardScore": 14.2},
                "items": [{"itemID": i, "slot": s} for s, i in enumerate(items)]}
    t = 1422.0
    ev = [{"EventName": "GameStart", "EventTime": 0}, {"EventName": "FirstBlood", "EventTime": 201, "Recipient": "You"},
          {"EventName": "ChampionKill", "EventTime": 201, "KillerName": "You", "VictimName": "Foe2", "Assisters": []},
          {"EventName": "DragonKill", "EventTime": 610, "KillerName": "Ally1", "DragonType": "Fire", "Stolen": "False"},
          {"EventName": "TurretKilled", "EventTime": 900, "KillerName": "You", "TurretKilled": "Turret_T2_C_05_A"},
          {"EventName": "ChampionKill", "EventTime": 1180, "KillerName": "Foe1", "VictimName": "You", "Assisters": []},
          {"EventName": "Multikill", "EventTime": 1300, "KillerName": "You", "KillStreak": 2}]
    if result:
        ev.append({"EventName": "GameEnd", "EventTime": t, "Result": result})
    return {"activePlayer": {"riotId": "You#DEMO", "riotIdGameName": "You", "summonerName": "You#DEMO", "currentGold": 1375},
            "allPlayers": [p("You", "Pantheon", "ORDER", 9, 3, 6, 171, (3071, 3047, 3134, 1036, 3340)),
                           p("Ally1", "Xin Zhao", "ORDER", 5, 4, 9, 132, (3078, 3111, 3340)),
                           p("Ally2", "Janna", "ORDER", 1, 2, 17, 31, (3853, 3158), dead=True),
                           p("Ally3", "Lux", "ORDER", 7, 5, 8, 189, (3285, 3020, 1052, 3340)),
                           p("Ally4", "Ezreal", "ORDER", 4, 6, 5, 201, (3508, 3006, 1038, 3340)),
                           p("Foe1", "Garen", "CHAOS", 6, 5, 3, 160, (3078, 3047)),
                           p("Foe2", "Annie", "CHAOS", 3, 7, 5, 150, (3100, 3020)),
                           p("Foe3", "Olaf", "CHAOS", 5, 5, 4, 120, (3071, 3111)),
                           p("Foe4", "Galio", "CHAOS", 2, 4, 9, 140, (3068,)),
                           p("Foe5", "Twisted Fate", "CHAOS", 4, 5, 6, 190, (3100, 3020))],
            "events": {"Events": ev}, "gameData": {"gameMode": "JADE", "gameTime": t + (time.time() - T0)}}


class FakeLCU:
    def __init__(self, scenario, real=None):
        self.scenario = scenario
        self.real = real
        self.hist = history()

    def request(self, method, path, body=None, timeout=3):
        s = self.scenario
        if s == "offline":
            raise ConnectionError("League client not running")
        if path == "/lol-gameflow/v1/gameflow-phase":
            return {"idle": "Lobby", "queue": "Matchmaking", "readycheck": "ReadyCheck", "champselect": "ChampSelect",
                    "ingame": "InProgress", "postgame": "EndOfGame"}[s]
        if path == "/lol-matchmaking/v1/search":
            return {"timeInQueue": 312 + (time.time() - T0), "estimatedQueueTime": 1200}
        if path == "/lol-matchmaking/v1/ready-check":
            return {"state": "InProgress", "playerResponse": "None", "timer": 2 + (time.time() - T0) % 6}
        if path == "/lol-champ-select/v1/session":
            return champ_select_session()
        if path in ("/lol-champ-select/v1/pickable-champion-ids", "/lol-champ-select/v1/bannable-champion-ids"):
            return [c for c in CHAMPS if c not in (60086, 60103, 60005, 60016)]
        if path == "/lol-game-data/assets/v1/champion-summary.json":
            return [{"id": i, "name": n, "alias": "Jade_" + n.replace(" ", "")} for i, n in CHAMPS.items()]
        if path == "/lol-game-data/assets/v1/items.json":
            return self.real.request("GET", path) if self.real else []
        if path == "/lol-lobby/v2/lobby":
            return {"localMember": {"firstPositionPreference": "MIDDLE", "secondPositionPreference": "JUNGLE",
                                    "thirdPositionPreference": "TOP", "fourthPositionPreference": "BOTTOM",
                                    "fifthPositionPreference": "UTILITY"}}
        if path == "/lol-ranked/v1/current-ranked-stats":
            return {"queueMap": {"JADE_RANKED_SOLO_5x5": {"tier": "DIAMOND", "division": "IV", "leaguePoints": 44,
                                                          "wins": 66, "losses": 55, "highestTier": "DIAMOND",
                                                          "highestDivision": "IV"}}}
        if path.startswith("/lol-match-history/v1/products/"):
            return self.hist
        if path.startswith("/lol-match-history/v1/games/"):
            return None
        if path == "/lol-summoner/v1/current-summoner":
            return {"puuid": "me"}
        if path.startswith("/lol-ranked/v1/league-ladders/"):
            return [{"queueType": "JADE_RANKED_SOLO_5x5", "divisions": [{"standings":
                    [{"puuid": f"p{i}"} for i in range(2)] + [{"puuid": "me", "position": 3}] + [{"puuid": f"q{i}"} for i in range(14)]}]}]
        if path == "/lol-gameflow/v1/session":
            return {"gameData": {"gameId": 177100000, "playerChampionSelections": [{"championId": 60080}]}}
        if path == "/lol-end-of-game/v1/eog-stats-block":
            return None
        return None

    def raw(self, path):
        if self.real:
            return self.real.raw(path)
        raise ConnectionError("no icons in demo (use --icons)")

    def accept(self):
        pass

    def decline(self):
        pass


def seed_rank_history():
    changes = []
    pos, w, l = 1900, 60, 53
    for i, (win, d, pref) in enumerate([(1, 22, 1), (1, 21, 2), (0, -18, 1), (1, 23, 1), (0, -17, 2),
                                         (1, 44, 5), (1, 22, 1), (0, -19, 1)]):
        before = {"pos": pos, "wins": w, "losses": l}
        pos, w, l = pos + d, w + win, l + (1 - win)
        changes.append({"time": time.strftime("%Y-%m-%d %H:%M", time.localtime(T0 - (8 - i) * 5400)), "games": 1,
                        "win": bool(win), "delta": d, "before": before, "after": {"pos": pos, "wins": w, "losses": l},
                        "game_id": str(177000032 + i), "champ": "Pantheon",
                        "role": {1: "MIDDLE", 2: "JUNGLE", 5: "UTILITY"}[pref], "pref": pref, "aegis": pref == 5})
    with open(os.path.join(DATA, "rank_history.jsonl"), "w", encoding="utf-8") as f:
        for c in changes:
            f.write(json.dumps(c) + "\n")
    with open(os.path.join(DATA, "rank_history.jsonl.last"), "w", encoding="utf-8") as f:
        json.dump({"pos": 2044, "wins": 66, "losses": 55}, f)


def main():
    scenario = sys.argv[1] if len(sys.argv) > 1 else "idle"
    port = int(sys.argv[sys.argv.index("--port") + 1]) if "--port" in sys.argv else 8790
    with open(os.path.join(DATA, "config.json"), "w") as f:
        json.dump({"port": port, "ntfy_server": "http://127.0.0.1:9", "ntfy_topic": "league-3f9a1c07be",
                   "favorite_picks": ["Pantheon", "Xin Zhao", "Galio"], "last_version": lr.__version__}, f)
    seed_rank_history()
    lr.capture = lambda *a, **k: None
    real = None
    if "--icons" in sys.argv:  # read-only: champion/item images from the real client's game data
        os.environ.pop("LEAGUE_REMOTE_NO_CLIENT", None)
        real = lr.LCU()
    cfg = lr.load_config()
    lcu = FakeLCU(scenario, real)
    notifier = lr.Notifier(cfg, f"http://127.0.0.1:{port}")
    notifier.send = lambda *a, **k: None
    ingame.fetch_live = lambda timeout=1.0: copy.deepcopy(
        live_data("Win" if scenario == "postgame" else None)) if scenario in ("ingame", "postgame") else None
    w = lr.Watcher(cfg, lcu, notifier)

    class NoUpdate:
        latest = None
        def status(self): return None
        def check_now(self): return "latest", f"You're up to date (v{lr.__version__})."
        def update_now(self, log): return False
    w.updater = NoUpdate()
    try:
        w.refresh_history_and_rank()
    except ConnectionError:
        pass
    server = lr.ThreadingHTTPServer(("127.0.0.1", port), lr.make_handler(cfg, lcu, w))
    threading.Thread(target=w.run, daemon=True).start()
    print(f"demo '{scenario}' on http://127.0.0.1:{port}  (data: {DATA})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
