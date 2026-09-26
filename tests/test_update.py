"""Update check + one-click update against a fake GitHub on 127.0.0.1 (nothing is installed).

Run: python tests/test_update.py
"""
import hashlib
import json
import os
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["LEAGUE_REMOTE_DATA"] = tempfile.mkdtemp()
import update

failed = False


def check(cond, msg):
    global failed
    print(("PASS " if cond else "FAIL ") + msg)
    failed |= not cond


INSTALLER = os.urandom(300_000)  # pretend installer
STATE = {"tag": "v9.9.9", "body": INSTALLER, "sha": hashlib.sha256(INSTALLER).hexdigest(), "size": len(INSTALLER)}


class FakeGitHub(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/api":
            body = json.dumps({"tag_name": STATE["tag"], "html_url": "https://example/release",
                               "assets": [{"name": "notes.txt"},
                                          {"name": f"LeagueRemote-Setup-{STATE['tag'][1:]}.exe",
                                           "browser_download_url": f"http://127.0.0.1:{PORT}/installer",
                                           "size": STATE["size"], "digest": f"sha256:{STATE['sha']}"}]}).encode()
        elif self.path == "/installer":
            body = STATE["body"]
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitHub)
PORT = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
API = f"http://127.0.0.1:{PORT}/api"

launched = []


def fake_launcher(path, args):
    launched.append((path, args, open(path, "rb").read()))
    return True


def wait_state(u, states, seconds=10):
    end = time.time() + seconds
    while time.time() < end and u.state not in states:
        time.sleep(0.05)
    return u.state


# ------------------------------------------------------------ check
seen = []
u = update.UpdateChecker("2.0.2", on_new=seen.append, api_url=API, launcher=fake_launcher)
found = u.check()
check(found["version"] == "9.9.9" and found["installer"].endswith("/installer"), "finds the newer release and its installer")
check(found["sha256"] == STATE["sha"] and found["size"] == STATE["size"], "reads GitHub's SHA-256 and size")
check(len(seen) == 1, "notifies once")
u.check()
check(len(seen) == 1, "no repeat notification for the same version")
check(update.UpdateChecker("9.9.9", api_url=API).check() is None, "no update when already on the latest")
check(update.UpdateChecker("10.0.0", api_url=API).check() is None, "no 'update' to an older version")

# ------------------------------------------------------------ one-click update
check(u.update_now(lambda m: None), "update starts")
check(u.update_now(lambda m: None) is False, "second click while busy is ignored")
check(wait_state(u, ("installing", "error")) == "installing" and u.progress == 100, "downloads to 100% and installs")
check(len(launched) == 1 and launched[0][2] == INSTALLER, "runs exactly the downloaded, verified installer")
check("/SILENT" in launched[0][1] and "/SUPPRESSMSGBOXES" in launched[0][1], "installs silently (no wizard)")
check(launched[0][0].endswith("LeagueRemote-Setup-9.9.9.exe"), "installer saved under its real name")

# corrupted download -> never run
STATE["body"] = INSTALLER[:-1] + bytes([INSTALLER[-1] ^ 1])  # same size, different bytes
u2 = update.UpdateChecker("2.0.2", api_url=API, launcher=fake_launcher)
u2.check()
launched.clear()
u2.update_now(lambda m: None)
check(wait_state(u2, ("installing", "error")) == "error" and "SHA-256" in u2.message and not launched,
      "tampered/corrupted installer is rejected and never run")

# truncated download -> never run
STATE["body"] = INSTALLER[:1000]
u3 = update.UpdateChecker("2.0.2", api_url=API, launcher=fake_launcher)
u3.check()
u3.update_now(lambda m: None)
check(wait_state(u3, ("installing", "error")) == "error" and "incomplete" in u3.message and not launched,
      "incomplete download is rejected")

# you click "No" on the Windows prompt
STATE["body"] = INSTALLER
u4 = update.UpdateChecker("2.0.2", api_url=API, launcher=lambda p, a: False)
u4.check()
u4.update_now(lambda m: None)
check(wait_state(u4, ("installing", "error")) == "error" and "cancelled" in u4.message, "declined permission -> clear message")
check(u4.update_now(lambda m: None), "can retry after an error")

# status for the page / tray
st = u.status()
check(st["version"] == "9.9.9" and st["state"] == "installing" and "progress" in st, "status has version, state, progress")
check(update.UpdateChecker("2.0.2", api_url=API).status() is None, "no status before an update is found")
u5 = update.UpdateChecker("9.9.9", api_url=API)
check(u5.update_now(lambda m: None) is False and "latest" in u5.message and u5.state == "idle",
      "'Update now' with no update says you're up to date (not an error)")

srv.shutdown()
print("\nALL PASSED" if not failed else "\nSOME FAILED")
sys.exit(1 if failed else 0)
