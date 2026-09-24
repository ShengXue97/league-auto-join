"""Simulated champion select against the real server code (no League client needed).

Run: python tests/test_champ_select.py
"""
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
          {"id": 60081, "name": "Ezreal"}, {"id": 60103, "name": "Ahri"},
          {"id": 80, "name": "Pantheon"},  # modern Pantheon shares the name
          {"id": 1, "name": "Annie"}]
POOL = [60001, 60080, 60103, 60081]


class FakeLCU:
    """Mimics the parts of the League client API used in champ select."""

    def __init__(self):
        self.calls = []
        # my team picks in cell order 0..4, I'm cell 2
        self.actions = [
            [{"id": 10, "actorCellId": ME, "type": "ban", "championId": 0, "completed": False, "isInProgress": True},
             {"id": 11, "actorCellId": 7, "type": "ban", "championId": 0, "completed": False, "isInProgress": True}],
            [{"id": 20 + c, "actorCellId": c, "type": "pick", "championId": 0,
              "completed": False, "isInProgress": False} for c in range(5)],
        ]
        self.team = [{"cellId": c, "championId": 0, "championPickIntent": 0, "gameName": f"P{c}",
                      "assignedPosition": pos} for c, pos in enumerate(["top", "jungle", "middle", "bottom", "utility"])]
        self.team[ME]["championPickIntent"] = 60103
        self.swaps = [{"id": 100 + c, "cellId": c, "state": "AVAILABLE"} for c in range(5) if c != ME]

    def all_actions(self):
        return [a for g in self.actions for a in g]

    def taken(self):
        return {a["championId"] for a in self.all_actions() if a["completed"] and a["championId"]}

    def request(self, method, path, body=None):
        if method != "GET":
            self.calls.append((method, path, body))
        if path == "/lol-gameflow/v1/gameflow-phase":
            return "ChampSelect"
        if path == "/lol-lobby/v2/lobby":
            return {"localMember": {"firstPositionPreference": "TOP", "secondPositionPreference": "JUNGLE",
                                    "thirdPositionPreference": "MIDDLE", "fourthPositionPreference": "BOTTOM",
                                    "fifthPositionPreference": "UTILITY"}}
        if path == "/lol-game-data/assets/v1/champion-summary.json":
            return [{"id": -1, "name": "None"}] + CHAMPS
        if path == "/lol-champ-select/v1/session":
            return {
                "localPlayerCellId": ME,
                "timer": {"phase": "BAN_PICK", "adjustedTimeLeftInPhase": 30000,
                          "internalNowInEpochMs": time.time() * 1000 - 5000},
                "actions": self.actions,
                "myTeam": self.team,
                "theirTeam": [{"cellId": 7, "championId": 0}],
                "pickOrderSwaps": self.swaps,
            }
        if path in ("/lol-champ-select/v1/bannable-champion-ids", "/lol-champ-select/v1/pickable-champion-ids"):
            return [c for c in POOL if c not in self.taken()]  # client hides banned/picked champions
        if method == "PATCH" and path.startswith("/lol-champ-select/v1/session/actions/"):
            aid = int(path.rsplit("/", 1)[-1])
            for a in self.all_actions():
                if a["id"] == aid:
                    a["championId"] = body["championId"]
            return None
        if method == "POST" and path.endswith("/complete"):
            aid = int(path.split("/")[-2])
            for a in self.all_actions():
                if a["id"] == aid:
                    a["completed"], a["isInProgress"] = True, False
            return None
        return None

    def raw(self, path):
        return b"\x89PNG fake", "image/png"

    def start_my_pick(self):
        for a in self.all_actions():
            if a["type"] == "ban":
                a["completed"], a["isInProgress"] = True, False
            if a["id"] == 20 + ME:
                a["isInProgress"] = True


failed = False


def check(cond, msg):
    global failed
    print(("PASS " if cond else "FAIL ") + msg)
    failed |= not cond


def make(cfg_over=None):
    cfg = {"auto_accept": False, "favorite_picks": ["pantheon", "Ahri", "Zed"], "favorite_bans": ["Annie"],
           "notify_your_turn": True, "notify_champ_select": True, "notify_requeue": True}
    cfg.update(cfg_over or {})
    sent = []
    lcu = FakeLCU()
    notifier = lr.Notifier(cfg, "http://pc:5000")
    notifier.send = lambda title, message, **kw: sent.append((title, message, kw.get("actions") or []))
    return cfg, lcu, lr.Watcher(cfg, lcu, notifier), sent


def labels(n):
    return [a["label"] for a in n[2]]


lr.capture = lambda *a, **k: None  # no capture files during tests
lr.save_config = lambda cfg: None  # don't touch the real config.json

# ------------------------------------------------------------ 1. full flow over HTTP
cfg, lcu, w, sent = make()
srv = ThreadingHTTPServer(("127.0.0.1", 5057), lr.make_handler(cfg, lcu, w))
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASE = "http://127.0.0.1:5057"


def req(method, path):
    try:
        with urllib.request.urlopen(urllib.request.Request(BASE + path, method=method)) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


w.tick()
st = json.loads(req("GET", "/api/status")[1])
cs = st["cs"]
check(st["phase"] == "ChampSelect", "phase is ChampSelect")
check(st["version"] == lr.__version__, "status reports version")
check(cs["action"]["type"] == "ban" and cs["action"]["in_progress"], "my ban is in progress")
check(24 <= cs["time_left"] <= 25, f"timer counts from internalNow (got {cs['time_left']})")
check([p["order"] for p in cs["team"]] == [1, 2, 3, 4, 5] and cs["my_order"] == 3, "team sorted by pick order, I'm #3")
check(len(sent) == 1 and sent[0][0].startswith("YOUR TURN TO BAN"), "ban alert sent (no extra champ-select alert)")
check(labels(sent[0]) == ["Open", "Ban Annie"], "ban favorite button")
w.tick()
check(len(sent) == 1, "no duplicate alert on next tick")

check(req("GET", "/api/champs")[0] == 200, "/api/champs ok")
code, body = req("GET", "/icon/60080")
check(code == 200 and body.startswith(b"\x89PNG"), "icon proxied")
check(req("GET", "/icon/../x")[0] == 404, "bad icon id rejected")

code, body = req("POST", "/api/cs/lock?champ=999")
check(code == 409 and b"available" in body, "can't ban unavailable champion")
code, _ = req("POST", "/api/cs/hover?champ=60001")
check(code == 200 and lcu.calls[-1] == ("PATCH", "/lol-champ-select/v1/session/actions/10", {"championId": 60001}),
      "hover PATCHes the ban action")
code, _ = req("POST", "/api/cs/hover?kind=pick&champ=60080")
check(code == 200 and lcu.calls[-1] == ("PATCH", "/lol-champ-select/v1/session/actions/22", {"championId": 60080}),
      "kind=pick hovers my PICK even during my ban turn")
code, _ = req("POST", "/api/cs/lock?champ=60001")
check(code == 200 and lcu.calls[-1] == ("POST", "/lol-champ-select/v1/session/actions/10/complete", None), "ban Annie")

lcu.start_my_pick()
w.tick()
turn = [n for n in sent if n[0].startswith("YOUR TURN TO PICK")]
check(len(turn) == 1 and labels(turn[0]) == ["Open", "Lock Pantheon", "Lock Ahri"],
      "pick alert: favorites in order, case-insensitive, missing (Zed) skipped")
check(not any("UNAVAILABLE" in n[0] for n in sent), "no favorite-lost alert (Annie is only a ban favorite)")

code, body = req("POST", "/api/cs/lock")
check(code == 200 and "Locked in Pantheon" in w.last_event, "lock with no champ uses current hover (Pantheon)")
w.tick()
st = json.loads(req("GET", "/api/status")[1])
check(st["cs"]["action"] is None and st["cs"]["done"], "done after locking")
check(st["cs"]["favorites"][0]["status"] == "mine", "Pantheon shows as mine")
code, body = req("POST", "/api/cs/lock?champ=60001")
check(code == 409 and b"no pick" in body, "no further actions allowed")

# favorites editing over HTTP
code, _ = req("POST", "/api/favorites?op=add&kind=pick&name=ezreal")
check(cfg["favorite_picks"][-1] == "Ezreal", "add favorite (name normalized)")
req("POST", "/api/favorites?op=up&kind=pick&name=Ezreal")
check(cfg["favorite_picks"] == ["pantheon", "Ahri", "Ezreal", "Zed"], "move favorite up")
req("POST", "/api/favorites?op=remove&kind=pick&name=Zed")
check("Zed" not in cfg["favorite_picks"], "remove favorite")
code, body = req("POST", "/api/favorites?op=add&kind=pick&name=Notachamp")
check(code == 409, "unknown champion rejected")
srv.shutdown()

# ------------------------------------------------------------ 2. favorite banned -> alert with next favorite
cfg, lcu, w, sent = make()
lcu.team[ME]["championPickIntent"] = 0  # not hovering anything yet
w.tick()
enemy_ban = lcu.actions[0][1]
enemy_ban.update(championId=60080, completed=True, isInProgress=False)
w.tick()
lost = [n for n in sent if "UNAVAILABLE" in n[0]]
check(len(lost) == 1 and "Pantheon was banned" in lost[0][1] and "Next up: Ahri" in lost[0][1],
      "Pantheon banned -> alert suggests Ahri")
check(labels(lost[0]) == ["Open", "Hover Ahri"], "alert has Hover Ahri button")
check(lost[0][2][1]["url"].endswith("/api/cs/hover?kind=pick&champ=60103"), "hover button targets my pick")
w.tick()
check(len([n for n in sent if "UNAVAILABLE" in n[0]]) == 1, "favorite-lost alert only once")
favs = {f["name"]: f["status"] for f in w.champ_select_state()["favorites"]}
check(favs == {"Pantheon": "banned", "Ahri": "available"}, f"favorite statuses {favs}")

# already hovering the next favorite -> suggest it, but no redundant hover button
cfg, lcu, w, sent = make()
lcu.actions[0][1].update(championId=60080, completed=True, isInProgress=False)
w.tick()
lost = [n for n in sent if "UNAVAILABLE" in n[0]]
check(lost and "Next up: Ahri" in lost[0][1] and labels(lost[0]) == ["Open"],
      "hovering Ahri already -> 'Next up: Ahri', no hover button")

# ally locks my favorite
cfg, lcu, w, sent = make()
lcu.team[0]["championId"] = 60080
lcu.actions[1][0].update(championId=60080, completed=True)
w.tick()
lost = [n for n in sent if "UNAVAILABLE" in n[0]]
check(lost and "taken by a teammate (Top)" in lost[0][1], "ally took Pantheon -> alert names their role, not their name")

# ------------------------------------------------------------ 3. League Classic id preferred over modern id
cfg, lcu, w, sent = make()
check(w.resolve("Pantheon", {60080, 60001}) == 60080 and w.resolve("Pantheon", {80}) == 80,
      "name resolves to the id present in this champ select")

# ------------------------------------------------------------ 4. pick order swaps
cfg, lcu, w, sent = make()
lcu.start_my_pick()
cs = w.champ_select_state()
check(cs["swap_up"]["cell"] == 0 and cs["swap_up"]["order"] == 1, "swap-up targets the earliest pick (#1)")
lcu.swaps[0]["state"] = "BUSY"
check(w.champ_select_state()["swap_up"]["cell"] == 1, "falls back to next earliest when #1 is busy")
lcu.swaps[0]["state"] = "AVAILABLE"
lcu.actions[1][0].update(completed=True, championId=60081)  # #1 already picked
check(w.champ_select_state()["swap_up"]["cell"] == 1, "never offers a swap with someone who already picked")
lcu.actions[1][0].update(completed=False, championId=0)
w.cs_swap("up")
check(lcu.calls[-1] == ("POST", "/lol-champ-select/v1/session/pick-order-swaps/100/request", None),
      "swap-up POSTs a request to #1")

# outgoing request accepted -> my order improves
lcu.swaps[0]["state"] = "SENT"
w.tick()
check(w.champ_select_state()["swap_up"] is None, "no second swap-up while a request is pending")
lcu.swaps[0]["state"] = "AVAILABLE"
lcu.actions[1][0]["actorCellId"], lcu.actions[1][ME]["actorCellId"] = ME, 0  # we traded pick slots
w.tick()
check(any(n[0] == "Swap accepted" and "#1" in n[1] for n in sent), "alert when my swap is accepted")

# incoming requests
cfg, lcu, w, sent = make()
lcu.start_my_pick()
lcu.swaps[3]["state"] = "RECEIVED"  # cell 4 (#5) asks me (#3)
w.tick()
inc = [n for n in sent if n[0].startswith("SWAP REQUEST")]
check(len(inc) == 1 and "LATER" in inc[0][1] and labels(inc[0]) == ["ACCEPT", "DECLINE"],
      "later-pick request -> warning alert with ACCEPT/DECLINE")
lcu.swaps[3]["state"] = "AVAILABLE"
lcu.swaps[0]["state"] = "RECEIVED"  # cell 0 (#1) asks me
w.tick()
inc = [n for n in sent if n[0].startswith("SWAP REQUEST")]
check(len(inc) == 2 and "EARLIER" in inc[1][1], "earlier-pick request -> recommended alert")
check(inc[1][2][0]["url"].endswith("/api/cs/swap?op=accept&id=100"), "ACCEPT button targets swap 100")
w.cs_swap("accept", 100)
check(lcu.calls[-1] == ("POST", "/lol-champ-select/v1/session/pick-order-swaps/100/accept", None), "accept swap")
for bad in (("hack", 1), ("accept", None)):
    try:
        w.cs_swap(*bad)
        check(False, f"bad swap {bad} rejected")
    except ValueError:
        check(True, f"bad swap {bad} rejected")

# ------------------------------------------------------------ 5. champ select start alert buttons
cfg, lcu, w, sent = make()
for a in lcu.all_actions():
    a["isInProgress"] = False  # planning phase: nobody's turn yet
w.last_phase = "Matchmaking"
w.tick()
start = [n for n in sent if n[0] == "CHAMP SELECT STARTED"]
check(len(start) == 1 and labels(start[0]) == ["Open", "Hover Pantheon", "Ask #1 to swap"],
      "start alert: Hover Pantheon + Ask #1 to swap")

# ------------------------------------------------------------ 6. Aegis of Valor
cfg, lcu, w, sent = make()
for a in lcu.all_actions():
    a["isInProgress"] = False
w.last_phase = "Matchmaking"
w.rank = __import__("rank").RankTracker(os.path.join(__import__("tempfile").mkdtemp(), "r.jsonl"))
w.tick()
cs = w.snapshot()["cs"]
check(cs["aegis"] and cs["aegis"]["role_name"] == "Mid" and cs["aegis"]["pref"] == 3 and cs["aegis"]["bonus"] == 40,
      f"assigned Mid = 3rd preference -> Aegis +40% ({cs['aegis']})")
check(cs["aegis"]["base_win"] is None, "no SP estimate in the banner before your win SP is learned")
start = [n for n in sent if n[0] == "CHAMP SELECT STARTED"]
check(start and "Aegis of Valor possible: Mid is your #3 role" in start[0][1], "start alert mentions Aegis")
check(w.game_context == {"role": "MIDDLE", "pref": 3, "aegis": True}, "role remembered for SP tracking")
lcu.team[ME]["assignedPosition"] = "bottom"  # role swap into another #3-#5 role
w.tick()
ae = w.snapshot()["cs"]["aegis"]
check(ae and ae["lost"] and ae["role_name"] == "Mid" and ae["now"] == "Bot",
      f"swapped Mid -> Bot: Aegis lost even though Bot is #4 ({ae})")
check(w.game_context == {"role": "BOTTOM", "pref": 4, "aegis": False}, "swapped game tracked as a normal game")
cfg, lcu, w, sent = make()
lcu.team[ME]["assignedPosition"] = "jungle"  # autofilled into 2nd preference
w.tick()
check(w.snapshot()["cs"]["aegis"] is None and w.game_context["aegis"] is False, "2nd preference -> no Aegis")

# ------------------------------------------------------------ 7. SAFETY
cfg, lcu, w, sent = make()
w.tick()
blob = json.dumps(w.snapshot())
check(not any(f"P{c}" in blob for c in range(5)), "SAFETY: teammate names never reach the page in champ select")
check([p["name"] for p in w.snapshot()["cs"]["team"]] == ["Top", "Jungle", "Mid", "Bot", "Support"],
      "teammates shown by role")
cfg, lcu, w, sent = make({"auto_accept": True})  # old config from an earlier version
w.on_phase_change("Matchmaking", "ReadyCheck", {})
check(not any("ready-check/accept" in c[1] for c in lcu.calls) and sent[-1][0] == "MATCH FOUND!",
      "SAFETY: never accepts on its own, even with an old auto_accept config")

# ------------------------------------------------------------ 8. not your turn
cfg, lcu, w, sent = make()
lcu.actions[0][0]["isInProgress"] = False
try:
    w.cs_act(60001, lock=True)
    check(False, "lock before your turn refused")
except ValueError as e:
    check("not your turn" in str(e), "lock before your turn refused")

print("\nALL PASSED" if not failed else "\nSOME FAILED")
sys.exit(1 if failed else 0)
