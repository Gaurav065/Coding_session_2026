#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prototype and benchmark dedicated SE Tomato & Wheat planting corridor on Route 13."""

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kaggriculture_architecture"))

import kaggle_environments
from modular_apex import chassis, config, payload, router, guards
from develop_crop_pizza_dump_engine import build_sanitized_route0

def build_advanced_route13(base_tape):
    tape = copy.deepcopy(base_tape)
    
    # 1. Step 312: Unlock SE Quadrant and buy seeds
    step_unlock = 312
    act = tape[step_unlock]
    m = act.get("market", [])
    m = [["BUY_LAND"], ["BUY_SEED", "TOMATO", 6], ["BUY_SEED", "WHEAT", 4]] + [o for o in m if o and o[0] != "BUY_LAND"]
    tape[step_unlock]["market"] = m[:10]
    
    # The SE corridor path of 6 tiles:
    # (5,5), (6,5), (6,6), (5,6), (5,7), (6,7)
    # Target crops: 4 Tomatoes on (5,5), (6,5), (6,6), (5,6); 2 Wheat on (5,7), (6,7)
    
    # Let's program Hand 3 (or the worker spawning at (5,5)) on Day 13 (steps 313 to 335)
    # Day 13: Plant the corridor
    plant_seq = [
        ["PLANT", "TOMATO"],  # at (5,5)
        ["EAST"],             # to (6,5)
        ["PLANT", "TOMATO"],  # at (6,5)
        ["SOUTH"],            # to (6,6)
        ["PLANT", "TOMATO"],  # at (6,6)
        ["WEST"],             # to (5,6)
        ["PLANT", "TOMATO"],  # at (5,6)
        ["SOUTH"],            # to (5,7)
        ["PLANT", "WHEAT"],   # at (5,7)
        ["EAST"],             # to (6,7)
        ["PLANT", "WHEAT"],   # at (6,7)
        ["WEST"],             # back to (5,7)
        ["NORTH"],            # back to (5,6)
        ["NORTH"],            # back to (5,5) - shed door!
        ["DROP"],
        ["PASS"]
    ]
    
    for idx, cmd in enumerate(plant_seq):
        s = step_unlock + 1 + idx
        if s < len(tape):
            hands = tape[s].get("hands", [])
            # Target hand index 3 (starts at (5,5))
            if len(hands) > 3:
                hands[3] = list(cmd)
                tape[s]["hands"] = hands

    # Days 14 to 26: Water & Harvest corridor
    # Loop over days:
    for day in range(14, 27):
        day_start = day * 24
        # Add 1 hire if needed on day_start
        if day_start < len(tape):
            m = tape[day_start].get("market", [])
            if len(m) < 10:
                m = [["HIRE"]] + m
                tape[day_start]["market"] = m[:10]
                
        # Serpentine water sequence:
        water_seq = [
            ["WATER"],   # at (5,5)
            ["EAST"],    # to (6,5)
            ["WATER"],   # at (6,5)
            ["SOUTH"],   # to (6,6)
            ["WATER"],   # at (6,6)
            ["WEST"],    # to (5,6)
            ["WATER"],   # at (5,6)
            ["SOUTH"],   # to (5,7)
            ["WATER"],   # at (5,7)
            ["EAST"],    # to (6,7)
            ["WATER"],   # at (6,7)
            ["WEST"],    # back to (5,7)
            ["NORTH"],   # back to (5,6)
            ["NORTH"],   # back to (5,5) shed access!
            ["HARVEST"] if day >= 21 else ["DROP"],
            ["DROP"],
            ["PASS"]
        ]
        for idx, cmd in enumerate(water_seq):
            s = day_start + 1 + idx
            if s < len(tape):
                hands = tape[s].get("hands", [])
                if len(hands) > 3:
                    hands[3] = list(cmd)
                    tape[s]["hands"] = hands

    # Sell extra tomatoes into pizza shop demand throughout mid-late game
    for s in range(360, len(tape), 12):
        act_s = tape[s]
        m = act_s.get("market", [])
        if len(m) < 10:
            m.append(["SELL", "TOMATO", 4])
        tape[s]["market"] = m

    return tape

def evaluate():
    routes = payload.load_routes()
    r0 = build_sanitized_route0(routes[0])
    adv_r13 = build_advanced_route13(r0)
    
    test_routes = copy.deepcopy(routes)
    test_routes[0] = r0
    test_routes[13] = adv_r13
    
    def test_router(obs, step, st):
        if step >= config.FINAL_PLAN_STEP:
            st["route"] = 2
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

    base_agent = chassis.make_agent(test_routes, router=test_router, **config.CHASSIS_SETTINGS)
    agent = guards.wrap_apex_guards(base_agent)
    
    print("Evaluating Advanced Route 13 on Pizza Seeds (42, 100, 24)...")
    for s in [42, 100, 24]:
        env = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "pass"])
        obs = env.steps[-1][0]["observation"]
        r = env.steps[-1][0]["reward"] or 0
        shed = obs["private"]["shed"]
        trapped = shed.get("COW", 0) + shed.get("SHEEP", 0) + shed.get("GOOSE", 0)
        quads = obs["farms"][0]["unlocked_quadrants"]
        print(f"Seed {s:4d}: Reward = ${r:,.0f} | Trapped Animals = {trapped} | Quads = {quads}")

if __name__ == "__main__":
    evaluate()
