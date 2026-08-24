"""Validate Production Dispatcher Agent (Steered Candidate vs Unsteered Opponent)

Runs real env.run() across Official 20 Seeds and compares with FastGame.
"""

import sys
import numpy as np
from kaggle_environments import make

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent, make_spatial_dispatcher_agent
)

OFFICIAL_20_SEEDS = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200, 250, 300, 333, 404, 500, 600, 700, 777, 888, 999]


def run_real_kaggle_env(seed: int) -> tuple[float, float]:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
    p0 = make_spatial_dispatcher_agent(seed=seed)
    p1 = make_spatial_dispatcher_agent() # Standard standing opponent (Kw=10)
    env.run([p0, p1])
    s = env.steps[-1]
    return float(s[0].reward), float(s[1].reward)


def run_fast_engine(seed: int) -> tuple[float, float]:
    game = FastGame(seed=seed)
    p0 = make_spatial_dispatcher_agent(seed=seed)
    p1 = make_spatial_dispatcher_agent() # Standard standing opponent (Kw=10)
    while not game.done:
        act0 = p0(game.get_observation(0))
        act1 = p1(game.get_observation(1))
        game.step_game(act0, act1)
    return float(game.farms[0].money), float(game.farms[1].money)


def main():
    print("=" * 95)
    print("=== VALIDATING PRODUCTION DISPATCHER AGENT (STEERED P0 vs UNSTEERED P1) ===")
    print("=" * 95)

    real_scores = []
    fast_scores = []

    print(f"{'Seed':<6} | {'Real env.run() (P0, P1)':<28} | {'Real Avg':<14} | {'Fast Engine Avg':<16} | {'Delta':<8}")
    print("-" * 80)
    for seed in OFFICIAL_20_SEEDS:
        r0_real, r1_real = run_real_kaggle_env(seed)
        real_avg = (r0_real + r1_real) / 2.0
        real_scores.append(real_avg)

        r0_fast, r1_fast = run_fast_engine(seed)
        fast_avg = (r0_fast + r1_fast) / 2.0
        fast_scores.append(fast_avg)

        diff = abs(real_avg - fast_avg)
        print(f"{seed:<6} | (${r0_real:>10,.2f}, ${r1_real:>10,.2f}) | ${real_avg:>12,.2f} | ${fast_avg:>14,.2f} | ${diff:>6,.2f}")

    mean_real = float(np.mean(real_scores))
    mean_fast = float(np.mean(fast_scores))
    max_engine_diff = float(np.max(np.abs(np.array(real_scores) - np.array(fast_scores))))

    print("\n--- Official 20-Seed Production Validation Results ---")
    print(f"Real env.run() Mean:    ${mean_real:,.2f}")
    print(f"Fast Engine Mean:       ${mean_fast:,.2f}")
    print(f"Max Engine Discrepancy: ${max_engine_diff:,.2f}")

    print("\n--- 100 Disjoint Seeds (10000-10099) Fast Engine ---")
    disjoint_100_scores = []
    for idx, seed in enumerate(range(10000, 10100)):
        r0, r1 = run_fast_engine(seed)
        disjoint_100_scores.append((r0 + r1) / 2.0)
        if (idx + 1) % 25 == 0:
            print(f"Processed {idx + 1:>3}/100 seeds...")

    mean_disjoint = float(np.mean(disjoint_100_scores))
    print(f"\n100 Disjoint Seeds Mean: ${mean_disjoint:,.2f}")

    print("\n" + "=" * 95)
    print(f"Official 20 Seeds: Real env.run() = ${mean_real:,.2f} | Fast Engine = ${mean_fast:,.2f}")
    print(f"100 Disjoint Seeds: Fast Engine  = ${mean_disjoint:,.2f}")
    print("=" * 95)


if __name__ == "__main__":
    main()
