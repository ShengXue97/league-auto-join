"""Write the GitHub release text for a version: its CHANGELOG entry + install steps.

The app shows the bullets under "## New in ..." on the phone's update card.
Run: python tools/release_notes.py 2.3.1 > notes.md
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INSTALL = """## Install
1. Download **LeagueRemote-Setup-{v}.exe** below and run it.
2. Windows may say *"Windows protected your PC"* (the app isn't code-signed): click **More info → Run anyway**.
3. When it's done, the **phone setup** page opens. Scan the first QR code with your phone: it walks you through getting alerts in the free **ntfy** app, testing them, and opening League Remote.
4. League Remote runs in the **notification area** as a **gold bell** near the clock (click **^** if you don't see it). Right-click it for the control page, phone setup, updates, Start with Windows and Quit.

Your phone must be on the same Wi-Fi as your PC. If Windows treats your home Wi-Fi as *Public*, the setup page shows how to switch it to *Private* (or tick the installer's "Public networks" box).

Already installed? Right-click the tray bell → **Update now**.

---
League Remote isn't endorsed by Riot Games and doesn't reflect the views or opinions of Riot Games or anyone officially involved in producing or managing Riot Games properties. Riot Games, and all associated properties are trademarks or registered trademarks of Riot Games, Inc.
"""


def changes(version):
    """Bullets of the version's CHANGELOG entry, each joined onto one line."""
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        text = f.read()
    m = re.search(rf"^## \[{re.escape(version)}\].*?$(.*?)(?=^## \[|\Z)", text, re.M | re.S)
    if not m:
        sys.exit(f"CHANGELOG.md has no entry for {version}")
    bullets = []
    for line in m.group(1).splitlines():
        if line.startswith("- "):
            bullets.append(line[2:].strip())
        elif line.startswith("  ") and bullets:
            bullets[-1] += " " + line.strip()
    return bullets


def main():
    v = sys.argv[1].lstrip("vV")
    body = "Your League of Legends queue, champ select and game on your phone.\n\n"
    body += f"## New in {v}\n" + "".join(f"- {b}\n" for b in changes(v)) + "\n"
    sys.stdout.reconfigure(encoding="utf-8")
    print(body + INSTALL.format(v=v), end="")


if __name__ == "__main__":
    main()
