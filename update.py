"""Checks GitHub for a newer League Remote release (every few hours, read-only)."""

import json
import re
import threading
import time
import urllib.request

REPO = "league-remote-team/league-remote"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_EVERY = 6 * 3600


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", str(v))[:3]) or (0,)


class UpdateChecker:
    def __init__(self, current, on_new=None):
        self.current = current
        self.on_new = on_new  # called once when a newer version is found
        self.latest = None    # {"version", "url"} when an update is available

    def check(self):
        req = urllib.request.Request(API_URL, headers={"User-Agent": f"LeagueRemote/{self.current}",
                                                       "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        tag = data.get("tag_name") or ""
        if data.get("draft") or data.get("prerelease") or version_tuple(tag) <= version_tuple(self.current):
            return None
        found = {"version": tag.lstrip("vV"), "url": data.get("html_url") or RELEASES_URL}
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
