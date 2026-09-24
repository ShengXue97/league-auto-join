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

## Notes
- Your phone must be on the same Wi-Fi as the PC for the buttons to work.
- `config.json` settings: `auto_accept`, `notify_champ_select`, `notify_requeue`, `port`.
- If you miss champ select you dodge (queue lockout, and LP loss in ranked), so only turn on auto-accept if you'll be back in time.
