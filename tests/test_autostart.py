"""Single instance + Start with Windows, tested for real (Windows only).

Runs League Remote copies in a temporary folder on port 5099, so a League Remote
you have running on your normal port is never touched.
Run: python tests/test_autostart.py
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
import autostart

PORT = 5099
failed = False


def check(cond, msg):
    global failed
    print(("PASS " if cond else "FAIL ") + msg)
    failed |= not cond


def make_copy():
    d = tempfile.mkdtemp(prefix="lr-test-")
    for f in ("league_remote.py", "ingame.py", "rank.py", "autostart.py", "phone.html"):
        shutil.copy(os.path.join(REPO, f), d)
    with open(os.path.join(d, "config.json"), "w") as f:
        json.dump({"port": PORT, "auto_accept": False, "ntfy_server": "http://127.0.0.1:9", "ntfy_topic": "test",
                   "notify_champ_select": False, "notify_requeue": False, "notify_your_turn": False,
                   "notify_game": False}, f)
    return d


def start(d, *args):
    log = open(os.path.join(d, f"out-{time.time_ns()}.txt"), "w")
    p = subprocess.Popen([sys.executable, os.path.join(d, "league_remote.py"), *args], cwd=d,
                         stdout=log, stderr=subprocess.STDOUT, creationflags=autostart.NO_WINDOW)
    p.log_path = log.name
    return p


def serving():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/api/status", timeout=1) as r:
            return json.loads(r.read())
    except Exception:
        return None


def output(p):
    with open(p.log_path, encoding="utf-8", errors="replace") as f:
        return f.read()


if autostart.port_in_use(PORT):
    print(f"Port {PORT} is busy - free it before running this test")
    sys.exit(1)

d = make_copy()
procs = []
try:
    # 1. a second copy replaces the first (graceful /api/shutdown)
    a = start(d); procs.append(a)
    check(autostart.wait_for(lambda: serving() is not None, 20), "first copy starts and serves the page")
    b = start(d); procs.append(b)
    check(autostart.wait_for(lambda: a.poll() is not None, 25), "starting a second copy stops the first")
    check(autostart.wait_for(lambda: serving() is not None, 20), "second copy takes over the port")
    check(autostart.read_pid(os.path.join(d, "league_remote.pid")) == b.pid, "PID file points at the new copy")
    check("this one is stopping" in output(a), "old copy shut down cleanly (not killed)")
    check("replacing it with this one" in output(b), "new copy says it replaced the old one")

    # 2. --stop
    s = start(d, "--stop"); procs.append(s)
    s.wait(30)
    check(autostart.wait_for(lambda: b.poll() is not None and serving() is None, 15), "--stop stops the running copy")

    # 3. an old version without /api/shutdown is force-stopped
    old = tempfile.mkdtemp(prefix="lr-old-")
    with open(os.path.join(old, "league_remote.py"), "w") as f:
        f.write("import http.server\nhttp.server.ThreadingHTTPServer(('0.0.0.0', %d), "
                "http.server.SimpleHTTPRequestHandler).serve_forever()\n" % PORT)
    o = subprocess.Popen([sys.executable, os.path.join(old, "league_remote.py")], cwd=old,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=autostart.NO_WINDOW)
    procs.append(o)
    autostart.wait_for(lambda: autostart.port_in_use(PORT), 10)
    c = start(d); procs.append(c)
    check(autostart.wait_for(lambda: o.poll() is not None, 25), "old version without /api/shutdown is force-stopped")
    check(autostart.wait_for(lambda: serving() is not None, 20), "new copy starts after force-stop")
    c.terminate(); c.wait(10)
    autostart.wait_for(lambda: not autostart.port_in_use(PORT), 10)

    # 4. some other program on the port is left alone
    other = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT), "--bind", "127.0.0.1"],
                             cwd=tempfile.mkdtemp(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=autostart.NO_WINDOW)
    procs.append(other)
    autostart.wait_for(lambda: autostart.port_in_use(PORT), 10)
    e = start(d); procs.append(e)
    e.wait(30)
    check(other.poll() is None, "another program on the port is NOT stopped")
    check("used by another program" in output(e), "League Remote explains the port conflict and exits")
    other.terminate(); other.wait(10)

    # 5. Start with Windows shortcut (in a temp folder, not your real Startup folder)
    autostart.SHORTCUT = os.path.join(tempfile.mkdtemp(), "League Remote.lnk")
    check(autostart.install_startup(os.path.join(REPO, "league_remote.py")) and autostart.startup_installed(),
          "startup shortcut created")
    info = autostart.powershell(f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{autostart.SHORTCUT}'); "
                                "$s.TargetPath + '|' + $s.Arguments + '|' + $s.WorkingDirectory")
    target, arguments, workdir = info.split("|")
    check(target.lower().endswith("pythonw.exe"), f"runs hidden with pythonw ({target})")
    check("league_remote.py" in arguments and "--background" in arguments, f"arguments: {arguments}")
    check(os.path.samefile(workdir, REPO), "working directory is the project folder")
    check(autostart.uninstall_startup() and not autostart.startup_installed(), "startup shortcut removed")
finally:
    for p in procs:
        if p.poll() is None:
            p.kill()

print("\nALL PASSED" if not failed else "\nSOME FAILED")
sys.exit(1 if failed else 0)
