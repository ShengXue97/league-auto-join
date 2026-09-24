"""Simulated champion select against the real server code (no League client needed)."""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import league_remote as lr

ME = 2
CHAMPS = [{"id": 60001, "name": "Annie"}, {"id": 60080, "name": "Pantheon"},
          {"id": 60081, "name": "Ezreal"}, {"id": 60103, "name": "Ahri"}, {"id": 1, "name": "Annie (modern)"}]


class FakeLCU:
    def __init__(self):
        self.calls = []
        self.actions = [
            [{"id": 10, "actorCellId": ME, "type": "ban", "championId": 0, "completed": False, "isInProgress": True}],
            [{"id": 20, "actorCellId": ME, "type": "pick", "championId": 0, "completed": False, "isInProgress": False},
             {"id": 21, "actorCellId": 3, "type": "pick", "championId": 60081, "completed": True, "isInProgress": False}],
        ]

    def request(self, method, path, body=None):
        if method != "GET":
            self.calls.append((method, path, body))
        if method == "GET" and path == "/lol-gameflow/v1/gameflow-phase":
            return "ChampSelect"
        if path == "/lol-game-data/assets/v1/champion-summary.json":
            return [{"id": -1, "name": "None"}] + CHAMPS
        if path == "/lol-champ-select/v1/session":
            return {
                "localPlayerCellId": ME,
                "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 30000,
                          "internalNowInEpochMs": time.time() * 1000 - 5000},
                "actions": self.actions,
                "myTeam": [{"cellId": ME, "championId": 0, "championPickIntent": 60103, "assignedPosition": "MIDDLE"},
                           {"cellId": 3, "championId": 60081, "gameName": "Ally2", "assignedPosition": "JUNGLE"}],
                "theirTeam": [{"championId": 0}],
            }
        if path == "/lol-champ-select/v1/bannable-champion-ids":
            return [60001, 60080, 60103]
        if path == "/lol-champ-select/v1/pickable-champion-ids":
            return [60001, 60080, 60103]
        if method == "PATCH" and path.startswith("/lol-champ-select/v1/session/actions/"):
            aid = int(path.rsplit("/", 1)[-1])
            for a in (x for g in self.actions for x in g):
                if a["id"] == aid:
                    a["championId"] = body["championId"]
            return None
        if method == "POST" and path.endswith("/complete"):
            aid = int(path.split("/")[-2])
            for a in (x for g in self.actions for x in g):
                if a["id"] == aid:
                    a["completed"], a["isInProgress"] = True, False
                if a["id"] == 20 and aid == 10:
                    a["isInProgress"] = True  # my pick turn starts after my ban
            return None
        return None

    def raw(self, path):
        return b"\x89PNG fake", "image/png"


sent = []
cfg = {"auto_accept": False, "favorite_picks": ["pantheon", "Zed"], "favorite_bans": ["Annie"],
       "notify_your_turn": True, "notify_champ_select": True, "notify_requeue": True}
lcu = FakeLCU()
notifier = lr.Notifier(cfg, "http://pc:5000")
notifier.send = lambda title, message, **kw: sent.append((title, kw.get("actions")))
w = lr.Watcher(cfg, lcu, notifier)
lr.capture = lambda *a, **k: None  # don't write capture files during the test

srv = ThreadingHTTPServer(("127.0.0.1", 5057), lr.make_handler(cfg, lcu, w))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:5057"


def req(method, path):
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, method=method)) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        globals()["failed"] = True


failed = False
w.tick()
st = json.loads(req("GET", "/api/status")[1])
cs = st["cs"]
check(st["phase"] == "ChampSelect", "phase is ChampSelect")
check(st["version"] == lr.__version__, "status reports version")
check(cs["action"]["type"] == "ban" and cs["action"]["in_progress"], "my ban is in progress")
check(24 <= cs["time_left"] <= 25, f"timer counts from internalNow (got {cs['time_left']})")
check(cs["choices"] == [60001, 60080, 60103], "bannable list used for ban")
check(cs["team"][0]["champ"] == 60103 and not cs["team"][0]["locked"], "my pick intent shown, not locked")
check(cs["team"][1]["locked"], "teammate shown locked")
check(len(sent) == 1 and sent[0][0].startswith("YOUR TURN TO BAN"), f"ban notification sent: {sent}")
check([a["label"] for a in sent[0][1]] == ["Open", "Ban Annie"], "ban favorite button only for available champ")
w.tick()
check(len(sent) == 1, "no duplicate notification on next tick")

code, _ = req("GET", "/api/champs")
check(code == 200, "/api/champs ok")
code, body = req("GET", "/icon/60080")
check(code == 200 and body.startswith(b"\x89PNG"), "icon proxied")
check(req("GET", "/icon/../x")[0] == 404, "bad icon id rejected")

code, body = req("POST", "/api/cs/lock?champ=60081")
check(code == 409 and b"available" in body, "can't ban unavailable champion")
code, _ = req("POST", "/api/cs/hover?champ=60080")
check(code == 200 and lcu.calls[-1] == ("PATCH", "/lol-champ-select/v1/session/actions/10", {"championId": 60080}), "hover PATCHes ban action")
code, _ = req("POST", "/api/cs/lock?champ=60080")
check(code == 200 and lcu.calls[-1] == ("POST", "/lol-champ-select/v1/session/actions/10/complete", None), "ban completes action")

w.tick()
st = json.loads(req("GET", "/api/status")[1])
check(st["cs"]["action"]["type"] == "pick" and st["cs"]["action"]["id"] == 20, "next action is my pick")
check(len(sent) == 2 and sent[1][0].startswith("YOUR TURN TO PICK"), "pick notification sent")
check([a["label"] for a in sent[1][1]] == ["Open", "Lock Pantheon"], "pick favorites: case-insensitive, unavailable skipped")

code, body = req("POST", "/api/cs/lock")
check(code == 409 and b"Choose" in body, "lock without champion refused")
code, _ = req("POST", "/api/cs/lock?champ=60103")
check(code == 200, "lock in Ahri")
w.tick()
st = json.loads(req("GET", "/api/status")[1])
check(st["cs"]["action"] is None and st["cs"]["done"], "done after locking")
code, body = req("POST", "/api/cs/lock?champ=60001")
check(code == 409 and b"no pick" in body, "no further actions allowed")

# not your turn yet
lcu2 = FakeLCU()
lcu2.actions[0][0]["isInProgress"] = False
w2 = lr.Watcher(cfg, lcu2, notifier)
try:
    w2.cs_act(60001, lock=True)
    check(False, "lock before turn refused")
except ValueError as e:
    check("not your turn" in str(e), "lock before turn refused")
w2.cs_act(60001, lock=False)
check(lcu2.calls[-1][0] == "PATCH", "hover allowed before your turn")

srv.shutdown()
print("\nALL PASSED" if not failed else "\nSOME FAILED")
sys.exit(1 if failed else 0)
