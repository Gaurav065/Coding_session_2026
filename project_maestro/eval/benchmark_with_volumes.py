"""Comprehensive 20-Seed Self-Play Benchmark with Product Volumes - Project Maestro

Measures pure self-play (both players running candidate agent) across 20 fixed seeds.
Reports match rewards, min/median/mean, and per-player sales volumes for all products.
"""

import sys
import time
import statistics
from typing import Dict, Any, Optional
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent, DEFAULT_PARAMS

SEEDS = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200, 250, 300, 333, 404, 500, 600, 700, 777, 888, 999]
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]

def run_benchmark(params: Optional[Dict[str, Any]] = None, title: str = "SELF-PLAY BENCHMARK"):
    p0_rewards = []
    p1_rewards = []
    avg_rewards = []
    sold_totals = {p: 0 for p in PRODUCTS}

    print("=" * 80)
    print(f"=== {title} (20 SEEDS) ===")
    print("=" * 80)

    for seed in SEEDS:
        game = FastGame(seed=seed)
        a0 = make_spatial_dispatcher_agent(params)
        a1 = make_spatial_dispatcher_agent(params)

        while not game.done:
            obs0 = game.get_observation(0)
            obs1 = game.get_observation(1)
            act0 = a0(obs0)
            act1 = a1(obs1)

            for act in (act0, act1):
                for order in act.get("market", []):
                    if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                        item, n = order[1], order[2]
                        if item in sold_totals:
                            sold_totals[item] += n

            game.step_game(act0, act1)

        r0 = float(game.farms[0].money)
        r1 = float(game.farms[1].money)
        r_avg = (r0 + r1) / 2.0

        p0_rewards.append(r0)
        p1_rewards.append(r1)
        avg_rewards.append(r_avg)

        print(f"Seed {seed:>4} | P0: ${r0:>9,.2f} | P1: ${r1:>9,.2f} | Match Avg: ${r_avg:>9,.2f}")

    mean_avg = statistics.mean(avg_rewards)
    median_avg = statistics.median(avg_rewards)
    min_avg = min(avg_rewards)
    max_avg = max(avg_rewards)

    print("=" * 80)
    print("=== SUMMARY STATISTICS ===")
    print(f"Match Mean   : ${mean_avg:>10,.2f}")
    print(f"Match Median : ${median_avg:>10,.2f}")
    print(f"Match Min    : ${min_avg:>10,.2f}")
    print(f"Match Max    : ${max_avg:>10,.2f}")
    print("\n--- 20-Seed Average Product Sales (Per Player per Match) ---")
    num_players = len(SEEDS) * 2
    for p in PRODUCTS:
        per_player = sold_totals[p] / num_players
        print(f"  {p:<12}: {per_player:>7.1f} units")
    print("=" * 80)

    return {
        "mean": mean_avg,
        "median": median_avg,
        "min": min_avg,
        "max": max_avg,
        "rewards": avg_rewards,
        "volumes": {p: sold_totals[p] / num_players for p in PRODUCTS}
    }

if __name__ == "__main__":
    run_benchmark(title="BASELINE ON CORRECTED FAST ENGINE")
