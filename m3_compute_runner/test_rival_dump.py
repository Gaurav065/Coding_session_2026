#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Simulate Melon & Strawberry rival agents to test Market Crashing starvation."""

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kaggriculture_architecture"))

import kaggle_environments

def make_crop_rival(crop_name="MELON", plant_count=8):
    """An opponent that buys seeds, hires hands, plants, waters, harvests, and sells."""
    CROPS_INFO = {
        "MELON": {"seed": 80, "harvest_day": 12, "price": 250},
        "STRAWBERRY": {"seed": 100, "harvest_day": 10, "price": 120},
        "TOMATO": {"seed": 50, "harvest_day": 8, "price": 60},
    }
    info = CROPS_INFO[crop_name]
    
    def rival_agent(obs):
        farms = obs.get("farms", [])
        player = obs.get("player", 0)
        private = obs.get("private", {}) or {}
        if not farms or player >= len(farms):
            return {"farmer": ["PASS"], "hands": [], "market": []}
        farm = farms[player]
        day = obs.get("day", 0)
        hour = obs.get("hour", 0)
        seeds = private.get("seeds", {})
        shed = private.get("shed", {})
        
        market = []
        # Sell harvest when available in shed
        if shed.get(crop_name, 0) > 0:
            market.append(["SELL", crop_name, shed[crop_name]])
            
        # Buy seeds early on Day 0
        if day == 0 and hour == 0:
            market.append(["BUY_SEED", crop_name, plant_count])
            
        # Hire 1 hand on days 1-15 for watering
        if 1 <= day <= 15 and hour == 0 and farm["money"] > 10:
            market.append(["HIRE"])
            
        # Worker logic
        farmer = ["PASS"]
        hands = [["PASS"] for _ in farm.get("hands", [])]
        
        fx, fy = farm["farmer"]
        tile = farm["tiles"][fy][fx]
        
        # Simple farmer: walk to empty tile, plant, water
        if tile is None and seeds.get(crop_name, 0) > 0:
            farmer = ["PLANT", crop_name]
        elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
            age = day - tile.get("planted_day", 0)
            if age >= info["harvest_day"] and tile.get("yield_units", 0) > 0:
                farmer = ["HARVEST"]
            elif not tile.get("watered_today"):
                farmer = ["WATER"]
            else:
                # move to next tile
                farmer = ["EAST"] if fx < 4 else ["SOUTH"]
        else:
            if fx < 4:
                farmer = ["EAST"]
            elif fy < 4:
                farmer = ["SOUTH"]
                
        # Drop if shed adjacent and carrying
        invs = private.get("inventories", [])
        if len(invs) > 0 and invs[0].get(crop_name, 0) > 0:
            if (fx, fy) in [(4, 4), (5, 4), (4, 5), (5, 5)]:
                farmer = ["DROP"]
            else:
                # walk to shed
                farmer = ["SOUTH"] if fy < 4 else (["NORTH"] if fy > 5 else (["EAST"] if fx < 4 else ["WEST"]))

        return {"farmer": farmer, "hands": hands, "market": market}

    return rival_agent

if __name__ == "__main__":
    from modular_apex import chassis, config, payload, router
    from develop_crop_pizza_dump_engine import build_sanitized_route0, build_route13_pizza_se_expansion

    routes = payload.load_routes()
    r0 = build_sanitized_route0(routes[0])
    r13 = build_route13_pizza_se_expansion(r0)
    test_routes = copy.deepcopy(routes)
    test_routes[0] = r0
    test_routes[13] = r13

    def test_router(obs, step, st):
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

    agent_base = chassis.make_agent(test_routes, router=test_router, **config.CHASSIS_SETTINGS)
    melon_rival = make_crop_rival("MELON", plant_count=8)

    env = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
    env.run([agent_base, melon_rival])
    p0 = env.steps[-1][0]["reward"]
    p1 = env.steps[-1][1]["reward"]
    print(f"Game vs Melon Rival: Our Agent = ${p0:,.0f} | Rival = ${p1:,.0f}")
