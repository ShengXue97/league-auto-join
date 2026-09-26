# Changelog

Versions follow [semantic versioning](https://semver.org): MAJOR.MINOR.PATCH.
The running version is shown in the startup window and at the bottom of the phone page.

## [2.1.0] - 2026-09-26
### Added
- One-click update: "Update now" in the tray menu and on the control page. League
  Remote downloads the new installer, checks it against GitHub's SHA-256 and size
  (a corrupted or tampered file is never run), installs it silently and restarts
  on the new version, keeping your settings. Windows asks once for permission.
- "League Remote was updated to vX" notification after an update.

### Fixed
- "Subscribe in ntfy" on Android now uses an intent link (opens the ntfy app, or
  the Play Store if it isn't installed). On iPhone, where ntfy doesn't document
  subscribe links, the page goes straight to the copy-and-paste steps.
- "Copy topic" didn't work: browsers block the modern clipboard API on http pages.
  It now falls back to the classic copy command and says "Copied!" only when it
  really copied.

## [2.0.2] - 2026-09-26
### Fixed
- The ntfy QR code on the setup page didn't work: phone cameras won't open ntfy://
  links from a QR code. It now opens a League Remote page on your phone with a
  "Subscribe in ntfy" button, a Copy topic button and app store links.

### Changed
- Update check, installer and README point to github.com/league-remote-team/league-remote.

## [2.0.1] - 2026-09-26
### Added
- After installing, League Remote opens the phone setup page automatically and
  shows a Windows notification pointing to its bell icon in the notification area.
- The installer's last screen and the setup page explain where League Remote
  lives (the tray bell, the ^ arrow, the Start menu entry).

## [2.0.0] - 2026-09-26
### Added
- Windows app: `LeagueRemote.exe` (no Python needed) and an installer
  (`LeagueRemote-Setup-x.y.z.exe`) with Start Menu entry, optional Start with
  Windows / desktop shortcut, uninstaller, and a firewall rule for the phone
  (Private networks; Public is an opt-in checkbox).
- League Remote icon (original artwork) for the app, tray, installer and page.
- System tray icon: open the control page, phone setup, Start with Windows, Quit.
- Phone setup page (`/setup`) with QR codes to subscribe to ntfy (Android opens
  the app directly) and to open the control page, a test-alert button, and a
  warning with steps when Windows treats your Wi-Fi as Public.
- Update check against GitHub releases (tray notification + banner on the page).
- Riot Games "not endorsed" notice on the page, setup page and README.

### Fixed
- LOCK IN from the phone could silently do nothing. Lock-in now uses the same
  one-step update as the client, falls back to the separate /complete call, and
  verifies the pick really locked; if not, a clear red message says so. The
  page updates right after the tap and shows a confirmation.

### Changed
- Auto-accept is back as an optional toggle, off by default, with a warning that
  Riot's rules treat it as automation.
- Your data now lives in `%APPDATA%\LeagueRemote` (copied there automatically
  from the project folder when running from source).
- The raw client-data recorder only runs from source (not in the app).

## [1.7.3] - 2026-09-25
### Added
- A game League Remote saw end is fetched from Riot by its id and shown in Stats
  right away, even while Riot's recent-games list hasn't added it yet (seen on a
  real game: the list caught up about 5 minutes after the game ended).

### Changed
- Much less match-history traffic: the recent-games list is read every 5 minutes
  (was every minute, and every 5 s for 4 minutes after each game). Right after a
  game only your rank is checked quickly.

## [1.7.2] - 2026-09-25
### Fixed
- SP change credited to the wrong game: Riot adds a finished game to the match
  history minutes later, and League Remote linked the SP change to the newest
  game in the history, i.e. the previous game. It now links it to the game it saw
  end (end-of-game stats / live game id). Confirmed on a real League Classic game.

## [1.7.1] - 2026-09-24
### Fixed
- Constant flicker in champ select: every second the page rebuilt your team,
  favorites and bans, recreating every icon (measured: 36 icons per 6 s). Sections
  are now only redrawn when their content changes (measured after: 0).
- Countdown could jump back and forth by a second between refreshes.

### Changed
- The page refreshes less often: every 1 s only during match found and champ
  select, 2 s in queue, 3 s in game, 5 s otherwise (and right away when you
  come back to the tab). Queue, champ select and game timers tick locally in
  between. League Remote itself still checks the client every 0.5 s, so alerts
  are as fast as before.

## [1.7.0] - 2026-09-24
### Removed
- Auto-accept. Riot's Terms of Service (7.1) forbid automation programs and Riot
  support names "taking actions on your behalf" as bannable. Accepting is now
  always your own tap (notification button or phone page). An old
  `auto_accept` setting in config.json is ignored.

### Changed
- Champ select never shows teammates' names, only their role (or "Ally #n").
  Riot hides names in ranked champ select to prevent dodging, and apps must not
  reveal them.
- README safety section updated with Riot's Terms of Service, developer policy
  and Vanguard FAQ.

## [1.6.0] - 2026-09-24
### Added
- Start with Windows: League Remote starts hidden (no console window) when you
  log in, and waits for the League client. Toggle it on the phone page, or run
  `--install-startup` / `--uninstall-startup`. Hidden runs log to
  `league_remote.log`.
- One League Remote at a time: opening it while another copy runs replaces that
  copy (a restart with your latest changes). The old copy is asked to stop
  (`/api/shutdown`, accepted only from this PC) and force-stopped if it's an
  older version without that. Programs that aren't League Remote are never
  stopped; if one holds the port, League Remote says so and exits.
- `stop.bat` / `--stop` to stop the hidden copy.
- `tests/test_autostart.py`: real processes on a spare port.

## [1.5.3] - 2026-09-24
### Fixed
- Wrong scroll position when loading or refreshing the page: the browser restored
  the old scroll position before the data had loaded, and the page sections had
  ids equal to the URL fragment (#live / #stats), which the browser treats as
  "jump here". Sections are renamed, scroll restoration is manual, and each tab
  starts at the top.

## [1.5.2] - 2026-09-24
### Fixed
- Stats overview showed 98 games / 49-49 while the Live tab showed 60W 54L.
  Both were real but covered different things: the League client only keeps
  your last 100 games (checked: it ignores requests for older ones), while the
  rank data has the full season. The overview now shows the full season
  record from the rank data, and champion stats / trends / recent games say
  which games and dates they cover.
- A test wrote a fake history file into the project folder; tests now always
  use temporary folders.

### Added
- History cache (`history_cache.json`, git-ignored): every game seen is kept,
  so games no longer drop off when the client's 100-game window moves on.

## [1.5.1] - 2026-09-24
### Fixed
- Aegis of Valor after a role swap: League Remote re-checked your *new* role, so
  swapping from an autofilled Support (#5) into Jungle (#3) still showed
  "+40% possible". It now remembers the role you were first assigned; swapping
  shows "Aegis of Valor lost" and the game is tracked as a normal game.

## [1.5.0] - 2026-09-24
### Added
- Aegis of Valor: League Remote reads your 5 role preferences from the lobby
  and, in champ select, shows "Aegis of Valor possible" when you're assigned
  your #3/#4/#5 role (+40% / +70% / +100% SP on a win; occasional, lost if you
  swap roles). Also in the champ select alert and the post-game alert.
- SP changes are saved with your role and preference; wins in Aegis roles are
  kept out of your normal SP-per-win average and shown separately with the
  observed bonus. Stats tab has an Aegis of Valor card with your role order.

### Changed
- No made-up SP numbers: the old +/-20 default is gone. "If you win / lose",
  games-to-goal, scenarios, break-even and demotion warnings only appear once
  real SP changes are tracked (marked "rough" until 3 wins and 3 losses).
  SP needed for each goal is always shown.

### Fixed
- Champ select would crash when checking Aegis (a local variable shadowed the
  rank module).

## [1.4.0] - 2026-09-24
### Added
- Classic rank (Summoner's Journey): emblem, division and SP from the client,
  season record, league standing, and SP for your next win / loss.
- SP tracking: Riot doesn't store per-game SP, so League Remote records the rank
  before and after every game (`rank_history.jsonl`, git-ignored) and learns
  your typical SP per win and loss. Games played while it was closed are still
  counted on the next start.
- Climb forecast: games and minimum wins to the next division, each emblem and
  Legend, with a what-if win-rate slider (presets: recent form, season, your
  main champion), break-even win rate and demotion warning.
- Next-games scenarios (1/2/3/5 wins or losses) and an SP history list.
- Post-game alert now waits for the SP change: "VICTORY +21 SP", new rank and
  games to the next emblem.
- Rank line on the Live tab while idle or in queue.
- `tests/test_rank.py`.

### Changed
- Stats now come from Riot's official match history (your last ~100 games,
  Classic only), replacing League Remote's own `matches.jsonl` log.

## [1.3.0] - 2026-09-24
### Added
- In-game second screen (read-only, from Riot's official Live Client Data API):
  your KDA, CS, CS/min vs your goal (`cs_goal`), kill participation, vision,
  gold, items and respawn countdown; Tab-style scoreboard; kill/objective feed.
- Alerts: game loaded, reconnect needed (with a RECONNECT button), and a
  VICTORY/DEFEAT summary with personal bests and today's record.
- Match history (`matches.jsonl`, git-ignored) from the client's end-of-game
  stats, with a fallback to the last live snapshot.
- Stats tab: win rate, W-L, streak, today's record, CS/min trend vs goal,
  per-champion stats (favorites first) and recent games.
- Responsive layout: one column on phones, two on tablets and desktop.
- Settings (auto-accept, favorites editor) only show outside champ select and games,
  so those screens stay focused.
- `tests/test_ingame.py`, including safety checks that no hidden enemy info
  (respawn timers, dead state, spells, gold) reaches the page.

### Security
- Player and champion names are HTML-escaped on the page; previously a
  crafted in-game name could inject markup into the control page.

## [1.2.0] - 2026-09-24
### Added
- Pick order swaps: team listed in pick order (#1-#5), Swap buttons for players
  who pick before you (earliest marked best), "Ask for pick #1" shortcut, and cancel.
- Incoming swap request alert and banner with ACCEPT / DECLINE and a verdict
  (earlier pick = recommended, later pick = warning). Alert when your request is
  accepted or declined.
- My champions: priority list with live status (available, banned, taken, ally
  hovering). Your top available favorite is pre-selected for one-tap LOCK IN.
- Alert when a favorite is banned or taken, suggesting the next available one.
- Champ select start alert now has "Hover <favorite>" and "Ask #N to swap" buttons.
- Add, remove and reorder favorites from the phone page; star/unstar from the grid.

### Fixed
- During a ban turn the page could pre-select your pick hover, making the button
  read "BAN <your pick>". Selection now resets when your action changes.
- Favorite names shared by League Classic and modern champions (e.g. Pantheon)
  resolve to the one in the current champ select.
- Favorites unknown to the client (typos) can still be removed.

## [1.1.0] - 2026-09-24
### Added
- Champion select from your phone: team, bans, enemy picks, timer, searchable
  champion grid (League Classic champions included), hover, LOCK IN and BAN.
- "Your turn to pick/ban" notification with one-tap buttons for favorite champions
  (`favorite_picks` / `favorite_bans` in `config.json`).
- Version number shown in the startup window, on the phone page and in `/api/status`.
- Simulated champion select test: `python tests/test_champ_select.py`.

### Changed
- No "champ select started" alert when a "your turn" alert was already sent.

## [1.0.0] - 2026-09-24
### Added
- Match found notification via ntfy with ACCEPT / DECLINE buttons.
- Phone control page on the home network with queue timer and auto-accept toggle.
- Alerts for champ select start, failed ready checks and leaving queue.
- Recorder that saves raw client data to `capture/` to study League Classic.
