# Changelog

Versions follow [semantic versioning](https://semver.org): MAJOR.MINOR.PATCH.
The running version is shown in the startup window and at the bottom of the phone page.

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
