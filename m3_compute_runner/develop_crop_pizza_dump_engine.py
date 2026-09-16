#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Develop and optimize:
1. No-Goose / Tomato Pivot on Route 0
2. Route 13: 4th-Tile SE Quadrant Expansion (PIZZA_SHOP >= 2)
3. Opponent Starvation via Mass Market Dumping
"""

import copy
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kaggriculture_architecture"))

import kaggle_environments
from modular_apex import chassis, config, payload, router

def build_sanitized_route0(base_tape):
    """Replaces all Goose and Coop actions with ongoing Tomatoes and Crop care."""
    tape = copy.deepcopy(base_tape)
    tape[0] = dict(tape[0], market=[list(o) for o in config.CLEAN_OPENING])
    
    for step in range(len(tape)):
        act = tape[step]
        # Market updates
        new_market = []
        for order in act.get("market", []):
            if not order:
                continue
            op = order[0]
            if op == "BUY_ANIMAL" and len(order) >= 2 and order[1] == "GOOSE":
                # Replace goose purchase with tomato seeds + fertilizer
                qty = order[2] if len(order) >= 3 else 1
                new_market.append(["BUY_SEED", "TOMATO", qty * 2])
                new_market.append(["BUY_PRODUCT", "FERTILIZER", qty])
            elif op == "SELL" and len(order) >= 2 and order[1] == "EGG":
                # Replace egg sales with tomato sales
                qty = order[2] if len(order) >= 3 else 1
                new_market.append(["SELL", "TOMATO", qty])
            else:
                new_market.append(order)
        tape[step]["market"] = new_market

        # Farmer replacements
        f = act.get("farmer", [])
        if f:
            if f[0] == "BUILD_COOP":
                tape[step]["farmer"] = ["PLANT", "TOMATO"]
            elif f[0] in ("PLACE", "PICKUP") and len(f) >= 2 and f[1] == "GOOSE":
                tape[step]["farmer"] = ["WATER"]

        # Hands replacements
        new_hands = []
        for h in act.get("hands", []):
            if not h:
                new_hands.append(h)
                continue
            op = h[0]
            if op == "BUILD_COOP":
                new_hands.append(["PLANT", "TOMATO"])
            elif op in ("PLACE", "PICKUP") and len(h) >= 2 and h[1] == "GOOSE":
                new_hands.append(["WATER"])
            else:
                new_hands.append(h)
        tape[step]["hands"] = new_hands

    return tape

def build_route13_pizza_se_expansion(sanitized_tape):
    """Creates Route 13: unlocks SE Quadrant ($4,000) for mass Tomato/Milk production."""
    tape = copy.deepcopy(sanitized_tape)
    
    # At Step 312 (Day 13, Hour 0), queue the 3rd BUY_LAND ($4,000 for SE quadrant)
    # and buy Tomato + Wheat seeds for the newly opened 25 tiles
    step_unlock = 312
    act = tape[step_unlock]
    m = act.get("market", [])
    # Insert BUY_LAND at beginning of market orders
    m = [["BUY_LAND"], ["BUY_SEED", "TOMATO", 6], ["BUY_SEED", "WHEAT", 4]] + [o for o in m if o and o[0] != "BUY_LAND"]
    tape[step_unlock]["market"] = m[:10]

    # Additional Tomato seeds on Day 14 (Step 336)
    step_seeds = 336
    act2 = tape[step_seeds]
    m2 = act2.get("market", [])
    m2 = [["BUY_SEED", "TOMATO", 6]] + m2
    tape[step_seeds]["market"] = m2[:10]

    # Guide farmer / hands to plant and water on SE tiles when standing near (5,5)
    for s in range(step_unlock + 1, min(step_unlock + 72, len(tape))):
        act_s = tape[s]
        # If any hand is passing, encourage planting / watering
        new_h = []
        for h in act_s.get("hands", []):
            if h and h[0] == "PASS" and s % 4 == 0:
                new_h.append(["WATER"])
            elif h and h[0] == "PASS" and s % 5 == 0:
                new_h.append(["HARVEST"])
            else:
                new_h.append(h)
        tape[s]["hands"] = new_h

    # Add extra Tomato sales during mid-late game into Pizza demand
    for s in range(360, len(tape), 12):
        act_s = tape[s]
        m = act_s.get("market", [])
        if len(m) < 10:
            m.append(["SELL", "TOMATO", 4])
        tape[s]["market"] = m

    return tape

def run_evaluation():
    routes = payload.load_routes()
    base_tape = routes[0]
    
    print("1. Generating Sanitized Route 0 (No Geese, Ongoing Tomatoes)...")
    clean_r0 = build_sanitized_route0(base_tape)
    
    print("2. Generating Route 13 (Pizza 2+ SE Quadrant Expansion)...")
    r13 = build_route13_pizza_se_expansion(clean_r0)
    
    test_routes = copy.deepcopy(routes)
    test_routes[0] = clean_r0
    test_routes[13] = r13
    
    # Custom router with Pizza >= 2 detection
    def enhanced_router(obs, step, st):
        if step >= config.FINAL_PLAN_STEP and not st.get("day27"):
            st["route"] = 2
            st["day27"] = True
            return 2
            
        shops = (obs.get("town", {}) or {}).get("unlocked_shops", []) or []
        if shops.count("PIZZA_SHOP") >= 2:
            st["route"] = 13
            return 13
            
        if step >= config.ROUTE_STEP and not st.get("day6"):
            pair = tuple(shops[:2])
            st["route"] = router.SHOP_PLANS.get(pair, 0)
            st["day6"] = True
            
        return st.get("route", 0)

    agent = chassis.make_agent(test_routes, router=enhanced_router, **config.CHASSIS_SETTINGS)
    
    # Test on standard seeds AND Pizza seeds
    test_seeds = [42, 100, 2026, 7, 24]
    print(f"\nEvaluating Enhanced Agent across seeds {test_seeds}...")
    
    total_rewards = []
    for s in test_seeds:
        env = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "pass"])
        r = env.steps[-1][0]["reward"] or 0
        shed = env.steps[-1][0]["observation"]["private"]["shed"]
        shops = env.steps[-1][0]["observation"]["town"]["unlocked_shops"]
        pizzas = shops.count("PIZZA_SHOP")
        trapped = shed.get("COW", 0) + shed.get("SHEEP", 0) + shed.get("GOOSE", 0)
        total_rewards.append(r)
        print(f"Seed {s:4d} (Pizzas: {pizzas}): Reward = ${r:,.0f} | Trapped Animals = {trapped}")
        
    avg_reward = sum(total_rewards) / len(total_rewards)
    print("=" * 65)
    print(f"Average Reward: ${avg_reward:,.0f} | Peak: ${max(total_rewards):,.0f}")
    print("=" * 65)

if __name__ == "__main__":
    run_evaluation()
