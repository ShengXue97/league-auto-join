"""
League Classic rank (Summoner's Journey) tracking and predictions.

Rules (Riot support, "League Classic - Progression"):
  Emblems Salt, Wood, Silver, Gold, Platinum, Diamond each have divisions IV-I,
  100 SP (Seasonal Points) per division. Legend is the apex: no divisions, no SP cap.
  Dropping below 0 SP demotes a division, but Division IV is the floor of each emblem.

The client reports the Classic queue (JADE_RANKED_SOLO_5x5) with the standard
ranked tier names. PLATINUM is confirmed to be the Platinum emblem; the other
names map by order (IRON = Salt, BRONZE = Wood, ... MASTER and above = Legend).

The client only knows your *current* SP, not what each past game gave, so this
module records a snapshot before and after every game and learns your typical
SP per win / loss from those.
"""

import json
import math
import os
import time

QUEUE = "JADE_RANKED_SOLO_5x5"
EMBLEMS = ["Salt", "Wood", "Silver", "Gold", "Platinum", "Diamond"]
CLIENT_TIERS = ["IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "DIAMOND"]
APEX_TIERS = {"MASTER", "GRANDMASTER", "CHALLENGER"}
DIVS = ["IV", "III", "II", "I"]
LEGEND = len(EMBLEMS) * 400  # position where Legend starts

DEFAULT_WIN_SP = 20   # used until enough games are tracked
DEFAULT_LOSS_SP = 20
LEARN_MIN = 3         # tracked wins/losses needed before trusting the averages
LEARN_LAST = 10       # average over the most recent N


def position(tier, division, sp):
    """Rank as one number: 0 = Salt IV 0 SP, 100 per division, LEGEND = Legend 0 SP."""
    tier = (tier or "").upper()
    if tier in APEX_TIERS:
        return LEGEND + (sp or 0)
    if tier not in CLIENT_TIERS:
        return None
    div = DIVS.index(division) if division in DIVS else 0
    return CLIENT_TIERS.index(tier) * 400 + div * 100 + (sp or 0)


def describe(pos):
    """Position -> {'emblem', 'division', 'sp', 'text'}."""
    if pos >= LEGEND:
        sp = pos - LEGEND
        return {"emblem": "Legend", "division": "", "sp": sp, "text": f"Legend {sp} SP"}
    e, rest = divmod(max(0, pos), 400)
    d, sp = divmod(rest, 100)
    return {"emblem": EMBLEMS[e], "division": DIVS[d], "sp": sp, "text": f"{EMBLEMS[e]} {DIVS[d]} {sp} SP"}


def short(pos):
    """'Platinum I' / 'Legend' - the division a position is in."""
    d = describe(pos)
    return d["emblem"] + (f" {d['division']}" if d["division"] else "")


def emblem_floor(pos):
    """Division IV 0 SP of the current emblem - you can't drop below it."""
    return LEGEND if pos >= LEGEND else (pos // 400) * 400


def after_losses(pos, n, loss):
    """Where n losses leave you, respecting 'below 0 SP demotes' and the emblem floor."""
    floor = emblem_floor(pos)
    for _ in range(n):
        if pos >= LEGEND:
            pos = max(LEGEND, pos - loss)
            continue
        base = (pos // 100) * 100
        if pos - loss >= base:
            pos -= loss
        elif base > floor:  # demote: land in the division below
            pos = max(base - 100, base - 100 + 100 - (loss - (pos - base)))
        else:               # division IV of the emblem: stays at 0
            pos = base
    return pos


def entry_from_ranked_stats(stats):
    """The Classic queue entry from /lol-ranked/v1/current-ranked-stats (or None)."""
    q = ((stats or {}).get("queueMap") or {}).get(QUEUE)
    if not q or not q.get("tier") or q.get("tier") in ("NONE", ""):
        return None
    pos = position(q.get("tier"), q.get("division"), q.get("leaguePoints"))
    if pos is None:
        return None
    return {"pos": pos, "wins": q.get("wins", 0), "losses": q.get("losses", 0),
            "tier": q.get("tier"), "division": q.get("division"), "sp": q.get("leaguePoints", 0),
            "highest": position(q.get("highestTier"), q.get("highestDivision"), 0),
            "provisional": q.get("provisionalGamesRemaining", 0)}


class RankTracker:
    """rank_history.jsonl: one line per detected SP change (git-ignored)."""

    def __init__(self, path):
        self.path = path
        self.state_path = path + ".last"  # last rank seen, so games played while closed still count
        self.last = None

    def _load_last(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return None

    def _save_last(self, entry):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({k: entry[k] for k in ("pos", "wins", "losses")}, f)

    def changes(self):
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
        return out

    def update(self, entry, game=None):
        """Feed the latest Classic entry. Returns the new change record when a game finished."""
        if entry is None:
            return None
        prev, self.last = (self.last or self._load_last()), entry
        if prev is None or (prev["pos"], prev["wins"], prev["losses"]) != (entry["pos"], entry["wins"], entry["losses"]):
            self._save_last(entry)
        if prev is None:
            return None
        played = (entry["wins"] + entry["losses"]) - (prev["wins"] + prev["losses"])
        if played <= 0:
            return None
        change = {
            "time": time.strftime("%Y-%m-%d %H:%M"),
            "games": played,
            "win": entry["wins"] > prev["wins"] if played == 1 else None,
            "delta": entry["pos"] - prev["pos"],
            "before": {k: prev[k] for k in ("pos", "wins", "losses")},
            "after": {k: entry[k] for k in ("pos", "wins", "losses")},
            "game_id": str(game["id"]) if game and played == 1 else None,
            "champ": game.get("champ") if game and played == 1 else None,
        }
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(change) + "\n")
        return change


def learned_sp(changes):
    """Typical SP per win and per loss from single-game changes (with defaults until learned)."""
    single = [c for c in changes if c.get("games") == 1 and c.get("win") is not None]
    wins = [c["delta"] for c in single if c["win"] and c["delta"] > 0][-LEARN_LAST:]
    # a loss at the emblem floor shows 0 - it says nothing about SP per loss
    losses = [-c["delta"] for c in single if not c["win"] and c["delta"] < 0][-LEARN_LAST:]
    return {
        "win": round(sum(wins) / len(wins)) if len(wins) >= LEARN_MIN else DEFAULT_WIN_SP,
        "loss": round(sum(losses) / len(losses)) if len(losses) >= LEARN_MIN else DEFAULT_LOSS_SP,
        "win_learned": len(wins) >= LEARN_MIN,
        "loss_learned": len(losses) >= LEARN_MIN,
        "tracked_wins": len(wins),
        "tracked_losses": len(losses),
    }


def win_rate(entry, recent_results, recent_n=20):
    """Recent Classic ranked win rate when there's enough history, else the season's."""
    recent = [r for r in recent_results if r is not None][-recent_n:]
    season_games = entry["wins"] + entry["losses"]
    season = entry["wins"] / season_games if season_games else 0.5
    if len(recent) >= 10:
        return sum(recent) / len(recent), f"last {len(recent)} games", season
    return season, "this season", season


def predict(entry, changes, recent_results):
    """Everything the Stats page shows about climbing."""
    pos = entry["pos"]
    sp = learned_sp(changes)
    g, l = sp["win"], sp["loss"]
    p, basis, season_wr = win_rate(entry, recent_results)
    ev = p * g - (1 - p) * l

    targets = []
    if pos < LEGEND:
        nxt = (pos // 100 + 1) * 100
        targets.append(nxt)
        e = pos // 400
        for start in range((e + 1) * 400, LEGEND + 1, 400):
            if start not in targets:
                targets.append(start)
    goals = []
    for t in targets:
        need = t - pos
        goals.append({
            "name": "Legend" if t >= LEGEND else short(t),
            "emblem": t % 400 == 0 or t >= LEGEND,
            "need": need,
            "min_wins": math.ceil(need / g) if g > 0 else None,
            "games": math.ceil(need / ev) if ev > 0 else None,
        })

    floor = emblem_floor(pos)
    div_base = (pos // 100) * 100
    losses_to_drop = None
    if pos < LEGEND and div_base > floor and l > 0:
        losses_to_drop = (pos - div_base) // l + 1

    scenarios = []
    for n in (1, 2, 3, 5):
        scenarios.append({"n": n, "win": describe(min(pos + n * g, 10 ** 6))["text"] if pos + n * g < LEGEND
                          else describe(pos + n * g)["text"],
                          "loss": describe(after_losses(pos, n, l))["text"]})

    return {
        "rank": describe(pos),
        "pos": pos,
        "season": {"wins": entry["wins"], "losses": entry["losses"], "wr": round(100 * season_wr)},
        "highest": short(entry["highest"]) if entry.get("highest") is not None else None,
        "sp": sp,
        "win_rate": round(100 * p),
        "win_rate_basis": basis,
        "expected_per_game": round(ev, 1),
        "break_even_wr": round(100 * l / (g + l)) if g + l else 50,
        "goals": goals,
        "losses_to_drop": losses_to_drop,
        "at_floor": pos < LEGEND and div_base == floor,
        "scenarios": scenarios,
        "history": [{"time": c["time"], "delta": c["delta"], "win": c.get("win"), "games": c.get("games"),
                     "champ": c.get("champ"), "after": describe(c["after"]["pos"])["text"]}
                    for c in reversed(changes[-15:])],
        "trend": [c["after"]["pos"] for c in changes[-30:]],
    }
