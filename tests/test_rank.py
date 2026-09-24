"""Summoner's Journey rank math and predictions.

Run: python tests/test_rank.py
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import rank

failed = False


def check(cond, msg):
    global failed
    print(("PASS " if cond else "FAIL ") + msg)
    failed |= not cond


P1 = rank.position("PLATINUM", "I", 22)
check(P1 == 1922, "Platinum I 22 -> position 1922")
check(rank.describe(P1)["text"] == "Platinum I 22 SP", "describe")
check(rank.describe(rank.position("IRON", "IV", 0))["text"] == "Salt IV 0 SP", "IRON is Salt")
check(rank.describe(rank.position("BRONZE", "II", 50))["emblem"] == "Wood", "BRONZE is Wood")
check(rank.describe(rank.position("CHALLENGER", "I", 340))["text"] == "Legend 340 SP", "apex tiers are Legend")
check(rank.position("EMERALD", "I", 0) is None, "unknown tier ignored")

# losses: demotion and the Division IV floor
check(rank.after_losses(P1, 1, 20) == 1902, "one loss: 22 -> 2 SP")
check(rank.describe(rank.after_losses(P1, 2, 20))["text"] == "Platinum II 82 SP", "second loss demotes to Platinum II")
p4 = rank.position("PLATINUM", "IV", 10)
check(rank.after_losses(p4, 3, 20) == rank.position("PLATINUM", "IV", 0), "Division IV floor: can't drop out of Platinum")
check(rank.after_losses(rank.position("MASTER", "I", 30), 2, 20) == rank.LEGEND, "Legend floors at 0 SP")

# learning SP per game
check(rank.learned_sp([])["win"] == rank.DEFAULT_WIN_SP and not rank.learned_sp([])["win_learned"], "defaults before learning")


def ch(delta, win, games=1):
    return {"delta": delta, "win": win, "games": games, "time": "t", "after": {"pos": 1900}, "champ": None}


changes = [ch(24, True), ch(22, True), ch(-17, False), ch(26, True), ch(-19, False), ch(0, False), ch(-18, False),
           ch(-60, None, games=3)]
sp = rank.learned_sp(changes)
check(sp["win"] == 24 and sp["win_learned"], f"learned win SP = avg(24,22,26) (got {sp['win']})")
check(sp["loss"] == 18 and sp["loss_learned"], f"learned loss SP ignores floor 0s and multi-game (got {sp['loss']})")

# predictions
entry = {"pos": P1, "wins": 60, "losses": 54, "highest": P1}
pred = rank.predict(entry, changes, [True, False] * 10)
check(pred["win_rate"] == 50 and pred["win_rate_basis"] == "last 20 games", "recent win rate used when >= 10 games")
check(pred["expected_per_game"] == 3.0, f"EV = .5*24 - .5*18 = 3.0 (got {pred['expected_per_game']})")
g = pred["goals"]
check(g[0]["name"] == "Diamond IV" and g[0]["need"] == 78 and g[0]["min_wins"] == 4 and g[0]["games"] == 26,
      f"Diamond IV: 78 SP, 4 wins, 26 games (got {g[0]})")
check(g[-1]["name"] == "Legend" and g[-1]["need"] == 478, "Legend goal")
check(pred["losses_to_drop"] == 2 and not pred["at_floor"], "2 losses to drop from Platinum I 22")
check(pred["break_even_wr"] == 43, f"break-even 18/(24+18) = 43% (got {pred['break_even_wr']})")
check(pred["scenarios"][0] == {"n": 1, "win": "Platinum I 46 SP", "loss": "Platinum I 4 SP"}, "one-game scenario")
check(pred["history"][0]["delta"] == -60 and pred["history"][0]["games"] == 3, "history newest first")

low = rank.predict({**entry, "wins": 10, "losses": 30}, [], [])
check(low["win_rate_basis"] == "this season" and low["win_rate"] == 25, "season win rate when little recent data")
check(all(x["games"] is None for x in low["goals"]), "no ETA when losing SP on average")

floor = rank.predict({"pos": rank.position("GOLD", "IV", 40), "wins": 1, "losses": 1, "highest": None}, [], [])
check(floor["at_floor"] and floor["losses_to_drop"] is None, "Division IV: at floor, no demotion")
check([x["name"] for x in floor["goals"]][:2] == ["Gold III", "Platinum IV"], "next division then next emblem")
legend = rank.predict({"pos": rank.LEGEND + 50, "wins": 1, "losses": 1, "highest": None}, [], [])
check(legend["goals"] == [] and legend["rank"]["emblem"] == "Legend", "Legend has no further goals")

# tracker
path = os.path.join(tempfile.mkdtemp(), "r.jsonl")
t = rank.RankTracker(path)
e0 = {"pos": 1922, "wins": 60, "losses": 54}
check(t.update(e0) is None, "first snapshot records nothing")
check(t.update(dict(e0)) is None, "no change without a new game")
c = t.update({"pos": 1943, "wins": 61, "losses": 54}, {"id": 555, "champ": "Pantheon"})
check(c["delta"] == 21 and c["win"] and c["game_id"] == "555" and c["champ"] == "Pantheon", "win recorded")
t2 = rank.RankTracker(path)  # restart: continues from the saved file
c = t2.update({"pos": 1925, "wins": 61, "losses": 55})
check(c and c["delta"] == -18 and c["win"] is False, "change after restart uses the saved snapshot")
check(len(rank.RankTracker(path).changes()) == 2, "changes persisted")
fresh = rank.RankTracker(os.path.join(tempfile.mkdtemp(), "r.jsonl"))
fresh.update({"pos": 1922, "wins": 60, "losses": 54})  # first ever run, then League Remote is closed
c = rank.RankTracker(fresh.path).update({"pos": 1966, "wins": 62, "losses": 54})  # reopened after 2 wins
check(c and c["games"] == 2 and c["delta"] == 44, "games played while closed are still recorded")
check(rank.entry_from_ranked_stats({"queueMap": {}}) is None, "no Classic rank -> None")
check(rank.entry_from_ranked_stats({"queueMap": {"JADE_RANKED_SOLO_5x5": {"tier": "NONE"}}}) is None, "unranked -> None")

print("\nALL PASSED" if not failed else "\nSOME FAILED")
sys.exit(1 if failed else 0)
