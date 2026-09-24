# League Remote Accept

Get a phone notification with **ACCEPT / DECLINE** buttons when your League match pops.

## Setup (once)
1. Install the **ntfy** app on your phone (Play Store / App Store).
2. In the app, tap **+** and subscribe to the topic printed at startup (`ntfy_topic` in `config.json`).
3. Double-click `start.bat`. When Windows Firewall asks, allow **Private networks**.
4. Optional: open the printed "Phone control page" link on your phone and add it to your home screen.

Check the setup: `python league_remote.py --test` sends a fake MATCH FOUND notification.

## Notifications
| When | Notification |
|---|---|
| Match found | Loud alert with ACCEPT / DECLINE buttons (~10s to tap) |
| Match found + auto-accept ON | "Accepted automatically, head back" |
| Someone else declined | Quiet "Back in queue" |
| Champ select starts | Loud "Get back!" with seconds left |
| Your turn to pick / ban | Loud alert + up to 2 one-tap favorite buttons |
| Favorite banned / taken | Alert suggesting your next available favorite |
| Swap request from a teammate | ACCEPT / DECLINE + whether you'd pick earlier or later |
| Your swap request answered | Accepted (new pick #) or declined |

## Champion select from your phone
Open the control page during champ select to see your team, bans and timer,
search the champion grid, and **LOCK IN** or **BAN** yourself. Tapping a
champion hovers it so teammates see your choice. Works with League Classic
champions.

**Pick order swaps:** your team is listed in pick order. Players who pick before
you get a **Swap** button (the earliest is highlighted), and incoming requests show
whether accepting gives you an earlier or later pick.

**My champions:** add your mains on the phone page in priority order. In champ
select you'll see each one's status (available / banned / taken), your top
available one is pre-selected so LOCK IN is one tap, and you're alerted if one
gets banned or taken.

Nothing is ever picked, banned or swapped automatically - every action is your own tap.

Optional favorites in `config.json` (shown first in the grid, and as buttons
in the "your turn" notification when available):
```json
"favorite_picks": ["Ahri", "Annie"],
"favorite_bans": ["Karthus"]
```

## Notes
- Your phone must be on the same Wi-Fi as the PC for the buttons to work.
- `config.json` settings: `auto_accept`, `notify_champ_select`, `notify_your_turn`, `notify_requeue`, `favorite_picks`, `favorite_bans`, `port`.
- Tests: `python tests/test_champ_select.py` (simulated champ select, no client needed).
- If you miss champ select you dodge (queue lockout, and LP loss in ranked), so only turn on auto-accept if you'll be back in time.

## Versions
The version is shown in the startup window and at the bottom of the phone page.
See `CHANGELOG.md` for what changed. Releases are tagged in git (`git tag` lists them).

To release: bump `__version__` in `league_remote.py`, add a `CHANGELOG.md` entry,
commit, then `git tag -a vX.Y.Z -m "..."`.
