#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test and evaluate the Mass Market Dumping Starvation Layer."""

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kaggriculture_architecture"))

import kaggle_environments
from modular_apex import chassis, config, payload, router
from develop_crop_pizza_dump_engine import build_sanitized_route0, build_route13_pizza_se_expansion
from test_rival_dump import make_crop_rival

CRASH_ITEMS = {
    "MELON": {"min_age": 9, "dump_trigger_price": 20},
    "STRAWBERRY": {"min_age": 8, "dump_trigger_price": 15},
    "TOMATO": {"min_age": 7, "dump_trigger_price": 10},
    "CARROT": {"min_age": 2, "dump_trigger_price": 5},
    "MILK": {"animal": "COW", "dump_trigger_price": 15},
    "WOOL": {"animal": "SHEEP", "dump_trigger_price": 15},
}

def apply_market_crash_dump(action, view, projected, max_orders=10):
    """Detects opponent crops/livestock near maturity and dumps shed inventory to crash prices."""
    rival_tiles = _get(view.rival, "tiles", []) or []
    if not rival_tiles:
        return
        
    day = int(_get(view.farm, "planted_day", 0)) if hasattr(view, "day") else 0
    # Collect opponent mature crops and livestock
    rival_threats = set()
    for row in rival_tiles:
        for tile in row:
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            if kind == "PLANT":
                crop = tile.get("crop")
                yield_units = tile.get("yield_units", 0)
                if crop in CRASH_ITEMS:
                    if yield_units > 0:
                        rival_threats.add(crop)
            elif kind in ("COOP", "PASTURE"):
                animal = tile.get("animal")
                yield_units = tile.get("yield_units", 0)
                if animal == "COW" and yield_units > 0:
                    rival_threats.add("MILK")
                elif animal == "SHEEP" and yield_units > 0:
                    rival_threats.add("WOOL")

    if not rival_threats:
        return

    # Check if we hold any of these products in shed
    market = action.setdefault("market", [])
    dump_orders = []
    
    for item in rival_threats:
        cfg_item = CRASH_ITEMS.get(item, {})
        min_price = cfg_item.get("dump_trigger_price", 10)
        curr_price = view.prices.get(item, 0)
        avail = projected.get(item, 0)
        
        if avail > 0 and curr_price >= min_price:
            # Check if order already queued
            already_queued = sum(o[2] for o in market if o and o[0] == "SELL" and o[1] == item)
            to_dump = avail - already_queued
            if to_dump > 0:
                dump_qty = min(to_dump, 10)
                dump_orders.append(["SELL", item, dump_qty])
                projected[item] -= dump_qty

    if dump_orders:
        # Prepend dump orders so they execute first in the AMM market queue
        existing = [o for o in market if not (o and o[0] == "SELL" and o[1] in rival_threats)]
        action["market"] = (dump_orders + existing)[:max_orders]

def _get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)

def run_simulation():
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

    # 1. Base agent (without crashing)
    agent_base = chassis.make_agent(test_routes, router=test_router, **config.CHASSIS_SETTINGS)
    
    # 2. Crash agent (with crashing enabled)
    # Wrap agent_base with market crash logic
    def crashing_agent(obs, configuration=None):
        act = agent_base(obs, configuration)
        step = obs.get("step", 0)
        player = obs.get("player", 0)
        view = chassis._View(obs, player, agent_base.chassis.cfg)
        projected = agent_base.chassis._projected_shed(act, view)
        apply_market_crash_dump(act, view, projected)
        return act

    # Run vs Melon Rival
    for seed in [42, 100, 2026]:
        melon_rival = make_crop_rival("MELON", plant_count=10)
        
        # Test Base vs Rival
        env_base = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env_base.run([agent_base, melon_rival])
        r_base_us = env_base.steps[-1][0]["reward"]
        r_base_rival = env_base.steps[-1][1]["reward"]
        
        # Test Crashing vs Rival
        env_crash = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env_crash.run([crashing_agent, melon_rival])
        r_crash_us = env_crash.steps[-1][0]["reward"]
        r_crash_rival = env_crash.steps[-1][1]["reward"]
        
        print(f"Seed {seed:4d} | Base: Us=${r_base_us:,.0f} Rival=${r_base_rival:,.0f} | Crash: Us=${r_crash_us:,.0f} Rival=${r_crash_rival:,.0f} (Rival reduced by ${r_base_rival - r_crash_rival:,.0f})")

if __name__ == "__main__":
    run_simulation()
