"""Diagnostic: is the CARE bonus mechanic (kaggriculture.py:826-830) actually landing on
the CURRENT dispatcher_agent.py, and if not, why not?

Triggered by a real discrepancy between two of this project's own documents: HANDOVER.md
still lists "no CARE bonus (~$42k)" as the single highest-value unimplemented fix, while
agent/NOTES.md's benchmark table shows a "CARE bonus lock (via Nemotron)" row was already
attempted and only gained ~$1,300 over the prior build -- and no volume numbers (milk/wool
sold) were ever recorded for that attempt or anything after it. Rather than trust either
document, measure the CURRENT code directly.

Uses the fast engine (verified 20/20 exact vs the reference engine) for speed and because
we need to read internal tile state (fed_today/cared_today/pending_care_bonus) that isn't
exposed through the public observation dict.
"""
import statistics
import sys

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame, EPISODE_STEPS
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

SEEDS = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200, 250, 300, 333, 404, 500, 600, 700, 777, 888, 999]


def _sold(action, sold):
    for order in (action.get("market") or []):
        if len(order) >= 3 and order[0] == "SELL":
            sold[order[1]] = sold.get(order[1], 0) + max(0, int(order[2] or 0))


def run_one(seed):
    game = FastGame(seed=seed)
    a0 = make_spatial_dispatcher_agent()
    a1 = make_spatial_dispatcher_agent()

    animal_days = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
    cared_days = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
    fed_only_days = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
    neither_days = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
    sold_p0 = {}
    last_hour_seen = -1

    while not game.done:
        act0 = a0(game.get_observation(0))
        act1 = a1(game.get_observation(1))
        _sold(act0, sold_p0)
        game.step_game(act0, act1)
        hour = game.step % 24
        # sample right before the midnight reset (engine resets fed/cared_today at
        # the day boundary, so hour 23 of the just-completed day is the last chance
        # to observe that day's true fed/cared state)
        if hour == 23 and hour != last_hour_seen:
            for farm in (game.farms[0], game.farms[1]):
                for row in farm.tiles:
                    for tile in row:
                        if isinstance(tile, dict) and "animal" in tile:
                            kind = tile["animal"]
                            animal_days[kind] += 1
                            fed = tile.get("fed_today", False)
                            cared = tile.get("cared_today", False)
                            if fed and cared:
                                cared_days[kind] += 1
                            elif fed:
                                fed_only_days[kind] += 1
                            else:
                                neither_days[kind] += 1
        last_hour_seen = hour

    money = (float(game.farms[0].money) + float(game.farms[1].money)) / 2
    return money, animal_days, cared_days, fed_only_days, neither_days, sold_p0


def main():
    moneys = []
    tot_animal_days = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
    tot_cared_days = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
    tot_fed_only_days = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
    tot_neither_days = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
    sold_totals = {}

    for seed in SEEDS:
        money, animal_days, cared_days, fed_only_days, neither_days, sold_p0 = run_one(seed)
        moneys.append(money)
        for k in ("COW", "SHEEP", "GOOSE"):
            tot_animal_days[k] += animal_days[k]
            tot_cared_days[k] += cared_days[k]
            tot_fed_only_days[k] += fed_only_days[k]
            tot_neither_days[k] += neither_days[k]
        for item, qty in sold_p0.items():
            sold_totals[item] = sold_totals.get(item, 0) + qty
        print(f"seed {seed:>4}: money(avg of P0/P1)=${money:>10,.2f}  sold(P0)={sold_p0}", flush=True)

    print("=" * 80)
    print(f"mean money across {len(SEEDS)} seeds: ${statistics.mean(moneys):,.2f}")
    print("=" * 80)
    print(f"mean units sold per game, P0 only (n={len(SEEDS)} seeds):")
    for item, total in sorted(sold_totals.items()):
        print(f"  {item:>12}: {total / len(SEEDS):>8.1f}")
    print("=" * 80)
    print("fed+cared same-day hit rate, by animal, across all animal-tile-days observed:")
    for k in ("COW", "SHEEP", "GOOSE"):
        total = tot_animal_days[k]
        if total == 0:
            print(f"  {k}: no animal-tile-days observed")
            continue
        pct_both = 100 * tot_cared_days[k] / total
        pct_fed_only = 100 * tot_fed_only_days[k] / total
        pct_neither = 100 * tot_neither_days[k] / total
        print(f"  {k}: n={total:>6}  both={pct_both:5.1f}%  fed-only={pct_fed_only:5.1f}%  neither={pct_neither:5.1f}%")


if __name__ == "__main__":
    main()
