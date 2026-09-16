#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test production agent loaded directly from modular_apex.main."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kaggriculture_architecture"))

from modular_apex import main
import kaggle_environments

def test_production():
    test_seeds = [42, 100, 2026, 7, 24]
    print("Testing Production main.py agent across seeds:", test_seeds)
    
    total_rewards = []
    for s in test_seeds:
        env = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([main.agent, "pass"])
        obs = env.steps[-1][0]["observation"]
        r = env.steps[-1][0]["reward"] or 0
        shed = obs["private"]["shed"]
        trapped = shed.get("COW", 0) + shed.get("SHEEP", 0) + shed.get("GOOSE", 0)
        quads = obs["farms"][0]["unlocked_quadrants"]
        shops = obs["town"]["unlocked_shops"]
        pizzas = shops.count("PIZZA_SHOP")
        total_rewards.append(r)
        print(f"Seed {s:4d} (Pizzas: {pizzas}): Reward = ${r:,.0f} | Trapped Animals = {trapped} | Quads = {quads}")
        
    avg = sum(total_rewards) / len(total_rewards)
    print("=" * 65)
    print(f"Production Benchmark: Avg Reward = ${avg:,.0f} | Peak = ${max(total_rewards):,.0f}")
    print("=" * 65)

if __name__ == "__main__":
    test_production()
