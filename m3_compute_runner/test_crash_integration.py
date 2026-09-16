#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Test _market_crash_dump integration in Chassis against pass, starter, and rivals."""

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "kaggriculture_architecture"))

import kaggle_environments
from modular_apex import chassis, config, payload, router
from develop_crop_pizza_dump_engine import build_sanitized_route0, build_route13_pizza_se_expansion
from test_rival_dump import make_crop_rival

def test_chassis_with_crash():
    # 1. Update CHASSIS_SETTINGS to include market_crash
    cfg = dict(config.CHASSIS_SETTINGS)
    cfg["market_crash"] = True

    # 2. Build sanitized routes
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

    # Monkey-patch _market_crash_dump into Chassis if not already present
    def _market_crash_dump(self, action, view, projected, route, step, next_sup):
        cfg = self.cfg
        if step > chassis.LAST_ACT_STEP or not view.rival:
            return

        rival_tiles = chassis._get(view.rival, "tiles", []) or []
        day = step // cfg["turns_per_day"]
        vulnerable_items = set()

        for row in rival_tiles:
            for tile in row:
                if not isinstance(tile, dict):
                    continue
                kind = chassis._get(tile, "kind")
                if kind == "PLANT":
                    crop = chassis._get(tile, "crop")
                    yield_units = chassis._int(chassis._get(tile, "yield_units", 0))
                    age = day - chassis._int(chassis._get(tile, "planted_day", 0))
                    if (crop == "MELON" and (yield_units > 0 or age >= 9) or
                        crop == "STRAWBERRY" and (yield_units > 0 or age >= 8) or
                        crop == "TOMATO" and (yield_units > 0 or age >= 7) or
                        crop == "CARROT" and (yield_units > 0 or age >= 2)):
                        vulnerable_items.add(crop)
                elif kind in ("COOP", "PASTURE"):
                    animal = chassis._get(tile, "animal")
                    yield_units = chassis._int(chassis._get(tile, "yield_units", 0))
                    if animal == "COW" and (yield_units > 0 or chassis._get(tile, "fed_today")):
                        vulnerable_items.add("MILK")
                    elif animal == "SHEEP" and (yield_units > 0 or chassis._get(tile, "fed_today")):
                        vulnerable_items.add("WOOL")

        rival_pos = [chassis._get(view.rival, "farmer", None)] + list(chassis._get(view.rival, "hands", []) or [])
        rival_near_shed = any(chassis._shed_adjacent(p, view.board) for p in rival_pos if p)

        dump_orders = []
        for item in ("MELON", "STRAWBERRY", "MILK", "WOOL", "TOMATO", "CARROT"):
            if item not in vulnerable_items and not rival_near_shed:
                continue
            price = view.prices.get(item, 0)
            if price < 10:
                continue
            avail = projected.get(item, 0)
            if avail <= 0:
                continue
            qty = min(avail, 10)
            if qty <= 0:
                continue
            dump_orders.append(["SELL", item, qty])
            projected[item] -= qty
            next_sup["suppress"][item] = next_sup["suppress"].get(item, 0) + qty

        if dump_orders:
            next_sup["due_step"] = step + 1
            market = action.setdefault("market", [])
            other_orders = [o for o in market if not (o and o[0] == "SELL" and o[1] in vulnerable_items)]
            action["market"] = (dump_orders + other_orders)[:cfg["max_orders"]]

    chassis.Chassis._market_crash_dump = _market_crash_dump

    # Patch Chassis.act to call _market_crash_dump
    orig_act = chassis.Chassis.act
    def patched_act(self, observation, configuration=None):
        step = chassis._step_of(observation)
        player = chassis._int(chassis._get(observation, "player", 0))
        st = self._state(player, step)
        cfg = self.cfg
        view = chassis._View(observation, player, cfg)
        
        # Call original act
        act = orig_act(self, observation, configuration)
        
        # If market_crash enabled, apply dump check
        if cfg.get("market_crash", True):
            projected = self._projected_shed(act, view)
            next_sup = st.get("sell_state", {"due_step": -1, "suppress": {}})
            self._market_crash_dump(act, view, projected, st.get("route", 0), step, next_sup)
            st["sell_state"] = next_sup
            
        return act

    chassis.Chassis.act = patched_act

    agent = chassis.make_agent(test_routes, router=test_router, **cfg)

    # Test 1: Solo vs Pass on standard seeds
    print("Testing Agent vs Pass across 5 seeds...")
    pass_scores = []
    for s in [42, 100, 2026, 7, 24]:
        env = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([agent, "pass"])
        r = env.steps[-1][0]["reward"] or 0
        shed = env.steps[-1][0]["observation"]["private"]["shed"]
        trapped = shed.get("COW", 0) + shed.get("SHEEP", 0) + shed.get("GOOSE", 0)
        pass_scores.append(r)
        print(f"  Seed {s:4d}: Reward = ${r:,.0f} | Trapped Animals = {trapped}")
    print(f"Average vs Pass: ${sum(pass_scores)/len(pass_scores):,.0f}")

    # Test 2: Agent vs Melon Rival
    print("\nTesting Agent vs Melon Rival...")
    melon_rival = make_crop_rival("MELON", plant_count=10)
    env2 = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
    env2.run([agent, melon_rival])
    print(f"  Seed 42 vs Melon Rival: Us = ${env2.steps[-1][0]['reward']:,.0f} | Rival = ${env2.steps[-1][1]['reward']:,.0f}")

    # Test 3: Agent vs Strawberry Rival
    print("\nTesting Agent vs Strawberry Rival...")
    straw_rival = make_crop_rival("STRAWBERRY", plant_count=8)
    env3 = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": 42})
    env3.run([agent, straw_rival])
    print(f"  Seed 42 vs Strawberry Rival: Us = ${env3.steps[-1][0]['reward']:,.0f} | Rival = ${env3.steps[-1][1]['reward']:,.0f}")

if __name__ == "__main__":
    test_chassis_with_crash()
