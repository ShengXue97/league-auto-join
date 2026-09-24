"""
League Remote Accept
--------------------
Watches the League client for "Match Found", pushes a notification to your
phone (via ntfy.sh) with ACCEPT / DECLINE buttons, and serves a small phone
control page on your home Wi-Fi. Optional auto-accept toggle.

Champion select: pick and ban from your phone. Nothing is ever picked or
banned automatically - every choice and lock-in is your own tap.

Standard library only. Run:  python league_remote.py
"""

import base64
import json
import os
import secrets
import socket
import ssl
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
PAGE_PATH = os.path.join(HERE, "phone.html")

DEFAULT_LOCKFILES = [
    r"C:\Riot Games\League of Legends\lockfile",
    r"D:\Riot Games\League of Legends\lockfile",
]
POLL_SECONDS = 0.5

# LCU uses a self-signed certificate on 127.0.0.1
_INSECURE = ssl.create_default_context()
_INSECURE.check_hostname = False
_INSECURE.verify_mode = ssl.CERT_NONE


def log(msg):
    print(time.strftime("[%H:%M:%S] ") + msg, flush=True)


CAPTURE_DIR = os.path.join(HERE, "capture")


def capture(name, data):
    """Save raw client data so we can study unfamiliar modes (e.g. JADE champ select)."""
    try:
        os.makedirs(CAPTURE_DIR, exist_ok=True)
        path = os.path.join(CAPTURE_DIR, time.strftime("%Y%m%d-%H%M%S-") + name + ".json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
    except Exception as e:
        log(f"capture failed: {e}")


# ---------------------------------------------------------------- config

def load_config():
    cfg = {}
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
    changed = False
    defaults = {
        "ntfy_topic": "league-" + secrets.token_hex(5),
        "ntfy_server": "https://ntfy.sh",
        "port": 5000,
        "auto_accept": False,
        "notify_champ_select": True,
        "notify_requeue": True,
        "notify_your_turn": True,
        # Champion names shown as one-tap buttons in the "your turn" notification
        "favorite_picks": [],
        "favorite_bans": [],
        "lockfile": "",
    }
    for k, v in defaults.items():
        if k not in cfg:
            cfg[k] = v
            changed = True
    if changed:
        save_config(cfg)
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # no packets sent; just picks the LAN interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


# ---------------------------------------------------------------- LCU client

class LCU:
    def __init__(self, lockfile_hint=""):
        self.hint = lockfile_hint
        self.base = None
        self.auth = None

    def _credentials(self):
        paths = [self.hint] if self.hint else []
        paths += DEFAULT_LOCKFILES
        for p in paths:
            if p and os.path.exists(p):
                try:
                    with open(p, encoding="utf-8") as f:
                        _name, _pid, port, password, proto = f.read().strip().split(":")
                    return port, password
                except (OSError, ValueError):
                    pass
        # Fallback: read port/token from the running client's command line
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Process -Filter \"name='LeagueClientUx.exe'\").CommandLine"],
                capture_output=True, text=True, timeout=10,
            ).stdout
            port = out.split("--app-port=")[1].split('"')[0].split()[0]
            token = out.split("--remoting-auth-token=")[1].split('"')[0].split()[0]
            return port, token
        except (IndexError, OSError, subprocess.SubprocessError):
            return None

    def connect(self):
        creds = self._credentials()
        if not creds:
            self.base = None
            return False
        port, password = creds
        self.base = f"https://127.0.0.1:{port}"
        self.auth = "Basic " + base64.b64encode(f"riot:{password}".encode()).decode()
        return True

    def request(self, method, path, body=None):
        """Returns parsed JSON (or None). Raises ConnectionError if client is unreachable."""
        if not self.base and not self.connect():
            raise ConnectionError("League client not running")
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Authorization", self.auth)
        req.add_header("Accept", "application/json")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, context=_INSECURE, timeout=3) as r:
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        except (urllib.error.URLError, OSError) as e:
            self.base = None  # client restarted -> re-read lockfile next time
            raise ConnectionError(str(e))

    def raw(self, path):
        """Fetch non-JSON content (champion icons)."""
        if not self.base and not self.connect():
            raise ConnectionError("League client not running")
        req = urllib.request.Request(self.base + path, headers={"Authorization": self.auth})
        try:
            with urllib.request.urlopen(req, context=_INSECURE, timeout=5) as r:
                return r.read(), r.headers.get("Content-Type", "image/png")
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, OSError) as e:
            self.base = None
            raise ConnectionError(str(e))

    def accept(self):
        return self.request("POST", "/lol-matchmaking/v1/ready-check/accept")

    def decline(self):
        return self.request("POST", "/lol-matchmaking/v1/ready-check/decline")


# ---------------------------------------------------------------- notifications

class Notifier:
    def __init__(self, cfg, control_url):
        self.cfg = cfg
        self.control_url = control_url  # http://ip:port

    def send(self, title, message, priority=3, tags=None, actions=None):
        payload = {
            "topic": self.cfg["ntfy_topic"],
            "title": title,
            "message": message,
            "priority": priority,
            "tags": tags or [],
            "click": self.control_url,
        }
        if actions:
            payload["actions"] = actions
        threading.Thread(target=self._post, args=(payload,), daemon=True).start()

    def _post(self, payload):
        try:
            req = urllib.request.Request(
                self.cfg["ntfy_server"].rstrip("/"),
                data=json.dumps(payload).encode(),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            log(f"ntfy push failed: {e}")

    def match_found(self):
        self.send(
            "MATCH FOUND!",
            "Tap ACCEPT within ~10 seconds.",
            priority=5,
            tags=["rotating_light", "video_game"],
            actions=[
                {"action": "http", "label": "ACCEPT", "method": "POST", "clear": True,
                 "url": f"{self.control_url}/api/accept"},
                {"action": "http", "label": "DECLINE", "method": "POST", "clear": True,
                 "url": f"{self.control_url}/api/decline"},
            ],
        )


    def your_turn(self, kind, seconds, favorites):
        """kind: 'pick' or 'ban'. favorites: [(champ_id, name)] that are available now."""
        verb = "Lock" if kind == "pick" else "Ban"
        actions = [{"action": "view", "label": "Open", "url": self.control_url, "clear": True}]
        for cid, name in favorites[:2]:
            actions.append({"action": "http", "label": f"{verb} {name}", "method": "POST",
                            "clear": True, "url": f"{self.control_url}/api/cs/lock?champ={cid}"})
        left = f" - {seconds}s left" if seconds else ""
        self.send(f"YOUR TURN TO {kind.upper()}{left}",
                  "Open the page to choose, or tap a favorite.",
                  priority=5, tags=["rotating_light", "crossed_swords"], actions=actions)


# ---------------------------------------------------------------- watcher

class Watcher:
    def __init__(self, cfg, lcu, notifier):
        self.cfg = cfg
        self.lcu = lcu
        self.notifier = notifier
        self.lock = threading.Lock()
        self.status = {"connected": False, "phase": "Unknown"}
        self.last_phase = None
        self.last_event = ""
        self.notified_action = None
        self._champs = {}  # id -> name

    def snapshot(self):
        with self.lock:
            s = dict(self.status)
        s["auto_accept"] = self.cfg["auto_accept"]
        s["favorites"] = list(self.cfg.get("favorite_picks", [])) + list(self.cfg.get("favorite_bans", []))
        s["last_event"] = self.last_event
        return s

    def event(self, text):
        self.last_event = time.strftime("%H:%M:%S ") + text
        log(text)

    def run(self):
        while True:
            try:
                self.tick()
            except ConnectionError:
                with self.lock:
                    if self.status.get("connected"):
                        self.event("Lost connection to League client")
                    self.status = {"connected": False, "phase": "Client not running"}
                self.last_phase = None
                time.sleep(3)
                continue
            except Exception as e:
                log(f"watcher error: {e!r}")
            time.sleep(POLL_SECONDS)

    def tick(self):
        phase = self.lcu.request("GET", "/lol-gameflow/v1/gameflow-phase") or "None"
        st = {"connected": True, "phase": phase}

        if phase in ("Matchmaking", "ReadyCheck"):
            search = self.lcu.request("GET", "/lol-matchmaking/v1/search") or {}
            st["time_in_queue"] = search.get("timeInQueue")
            st["estimated"] = search.get("estimatedQueueTime")
        if phase == "ReadyCheck":
            rc = self.lcu.request("GET", "/lol-matchmaking/v1/ready-check") or {}
            st["ready_state"] = rc.get("state")
            st["my_response"] = rc.get("playerResponse")
            st["ready_timer"] = rc.get("timer")
        if phase == "ChampSelect":
            cs = self.champ_select_state()
            st["cs"] = cs
            st["cs_phase"] = cs.get("phase")
            st["cs_time_left"] = cs.get("time_left")
            self.maybe_notify_turn(cs)
        else:
            self.notified_action = None

        with self.lock:
            was_connected = self.status.get("connected")
            self.status = st
        if not was_connected:
            self.event("Connected to League client")

        if phase != self.last_phase:
            self.record_phase(phase)
            self.on_phase_change(self.last_phase, phase, st)
            self.last_phase = phase
        elif phase not in ("None", "Lobby", "Matchmaking", "InProgress"):
            self.record_changes(phase)

    # ------------------------------------------------ champion select

    def champions(self):
        """id -> name for every champion the client knows (incl. League Classic 600xx ids)."""
        if not self._champs:
            data = self.lcu.request("GET", "/lol-game-data/assets/v1/champion-summary.json") or []
            self._champs = {c["id"]: c["name"] for c in data if c.get("id", 0) > 0}
        return self._champs

    def champ_select_state(self):
        s = self.lcu.request("GET", "/lol-champ-select/v1/session") or {}
        me = s.get("localPlayerCellId")

        timer = s.get("timer") or {}
        left = timer.get("adjustedTimeLeftInPhase")
        if isinstance(left, (int, float)):
            # the value is relative to internalNowInEpochMs, not to "now"
            since = timer.get("internalNowInEpochMs")
            if isinstance(since, (int, float)) and since > 0:
                left -= max(0, time.time() * 1000 - since)
            left = max(0, round(left / 1000))
        else:
            left = None

        actions = [a for group in (s.get("actions") or []) for a in group]
        mine = [a for a in actions if a.get("actorCellId") == me and not a.get("completed")]
        current = next((a for a in mine if a.get("isInProgress")), None)
        target = current or (mine[0] if mine else None)
        locked_cells = {a.get("actorCellId") for a in actions
                        if a.get("type") == "pick" and a.get("completed")}

        def player(p):
            return {
                "cell": p.get("cellId"),
                "champ": p.get("championId") or p.get("championPickIntent") or 0,
                "locked": p.get("cellId") in locked_cells,
                "pos": (p.get("assignedPosition") or "").lower(),
                "name": p.get("gameName") or "",
                "me": p.get("cellId") == me,
            }

        choices = []
        if target:
            ep = "bannable" if target.get("type") == "ban" else "pickable"
            choices = self.lcu.request("GET", f"/lol-champ-select/v1/{ep}-champion-ids") or []

        return {
            "phase": timer.get("phase"),
            "time_left": left,
            "action": {
                "id": target.get("id"),
                "type": target.get("type"),
                "in_progress": bool(current),
                "champ": target.get("championId") or 0,
            } if target else None,
            "done": not mine and me in locked_cells,
            "team": [player(p) for p in s.get("myTeam") or []],
            "enemies": [p.get("championId") or 0 for p in s.get("theirTeam") or []],
            "bans": [a.get("championId") for a in actions
                     if a.get("type") == "ban" and a.get("completed") and a.get("championId")],
            "choices": choices,
        }

    def maybe_notify_turn(self, cs):
        act = cs.get("action")
        if not act or not act["in_progress"] or act["id"] == self.notified_action:
            return
        self.notified_action = act["id"]
        kind = "ban" if act["type"] == "ban" else "pick"
        self.event(f"Your turn to {kind}")
        if not self.cfg.get("notify_your_turn", True):
            return
        champs = self.champions()
        by_name = {n.lower(): i for i, n in champs.items() if i in set(cs.get("choices") or [])}
        wanted = self.cfg.get("favorite_bans" if kind == "ban" else "favorite_picks") or []
        favs = [(by_name[n.lower()], champs[by_name[n.lower()]])
                for n in map(str, wanted) if n.lower() in by_name]
        self.notifier.your_turn(kind, cs.get("time_left"), favs)

    def cs_act(self, champ_id, lock):
        """Hover (lock=False) or lock in / ban (lock=True) a champion for my current action."""
        cs = self.champ_select_state()
        act = cs.get("action")
        if not act:
            raise ValueError("You have no pick or ban left")
        if lock and not act["in_progress"]:
            raise ValueError("It's not your turn yet")
        champ_id = champ_id or act["champ"]
        if not champ_id:
            raise ValueError("Choose a champion first")
        if champ_id not in (cs.get("choices") or []):
            raise ValueError("That champion isn't available")
        path = f"/lol-champ-select/v1/session/actions/{act['id']}"
        self.lcu.request("PATCH", path, {"championId": champ_id})
        name = self.champions().get(champ_id, champ_id)
        if lock:
            self.lcu.request("POST", path + "/complete")
            self.event(f"{'Banned' if act['type'] == 'ban' else 'Locked in'} {name} from phone")
        else:
            self.event(f"Hovering {name}")

    CAPTURE_ENDPOINTS = [
        "/lol-gameflow/v1/session",
        "/lol-champ-select/v1/session",
        "/lol-champ-select/v1/pickable-champion-ids",
        "/lol-champ-select/v1/bannable-champion-ids",
        "/lol-lobby-team-builder/champ-select/v1/session",
    ]

    def _snapshot_endpoints(self):
        snap = {}
        for ep in self.CAPTURE_ENDPOINTS:
            try:
                snap[ep] = self.lcu.request("GET", ep)
            except urllib.error.HTTPError as e:
                snap[ep] = f"HTTP {e.code}"
        return snap

    def record_phase(self, phase):
        snap = self._snapshot_endpoints()
        self._last_snap = json.dumps(snap, sort_keys=True)
        capture(f"phase-{phase}", snap)

    def record_changes(self, phase):
        # During unusual phases (ReadyCheck, ChampSelect, ...) save whenever data changes
        now = time.time()
        if now - getattr(self, "_last_rec", 0) < 1:
            return
        self._last_rec = now
        snap = self._snapshot_endpoints()
        dumped = json.dumps(snap, sort_keys=True)
        if dumped != getattr(self, "_last_snap", None):
            self._last_snap = dumped
            capture(f"update-{phase}", snap)

    def on_phase_change(self, old, new, st):
        if new == "ReadyCheck":
            if self.cfg["auto_accept"]:
                self.lcu.accept()
                self.event("Match found - auto-accepted")
                self.notifier.send("Match accepted automatically",
                                   "Champ select is coming - head back!",
                                   priority=5, tags=["white_check_mark", "video_game"])
            else:
                self.event("Match found - waiting for your answer")
                self.notifier.match_found()
        elif old == "ReadyCheck" and new == "Matchmaking":
            self.event("Ready check failed - back in queue")
            if self.cfg["notify_requeue"]:
                self.notifier.send("Back in queue", "Someone didn't accept. Still searching.",
                                   priority=2, tags=["hourglass"])
        elif old == "ReadyCheck" and new in ("None", "Lobby"):
            self.event("Ready check ended - left queue")
            self.notifier.send("Out of queue", "You (or the party) declined / missed the match.",
                               priority=3, tags=["x"])
        elif new == "ChampSelect":
            self.event("Champ select started")
            # skip if a "your turn" alert already went out for this champ select
            if self.cfg["notify_champ_select"] and self.notified_action is None:
                left = st.get("cs_time_left")
                msg = f"~{left}s left in this phase. Get back!" if left else "Get back to your PC!"
                self.notifier.send("CHAMP SELECT STARTED", msg, priority=5,
                                   tags=["runner", "video_game"])
        elif new == "Matchmaking" and old != "ReadyCheck":
            self.event("Entered queue")


# ---------------------------------------------------------------- web server

def make_handler(cfg, lcu, watcher):
    icon_cache = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _icon(self, cid):
            if not cid.isdigit():
                return self._json(404, {"error": "bad id"})
            if cid not in icon_cache:
                try:
                    icon_cache[cid] = lcu.raw(f"/lol-game-data/assets/v1/champion-icons/{cid}.png")
                except (ConnectionError, urllib.error.HTTPError):
                    return self._json(404, {"error": "no icon"})
            body, ctype = icon_cache[cid]
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "max-age=86400")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            if url.path == "/":
                with open(PAGE_PATH, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif url.path == "/api/status":
                self._json(200, watcher.snapshot())
            elif url.path == "/api/champs":
                try:
                    self._json(200, [{"id": i, "name": n} for i, n in watcher.champions().items()])
                except ConnectionError as e:
                    self._json(503, {"error": str(e)})
            elif url.path.startswith("/icon/"):
                self._icon(url.path.rsplit("/", 1)[-1])
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):
            url = urlparse(self.path)
            q = parse_qs(url.query)
            try:
                if url.path == "/api/accept":
                    lcu.accept()
                    watcher.event("Accepted from phone")
                elif url.path == "/api/decline":
                    lcu.decline()
                    watcher.event("Declined from phone")
                elif url.path in ("/api/cs/hover", "/api/cs/lock"):
                    champ = q.get("champ", [""])[0]
                    try:
                        watcher.cs_act(int(champ) if champ.isdigit() else 0,
                                       lock=url.path.endswith("lock"))
                    except ValueError as e:
                        watcher.event(f"Phone: {e}")
                        return self._json(409, {"error": str(e)})
                elif url.path == "/api/auto":
                    on = q.get("on", [""])[0]
                    cfg["auto_accept"] = (on == "1") if on else not cfg["auto_accept"]
                    save_config(cfg)
                    watcher.event(f"Auto-accept {'ON' if cfg['auto_accept'] else 'OFF'}")
                    # Match already popped? act on it now
                    if cfg["auto_accept"] and watcher.snapshot().get("phase") == "ReadyCheck":
                        lcu.accept()
                        watcher.event("Accepted (auto-accept switched on during ready check)")
                else:
                    return self._json(404, {"error": "not found"})
            except ConnectionError as e:
                return self._json(503, {"error": str(e)})
            except urllib.error.HTTPError as e:
                if url.path.startswith("/api/cs/"):
                    watcher.event(f"Client refused the champion select action ({e.code})")
                    return self._json(409, {"error": f"client refused ({e.code})"})
                watcher.event(f"Phone tapped {url.path.rsplit('/', 1)[-1].upper()} - no match to answer ({e.code})")
                return self._json(409, {"error": f"client refused ({e.code}) - no active ready check?"})
            self._json(200, watcher.snapshot())

    return Handler


# ---------------------------------------------------------------- main

def main():
    cfg = load_config()
    ip = lan_ip()
    control_url = f"http://{ip}:{cfg['port']}"

    lcu = LCU(cfg.get("lockfile", ""))
    notifier = Notifier(cfg, control_url)
    watcher = Watcher(cfg, lcu, notifier)

    # On Windows, SO_REUSEADDR lets a second copy silently share the port; refuse instead.
    ThreadingHTTPServer.allow_reuse_address = False
    try:
        server = ThreadingHTTPServer(("0.0.0.0", cfg["port"]), make_handler(cfg, lcu, watcher))
    except OSError:
        print(f"Port {cfg['port']} is already in use - is League Remote already running? Close it first.")
        return
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print("=" * 64)
    print(" League Remote Accept is running")
    print("=" * 64)
    print(f" Phone control page : {control_url}")
    print(f" ntfy topic         : {cfg['ntfy_topic']}")
    print(f"   -> install the 'ntfy' app on your phone and subscribe to it")
    print(f" Auto-accept        : {'ON' if cfg['auto_accept'] else 'OFF'}")
    print(" Phone must be on the same Wi-Fi as this PC. Ctrl+C to quit.")
    print("=" * 64)

    if "--test" in sys.argv:
        log("Sending a test MATCH FOUND notification to your phone...")
        notifier.match_found()

    if not lcu.connect():
        log("League client not found yet - will keep checking...")

    try:
        watcher.run()
    except KeyboardInterrupt:
        print("\nBye!")


if __name__ == "__main__":
    main()
