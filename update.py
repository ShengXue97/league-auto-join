"""Checks GitHub for a newer League Remote release, and installs it on request.

Checking is read-only (every few hours). Updating only happens when you click
"Update now": the new installer is downloaded, verified (size + GitHub's SHA-256),
and run silently. Windows asks once for permission (the app lives in Program Files).
"""

import hashlib
import json
import os
import re
import tempfile
import threading
import time
import urllib.request

REPO = "league-remote-team/league-remote"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_EVERY = 6 * 3600
INSTALLER = re.compile(r"^LeagueRemote-Setup-[\d.]+\.exe$", re.I)
# Inno Setup: no wizard (progress bar only), no questions, keep previous choices
SILENT_ARGS = "/SILENT /SUPPRESSMSGBOXES /NORESTART /SP-"


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


def _get_json(url, current):
    req = urllib.request.Request(url, headers={"User-Agent": f"LeagueRemote/{current}",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def run_elevated(path, args):
    """Start a program with admin rights (Windows shows its permission prompt). Returns True if started."""
    import ctypes
    rc = ctypes.windll.shell32.ShellExecuteW(None, "runas", path, args, None, 1)
    return rc > 32  # <= 32 means it didn't start (e.g. you clicked No)


class UpdateChecker:
    def __init__(self, current, on_new=None, api_url=API_URL, launcher=run_elevated):
        self.current = current
        self.on_new = on_new    # called once when a newer version is found
        self.api_url = api_url
        self.launcher = launcher
        self.latest = None      # {"version", "url", "installer", "size", "sha256"} when an update exists
        self.state = "idle"     # idle | downloading | installing | error
        self.progress = 0       # download %
        self.message = ""
        self._lock = threading.Lock()

    def check(self):
        data = _get_json(self.api_url, self.current)
        tag = data.get("tag_name") or ""
        if data.get("draft") or data.get("prerelease") or version_tuple(tag) <= version_tuple(self.current):
            return None
        asset = next((a for a in data.get("assets") or [] if INSTALLER.match(a.get("name") or "")), None)
        digest = (asset or {}).get("digest") or ""
        found = {
            "version": tag.lstrip("vV"),
            "url": data.get("html_url") or RELEASES_URL,
            "installer": (asset or {}).get("browser_download_url"),
            "size": (asset or {}).get("size"),
            "sha256": digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") else None,
        }
        new = self.latest is None or self.latest["version"] != found["version"]
        self.latest = found
        if new and self.on_new:
            self.on_new(found)
        return found

    def start(self):
        def loop():
            time.sleep(20)  # let the app start first
            while True:
                try:
                    self.check()
                except Exception:
                    pass  # offline, rate-limited, or no releases yet
                time.sleep(CHECK_EVERY)
        threading.Thread(target=loop, daemon=True).start()

    def status(self):
        if not self.latest:
            return None
        return {**self.latest, "state": self.state, "progress": self.progress, "message": self.message}

    # ------------------------------------------------------------ one-click update

    def update_now(self, log=print):
        """Download + verify + run the installer in the background. Returns False if already busy."""
        with self._lock:
            if self.state in ("downloading", "installing"):
                return False
            if not self.latest:
                self.message = "You're already on the latest version"
                return False
            if not self.latest.get("installer"):
                self.state, self.message = "error", "No installer found in the latest release"
                return False
            self.state, self.progress, self.message = "downloading", 0, "Downloading…"
        threading.Thread(target=self._do_update, args=(log,), daemon=True).start()
        return True

    def _do_update(self, log):
        info = self.latest
        path = os.path.join(tempfile.gettempdir(), f"LeagueRemote-Setup-{info['version']}.exe")
        try:
            self._download(info, path)
            self.state, self.message = "installing", "Installing… approve the Windows prompt on your PC"
            log(f"Installing League Remote v{info['version']}")
            if not self.launcher(path, SILENT_ARGS):
                raise RuntimeError("The update was cancelled (Windows permission not given)")
            # The installer stops this app, updates it and starts the new version.
        except Exception as e:
            self.state, self.message = "error", str(e)
            log(f"Update failed: {e}")

    def _download(self, info, path):
        req = urllib.request.Request(info["installer"], headers={"User-Agent": f"LeagueRemote/{self.current}"})
        sha = hashlib.sha256()
        done = 0
        with urllib.request.urlopen(req, timeout=60) as r, open(path, "wb") as f:
            total = info.get("size") or int(r.headers.get("Content-Length") or 0)
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                sha.update(chunk)
                done += len(chunk)
                if total:
                    self.progress = min(100, round(100 * done / total))
        if info.get("size") and done != info["size"]:
            raise RuntimeError(f"Download incomplete ({done} of {info['size']} bytes)")
        if info.get("sha256") and sha.hexdigest() != info["sha256"]:
            os.remove(path)
            raise RuntimeError("Download check failed (SHA-256 doesn't match GitHub's) - not installed")
        self.progress = 100
