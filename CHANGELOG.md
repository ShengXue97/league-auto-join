# Changelog

Versions follow [semantic versioning](https://semver.org): MAJOR.MINOR.PATCH.
The running version is shown in the startup window and at the bottom of the phone page.

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
