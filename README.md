# League Remote Accept

Get a phone notification with **ACCEPT / DECLINE** buttons when your League match pops.

## Setup (once)
1. Install the **ntfy** app on your phone (Play Store / App Store).
2. In the app, tap **+** and subscribe to the topic printed at startup (`ntfy_topic` in `config.json`).
3. Double-click `start.bat`. When Windows Firewall asks, allow **Private networks**.
4. Optional: open the printed "Phone control page" link on your phone and add it to your home screen.

Check the setup: `python league_remote.py --test` sends a fake MATCH FOUND notification.

## Start with Windows
League Remote can start hidden when you log in (toggle "Start with Windows" on the
phone page, or `python league_remote.py --install-startup`). It waits for the League
client, so SP tracking never misses a game. Its output goes to `league_remote.log`.

**Restarting:** just open League Remote again (`start.bat`). The new copy replaces
the running one, hidden or not. `stop.bat` stops it.

## Notifications
| When | Notification |
|---|---|
| Match found | Loud alert with ACCEPT / DECLINE buttons (~10s to tap) |
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

## In game
The **Live** tab becomes a second screen while you play: your KDA, CS/min against
your goal (`cs_goal` in `config.json`, default 7.0), kill participation, vision,
gold, items and respawn timer, plus a Tab-style scoreboard and kill feed.
After each game you get an alert like "VICTORY +21 SP - now Platinum I 43 SP".

## Rank (Summoner's Journey)
The **Stats** tab starts with your Classic rank: emblem, division, SP, season
record and league standing, plus what your next win or loss is worth.

The **climb forecast** shows how many games (and at least how many wins) you
need for the next division, each emblem and Legend. Drag the win-rate slider,
or tap recent form / season / your main champion, to see how it changes.

Riot only stores your *current* SP, not what each game gave, so League Remote
records every change while it runs (`rank_history.jsonl`) and learns your real
SP per win and loss. Nothing SP-based is guessed: win/loss SP and the forecast
appear after your first tracked win and loss (marked rough until 3 of each).

**Aegis of Valor:** if you're autofilled into your #3, #4 or #5 role, a win can
give +40%, +70% or +100% SP (occasional, and lost if you swap roles). Champ
select shows when it's possible, and those wins are tracked separately so they
don't inflate your normal SP per win.

Match stats (win rate, champions, CS/min trend, recent games) come from Riot's
official match history in the client (last ~100 games, Classic only).

Works on phone, tablet and desktop browsers.

## Safety (why this won't get you banned)
- Reads only Riot's official **Live Client Data API** (served by the game at
  `127.0.0.1:2999` for third-party apps) and the League client's own API.
- Never reads game memory, injects into the game, draws over it, or sends
  keyboard/mouse input - the things Vanguard looks for.
- Shows nothing you can't already see in game: no enemy cooldown, ultimate,
  summoner spell, jungle or respawn timers, no enemy gold estimates.
  `tests/test_ingame.py` checks this.
- Never acts on its own: accepting, picking, banning, swapping and reconnecting are
  always your own tap. Riot's Terms of Service (7.1) forbid "automation programs",
  and Riot support names "taking actions on your behalf" - so there is no auto-accept.
- Never shows teammates' names in champ select (Riot hides them in ranked champ
  select to prevent dodging; apps must not reveal them) - teammates show as roles.
- Not registered with Riot as an app. Riot's developer policy asks apps using the
  League client API to register; tools like this are widely used without bans, but
  that can't be guaranteed.

## Notes
- Your phone must be on the same Wi-Fi as the PC for the buttons to work.
- `config.json` settings: `notify_champ_select`, `notify_your_turn`, `notify_requeue`, `favorite_picks`, `favorite_bans`, `notify_game`, `cs_goal`, `port`.
- Tests: `python tests/test_champ_select.py`, `python tests/test_ingame.py`, `python tests/test_rank.py` and `python tests/test_autostart.py` (simulated, no client needed).
- If you miss champ select you dodge (queue lockout, SP loss), so only accept when you'll be back in time.

## Versions
The version is shown in the startup window and at the bottom of the phone page.
See `CHANGELOG.md` for what changed. Releases are tagged in git (`git tag` lists them).

To release: bump `__version__` in `league_remote.py`, add a `CHANGELOG.md` entry,
commit, then `git tag -a vX.Y.Z -m "..."`.
