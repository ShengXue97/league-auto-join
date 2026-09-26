"""
Start with Windows, and "only one League Remote at a time".

Opening League Remote while another copy is running means "restart with my latest
changes": the new copy asks the old one to stop (POST /api/shutdown, localhost only),
force-stops it if it doesn't, and takes over. Only processes that are actually
League Remote are ever stopped - found by the port it listens on, or its PID file.
"""

import ctypes
import os
import socket
import subprocess
import sys
import time
import urllib.request

NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW: no console flashes when running hidden
STARTUP_DIR = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs", "Startup")
SHORTCUT = os.path.join(STARTUP_DIR, "League Remote.lnk")


def powershell(cmd, timeout=20):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                           capture_output=True, text=True, timeout=timeout, creationflags=NO_WINDOW)
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


# ------------------------------------------------------------------ start with Windows

def pythonw():
    """pythonw.exe runs without a console window."""
    p = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return p if os.path.exists(p) else sys.executable


def startup_installed():
    return os.path.exists(SHORTCUT)


def launch_command(script=None):
    """(program, arguments, folder) that start League Remote hidden."""
    if getattr(sys, "frozen", False):  # packaged LeagueRemote.exe (has no console anyway)
        exe = sys.executable
        return exe, "--background", os.path.dirname(exe)
    script = os.path.abspath(script or os.path.join(os.path.dirname(os.path.abspath(__file__)), "league_remote.py"))
    return pythonw(), f'"{script}" --background', os.path.dirname(script)


def install_startup(script=None):
    q = lambda s: s.replace("'", "''")  # PowerShell single-quote escaping
    target, arguments, folder = launch_command(script)
    icon = target if getattr(sys, "frozen", False) else os.path.join(folder, "assets", "icon.ico")
    powershell(
        f"$s = (New-Object -ComObject WScript.Shell).CreateShortcut('{q(SHORTCUT)}'); "
        f"$s.TargetPath = '{q(target)}'; "
        f"$s.Arguments = '{q(arguments)}'; "
        f"$s.WorkingDirectory = '{q(folder)}'; "
        f"$s.IconLocation = '{q(icon)}'; "
        f"$s.Description = 'League Remote - match alerts for League of Legends'; "
        f"$s.Save()")
    return startup_installed()


def uninstall_startup():
    try:
        os.remove(SHORTCUT)
    except FileNotFoundError:
        pass
    return not startup_installed()


# ------------------------------------------------------------------ single instance

def alive(pid):
    """Is this process still running? (Windows API - no console, no side effects.)"""
    k32 = ctypes.windll.kernel32
    h = k32.OpenProcess(0x1000, False, int(pid))  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    ok = k32.GetExitCodeProcess(h, ctypes.byref(code))
    k32.CloseHandle(h)
    return bool(ok) and code.value == 259  # STILL_ACTIVE


def command_line(pid):
    return powershell(f"(Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}').CommandLine")


def port_in_use(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", int(port))) == 0


def port_owner(port):
    out = powershell(f"(Get-NetTCPConnection -LocalPort {int(port)} -State Listen -ErrorAction SilentlyContinue"
                     f" | Select-Object -First 1).OwningProcess")
    return int(out) if out.isdigit() else None


def is_league_remote(pid):
    cmd = (command_line(pid) or "").lower()
    return pid and pid != os.getpid() and ("league_remote.py" in cmd or "leagueremote.exe" in cmd)


def answers_as_league_remote(port):
    """Ask whatever listens on the port. Needed when its command line can't be read,
    e.g. a copy started with admin rights by the installer."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2) as r:  # the control page
            return b"<title>League Remote" in r.read(8192)
    except Exception:
        return False


def read_pid(pid_file):
    try:
        with open(pid_file, encoding="utf-8") as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return None


def wait_for(cond, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.2)
    return cond()


def takeover(port, pid_file, log=print):
    """Stop any running League Remote so this copy can start.
    Returns an error message if the port belongs to some other program, else None."""
    targets = set()
    pid = read_pid(pid_file)
    if pid and alive(pid) and is_league_remote(pid):
        targets.add(pid)
    if port_in_use(port):
        owner = port_owner(port)
        if owner and owner != os.getpid() and (is_league_remote(owner) or answers_as_league_remote(port)):
            targets.add(owner)
        elif owner:
            return (f"Port {port} is used by another program (PID {owner}). "
                    f"Close it or change \"port\" in config.json.")
    if not targets:
        return None

    log(f"League Remote is already running (PID {', '.join(map(str, sorted(targets)))}) - replacing it with this one")
    try:  # ask nicely first
        urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}/api/shutdown", method="POST"),
                               timeout=2).read()
    except Exception:
        pass  # older versions have no /api/shutdown
    if not wait_for(lambda: not any(alive(p) for p in targets), 4):
        for p in targets:
            if alive(p):
                subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True, creationflags=NO_WINDOW)
    if not wait_for(lambda: not port_in_use(port), 6):
        return f"Couldn't stop the running League Remote on port {port}."
    log("Previous League Remote stopped")
    return None


def write_pid(pid_file):
    with open(pid_file, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
