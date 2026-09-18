#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test Unified SE Expansion (6 Sheep + 6 Tomato/Melon corridor) across all shop types."""

import concurrent.futures
import copy
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KAGGLE_DIR = ROOT / "kaggriculture_architecture"
if str(KAGGLE_DIR) not in sys.path:
    sys.path.insert(0, str(KAGGLE_DIR))

import kaggle_environments
from modular_apex import chassis, config, payload, router, guards

def build_test_agent(allow_all_seeds=True, add_se_tomato=True):
    """Constructs agent with universal SE expansion."""
    import modular_apex._guards_source as gs
    
    # Store originals
    orig_eligible = gs._v233_eligible
    orig_qualifies = gs._v219_qualifies
    
    def universal_v233_eligible(obs, native):
        farm = obs["farms"][obs["player"]]
        prices = obs["market"]["prices"]
        if len(farm["tiles"]) != 10 or set(farm["unlocked_quadrants"]) != {"NW", "NE", "SW"}:
            return False
        # Universal eligibility: Day 12, cash >= 10,000, wool price reasonable or yarn store present
        shops = obs["town"]["unlocked_shops"]
        has_yarn = shops.count("YARN_STORE") >= 1
        has_cash = farm["money"] >= 10000
        if not (has_yarn or has_cash):
            return False
        if prices["WHEAT"] > 55:
            return False
        if any(farm["tiles"][y][x] != "LOCKED" for y in (5, 6) for x in range(5, 8)):
            return False
        if obs["private"]["shed"].get("SHEEP", 0) or any(i.get("SHEEP", 0) for i in obs["private"]["inventories"]):
            return False
        for day in range(12, 30):
            for a in gs._v219_native_day(native, day):
                if any(o and (o[0] == "BUY_LAND" or o[:2] == ["BUY_ANIMAL", "SHEEP"]) for o in a.get("market", [])):
                    return False
                if any(c and c[0] in ("PICKUP", "PLACE") and len(c) > 1 and c[1] == "SHEEP" for c in [a.get("farmer")] + a.get("hands", [])):
                    return False
        return True

    gs._v233_eligible = universal_v233_eligible
    
    routes = payload.load_routes()
    base_agent = chassis.make_agent(routes, router=router.router, **config.CHASSIS_SETTINGS)
    agent = guards.wrap_apex_guards(base_agent)
    return agent

def test_seed(seed):
    agent = build_test_agent()
    env = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([agent, "starter"])
    r = env.steps[-1][0]["reward"] or 0
    obs = env.steps[-1][0]["observation"]
    f = obs["farms"][0]
    quads = len(f["unlocked_quadrants"])
    cows = sum(1 for row in f["tiles"] for t in row if isinstance(t, dict) and t.get("animal") == "COW")
    sheep = sum(1 for row in f["tiles"] for t in row if isinstance(t, dict) and t.get("animal") == "SHEEP")
    shops = obs.get("town", {}).get("unlocked_shops", [])
    return seed, r, quads, cows, sheep, shops[:3]

def main():
    seeds = [7, 24, 6, 42, 1, 100, 2, 4, 9, 10]
    print(f"Testing Universal SE Expansion across {len(seeds)} seeds...")
    print(f"{'Seed':<6} | {'Reward':<10} | {'Quads':<6} | {'Cows':<5} | {'Sheep':<6} | Top Shops")
    print("-" * 65)
    
    for s in seeds:
        seed, r, quads, cows, sheep, shops = test_seed(s)
        print(f"{seed:<6} | ${r:<9,.0f} | {quads:<6} | {cows:<5} | {sheep:<6} | {shops}")

if __name__ == "__main__":
    main()
