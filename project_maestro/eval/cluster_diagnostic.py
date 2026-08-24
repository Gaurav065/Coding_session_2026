"""Real per-cluster performance diagnostic for the current chassis, via the fast engine.

Not a coverage table (that's Phase 2 proper, seeded from this). This answers a cheaper,
prior question: given the CURRENT static-portfolio dispatcher, does its self-play
performance actually vary by demand pressure the way the real meta's does (2.22x per
`meta_portfolio_summary.csv`), or is the gap to the $88k target uniform across draws?
That tells us whether a shop-conditional strategy is even the right lever to build next,
before investing in one (two isolated conditional-behavior attempts already failed this
session for principled reasons -- see agent/NOTES.md 2b/2c).

Uses engine/fast_engine.py (verified 20/20 exact vs the reference engine, ~14x speedup),
so this can run far more seeds than the standard 20-seed env.run() benchmark affords.
"""

import sys
import statistics
from collections import defaultdict

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame, EPISODE_STEPS
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

MILK_SHOPS = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}
WOOL_SHOPS = {"YARN_STORE"}
N_SEEDS = 60
BASE_SEED = 10000


def pressure_vector(shops):
    milk = sum(1 for s in shops if s in MILK_SHOPS)
    wool = sum(2 for s in shops if s in WOOL_SHOPS)  # single-product shop, x2 multiplier
    return milk, wool


def run_one(seed):
    game = FastGame(seed=seed)
    a0 = make_spatial_dispatcher_agent()
    a1 = make_spatial_dispatcher_agent()
    while not game.done:
        obs0 = game.get_observation(0)
        obs1 = game.get_observation(1)
        act0 = a0(obs0)
        act1 = a1(obs1)
        game.step_game(act0, act1)
    r0, r1 = float(game.farms[0].money), float(game.farms[1].money)
    milk, wool = pressure_vector(game.unlocked_shops)
    return r0, r1, milk, wool, tuple(sorted(game.unlocked_shops))


def main():
    results = []
    for i in range(N_SEEDS):
        seed = BASE_SEED + i
        r0, r1, milk, wool, shops = run_one(seed)
        results.append((seed, r0, r1, milk, wool, shops))
        print(f"seed {seed} | avg ${((r0+r1)/2):>10,.0f} | milk_shops={milk} wool_pressure={wool}", flush=True)

    all_avg = [(r0 + r1) / 2 for _, r0, r1, _, _, _ in results]
    print("\n" + "=" * 70)
    print(f"N={len(results)}  mean=${statistics.mean(all_avg):,.0f}  median=${statistics.median(all_avg):,.0f}  "
          f"min=${min(all_avg):,.0f}  max=${max(all_avg):,.0f}  spread={max(all_avg)/min(all_avg):.2f}x")

    by_milk = defaultdict(list)
    for seed, r0, r1, milk, wool, shops in results:
        by_milk[milk].append((r0 + r1) / 2)
    print("\nby milk-shop count:")
    for k in sorted(by_milk):
        v = by_milk[k]
        print(f"  milk_shops={k}  n={len(v):>3}  mean=${statistics.mean(v):>10,.0f}")

    by_wool = defaultdict(list)
    for seed, r0, r1, milk, wool, shops in results:
        by_wool[wool].append((r0 + r1) / 2)
    print("\nby wool pressure (YARN_STORE count x2):")
    for k in sorted(by_wool):
        v = by_wool[k]
        print(f"  wool_pressure={k}  n={len(v):>3}  mean=${statistics.mean(v):>10,.0f}")

    ranked = sorted(results, key=lambda x: (x[1] + x[2]) / 2)
    print("\nworst 5 seeds:")
    for seed, r0, r1, milk, wool, shops in ranked[:5]:
        print(f"  seed {seed}  avg=${(r0+r1)/2:,.0f}  milk={milk} wool={wool}  shops={shops}")
    print("best 5 seeds:")
    for seed, r0, r1, milk, wool, shops in ranked[-5:]:
        print(f"  seed {seed}  avg=${(r0+r1)/2:,.0f}  milk={milk} wool={wool}  shops={shops}")


if __name__ == "__main__":
    main()
