"""Throughput Experiment §2y: Crop Crew Auto-Flush Field Retention

Tests removing the hour >= 16/18 and carrying_produce >= 15 walk-to-shed interruption
for crop crews (units 4..12), relying on engine:843 _drop_inventories_to_shed auto-flush.

Evaluates:
- Candidate 0: Baseline (current production behavior)
- Candidate 1: Task Priority (work sector tasks first; only walk to shed if idle with produce)
- Candidate 2: Pure Field Retention (never walk to shed on days < 29; opportunistic drop if adjacent; auto-flush at midnight)
- Candidate 3: High Capacity Buffer (only walk to shed if carrying >= 50 items or idle)

Tested with standing canaries (Pass Baseline and Identity Control).
"""

import sys
import os
import time
import numpy as np
from scipy import stats
from typing import Tuple, List, Dict, Any, Optional
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent, make_spatial_dispatcher_agent,
    COW_PASTURES, SHEEP_PASTURES, GOOSE_COOPS, NW_WHEAT, NE_STRAWBERRY, NE_WHEAT, SW_MELON, SW_WHEAT,
    GLUT_RESISTANT, GLUT_PRONE, BASE_PRICES
)

OFFICIAL_20 = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
               250, 300, 333, 404, 500, 600, 700, 777, 888, 999]
DISJOINT_100 = list(range(10000, 10100))


class ThroughputCropAgent(MaestroFullPortfolioAgent):
    def __init__(self,
                 crop_drop_mode: str = "baseline", # "baseline", "task_first", "pure_field", "high_cap"
                 **kwargs):
        super().__init__(**kwargs)
        self.crop_drop_mode = crop_drop_mode

    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        # Exact copy of production __call__ with parameterized crop crew drop logic
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        day = obs["day"]
        hour = obs["hour"]
        money = me["money"]
        unlocked_quads = set(me.get("unlocked_quadrants", []))
        market_prices = obs.get("market", {}).get("prices", {})
        unlocked_shops = obs.get("town", {}).get("unlocked_shops", [])
        has_yarn_store = ("YARN_STORE" in unlocked_shops)

        if not self._planned_steering and day == 0:
            if self.seed is None and "seed" in obs:
                self.seed = obs["seed"]
            if self.seed is not None:
                self.kw_early = 10  # unsteered
            else:
                self.kw_early = 10
            self._planned_steering = True

        if day < 3:
            kw = self.kw_early if self.kw_early is not None else 10
            self.nw_wheat = list(NW_WHEAT[:kw])
        else:
            self.nw_wheat = list(NW_WHEAT)

        MILK_SHOPS = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}
        milk_shop_count = sum(1 for s in unlocked_shops if s in MILK_SHOPS)

        market_orders = []

        if day >= 29:
            target_crew = 7
        elif day < 3:
            target_crew = 6
        elif day < 8:
            target_crew = 8
        elif "SW" in unlocked_quads:
            target_crew = self.params["crew_late"]
        else:
            target_crew = self.params["crew_mid"]

        placed_animals = []
        for py in range(5):
            for px in range(5):
                t = me["tiles"][py][px]
                if isinstance(t, dict) and ("animal" in t):
                    placed_animals.append((px, py, t["animal"]))

        placed_c = sum(1 for _, _, a in placed_animals if a == "COW")
        placed_g = sum(1 for _, _, a in placed_animals if a == "GOOSE")
        placed_s = sum(1 for _, _, a in placed_animals if a == "SHEEP")

        shed = private.get("shed", {})
        shed_total_items = sum(shed.values())
        shed_c = shed.get("COW", 0)
        shed_g = shed.get("GOOSE", 0)
        shed_s = shed.get("SHEEP", 0)
        carried_c = sum(inv.get("COW", 0) for inv in private.get("inventories", []))
        carried_g = sum(inv.get("GOOSE", 0) for inv in private.get("inventories", []))
        carried_s = sum(inv.get("SHEEP", 0) for inv in private.get("inventories", []))

        total_c = placed_c + shed_c + carried_c
        total_g = placed_g + shed_g + carried_g
        total_s = placed_s + shed_s + carried_s
        shed_wheat = shed.get("WHEAT", 0)

        # 1. Market Operations
        if hour == 0:
            current_hands = len(me.get("hands", []))
            needed_hires = max(0, target_crew - current_hands)
            for _ in range(needed_hires):
                market_orders.append(["HIRE"])

            if day == 0:
                market_orders.append(["BUY_SEED", "WHEAT", 10])
                market_orders.append(["BUY_PRODUCT", "WHEAT", 10])
                market_orders.append(["BUY_ANIMAL", "COW", 4])
                market_orders.append(["BUY_ANIMAL", "SHEEP", 1])

        if day < 29 and shed_wheat == 0 and money >= 120:
            if len(market_orders) < 8:
                market_orders.append(["BUY_PRODUCT", "WHEAT", 6])

        if len(market_orders) < 8:
            if "NE" not in unlocked_quads and money >= 1000:
                market_orders.append(["BUY_LAND"])
            elif "NE" in unlocked_quads and "SW" not in unlocked_quads and money >= 2000 and day >= 6:
                market_orders.append(["BUY_LAND"])

            if "NE" in unlocked_quads and day < 20:
                strawberry_plants = 0
                for sx, sy in self.ne_strawberry:
                    t = me["tiles"][sy][sx]
                    if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "STRAWBERRY":
                        strawberry_plants += 1
                straw_needed = max(0, self.params["strawberry_target"] - strawberry_plants
                                    - private["seeds"].get("STRAWBERRY", 0))
                if straw_needed > 0 and money >= 300:
                    buy_straw = min(straw_needed, int((money - 100) // 300))
                    if buy_straw > 0:
                        market_orders.append(["BUY_SEED", "STRAWBERRY", min(4, buy_straw)])

            melon_target = self.params["melon_seed_target"]
            if "SW" in unlocked_quads and private["seeds"].get("MELON", 0) < melon_target and money >= 300 and day < 16:
                market_orders.append(["BUY_SEED", "MELON", melon_target])

            if private["seeds"].get("WHEAT", 0) < 40 and money >= 300 and day < 28:
                market_orders.append(["BUY_SEED", "WHEAT", 40])

            if day >= 18 and day < 27 and private["seeds"].get("CARROT", 0) < 16 and money >= 350:
                market_orders.append(["BUY_SEED", "CARROT", 16])

            allow_animal_expansion = ("SW" in unlocked_quads or day >= 10)
            if allow_animal_expansion:
                goose_cap = self.params["goose_cap"]
                if total_g < goose_cap and money >= 600 and shed_total_items <= 90 and day < 16:
                    buy_g = min(goose_cap - total_g, int((money - 300) // 300))
                    if buy_g > 0:
                        market_orders.append(["BUY_ANIMAL", "GOOSE", min(2, buy_g)])

                if day >= self.params.get("cow_gate_day_early", 99) and milk_shop_count == 0:
                    cow_cap = self.params.get("cow_cap_zero", 4)
                elif day >= self.params.get("cow_gate_day_mid", 99) and milk_shop_count <= 1:
                    cow_cap = self.params.get("cow_cap_low", 6)
                elif day >= 15 and milk_shop_count <= 1:
                    cow_cap = self.params["cow_cap_low"]
                else:
                    cow_cap = self.params["cow_cap_base"]
                if total_c < cow_cap and money >= 700 and shed_total_items <= 90 and day < 18:
                    buy_c = min(cow_cap - total_c, int((money - 300) // 400))
                    if buy_c > 0:
                        market_orders.append(["BUY_ANIMAL", "COW", min(2, buy_c)])

                else:
                    sheep_cap = self.params["sheep_cap"]
                    if has_yarn_store and total_s < sheep_cap and money >= 800 and shed_total_items <= 90 and day < 20:
                        buy_s = min(sheep_cap - total_s, int((money - 300) // 500))
                        if buy_s > 0:
                            market_orders.append(["BUY_ANIMAL", "SHEEP", min(2, buy_s)])

        # 2. Adaptive AMM Selling
        shed_near_overflow = shed_total_items >= 85
        for prod in ["EGG", "MILK", "WOOL", "STRAWBERRY", "MELON", "FERTILIZER", "CARROT", "TOMATO"]:
            qty = shed.get(prod, 0)
            if qty <= 0:
                continue
            base_price = BASE_PRICES.get(prod, 10)
            cur_price = market_prices.get(prod, base_price)
            price_ratio = cur_price / base_price if base_price else 1.0

            if day >= 28:
                sell_qty = qty
            elif prod == "FERTILIZER":
                sell_qty = qty
            elif prod in GLUT_RESISTANT:
                sell_qty = min(qty, 20)
            elif prod in GLUT_PRONE:
                if shed_near_overflow:
                    sell_qty = min(qty, 20)
                elif price_ratio >= 0.55:
                    sell_qty = min(qty, 4)
                else:
                    sell_qty = 0
            else:
                if price_ratio >= 0.65:
                    sell_qty = min(qty, 10)
                else:
                    sell_qty = min(qty, 5 if not shed_near_overflow else 20)

            if len(market_orders) < 10 and sell_qty > 0:
                market_orders.append(["SELL", prod, sell_qty])

        wheat_qty = shed.get("WHEAT", 0)
        if day >= 29 and hour >= 18 and wheat_qty > 0:
            if len(market_orders) < 10:
                market_orders.append(["SELL", "WHEAT", min(50, wheat_qty)])
        elif wheat_qty > 10:
            sell_amt = min(20, wheat_qty - 10)
            if len(market_orders) < 10 and sell_amt > 0:
                market_orders.append(["SELL", "WHEAT", sell_amt])

        # 3. Dynamic Sector Tasks
        nw_wheat_tasks_p1 = []
        nw_wheat_tasks_p2 = []
        for i, (wx, wy) in enumerate(self.nw_wheat):
            t = me["tiles"][wy][wx]
            task_list = nw_wheat_tasks_p1 if i < 5 else nw_wheat_tasks_p2
            if t is None and day < 28:
                task_list.append({"target": (wx, wy), "action": "PLANT_WHEAT", "crop": "WHEAT", "priority": 93})
            elif isinstance(t, dict) and t.get("kind") == "WEED":
                task_list.append({"target": (wx, wy), "action": "DIG", "priority": 30})
            elif isinstance(t, dict) and t.get("kind") == "PLANT":
                if not t.get("watered_today", False):
                    task_list.append({"target": (wx, wy), "action": "WATER", "priority": 95})
                if t.get("yield_units", 0) > 0 and (day - t.get("planted_day", 0)) >= 2:
                    task_list.append({"target": (wx, wy), "action": "HARVEST", "priority": 90})

        ne_tasks = []
        if "NE" in unlocked_quads:
            for sx, sy in self.ne_strawberry:
                t = me["tiles"][sy][sx]
                if t is None:
                    if day < 18:
                        ne_tasks.append({"target": (sx, sy), "action": "PLANT_STRAWBERRY", "crop": "STRAWBERRY", "priority": 95})
                    elif day < 28:
                        ne_tasks.append({"target": (sx, sy), "action": "PLANT_CARROT", "crop": "CARROT", "priority": 95})
                elif isinstance(t, dict) and t.get("kind") == "WEED":
                    ne_tasks.append({"target": (sx, sy), "action": "DIG", "priority": 45})
                elif isinstance(t, dict) and t.get("kind") == "PLANT":
                    crop = t.get("crop")
                    mls = t.get("max_lifespan_step", -1)
                    yields = t.get("yield_units", 0)
                    planted_day = t.get("planted_day", 0)

                    if crop == "STRAWBERRY":
                        if yields > 0:
                            ne_tasks.append({"target": (sx, sy), "action": "HARVEST", "priority": 98})
                        elif mls >= 0:
                            ne_tasks.append({"target": (sx, sy), "action": "DIG", "priority": 94})
                        elif not t.get("watered_today", False):
                            ne_tasks.append({"target": (sx, sy), "action": "WATER", "priority": 96})
                    elif crop == "CARROT":
                        if yields > 0 and (day - planted_day) >= 2:
                            ne_tasks.append({"target": (sx, sy), "action": "HARVEST", "priority": 98})
                        elif not t.get("watered_today", False):
                            ne_tasks.append({"target": (sx, sy), "action": "WATER", "priority": 96})
                    else:
                        if yields > 0 and (day - planted_day) >= 2:
                            ne_tasks.append({"target": (sx, sy), "action": "HARVEST", "priority": 98})
                        elif not t.get("watered_today", False):
                            ne_tasks.append({"target": (sx, sy), "action": "WATER", "priority": 96})

            for wx, wy in self.ne_wheat:
                t = me["tiles"][wy][wx]
                if t is None and day < 28:
                    ne_tasks.append({"target": (wx, wy), "action": "PLANT_WHEAT", "crop": "WHEAT", "priority": 93})
                elif isinstance(t, dict) and t.get("kind") == "WEED":
                    ne_tasks.append({"target": (wx, wy), "action": "DIG", "priority": 30})
                elif isinstance(t, dict) and t.get("kind") == "PLANT":
                    if not t.get("watered_today", False):
                        ne_tasks.append({"target": (wx, wy), "action": "WATER", "priority": 92})
                    if t.get("yield_units", 0) > 0 and (day - t.get("planted_day", 0)) >= 2:
                        ne_tasks.append({"target": (wx, wy), "action": "HARVEST", "priority": 90})

        sw_tasks = []
        if "SW" in unlocked_quads:
            for mx, my in self.sw_melon:
                t = me["tiles"][my][mx]
                if t is None and day < 16:
                    sw_tasks.append({"target": (mx, my), "action": "PLANT_MELON", "crop": "MELON", "priority": 95})
                elif isinstance(t, dict) and t.get("kind") == "WEED":
                    sw_tasks.append({"target": (mx, my), "action": "DIG", "priority": 45})
                elif isinstance(t, dict) and t.get("kind") == "PLANT":
                    if not t.get("watered_today", False):
                        sw_tasks.append({"target": (mx, my), "action": "WATER", "priority": 95})
                    if t.get("yield_units", 0) > 0 and (day - t.get("planted_day", 0)) >= 10:
                        sw_tasks.append({"target": (mx, my), "action": "HARVEST", "priority": 97})

            for wx, wy in self.sw_wheat:
                t = me["tiles"][wy][wx]
                if t is None and day < 28:
                    sw_tasks.append({"target": (wx, wy), "action": "PLANT_WHEAT", "crop": "WHEAT", "priority": 93})
                elif isinstance(t, dict) and t.get("kind") == "WEED":
                    sw_tasks.append({"target": (wx, wy), "action": "DIG", "priority": 30})
                elif isinstance(t, dict) and t.get("kind") == "PLANT":
                    if not t.get("watered_today", False):
                        sw_tasks.append({"target": (wx, wy), "action": "WATER", "priority": 92})
                    if t.get("yield_units", 0) > 0 and (day - t.get("planted_day", 0)) >= 2:
                        sw_tasks.append({"target": (wx, wy), "action": "HARVEST", "priority": 90})

        all_units = [me["farmer"]] + me.get("hands", [])
        unit_actions = []
        claimed_targets = set()
        is_endgame_flush = (day >= 29 and hour >= 18)
        SHED_ACCESS_TILES = [(4, 4), (5, 4), (4, 5), (5, 5)]

        avail_seeds = dict(private.get("seeds", {}))

        for u_idx, (ux, uy) in enumerate(all_units):
            inv = private["inventories"][u_idx] if u_idx < len(private["inventories"]) else {}
            pos = (ux, uy)
            current_tile = me["tiles"][uy][ux]
            action = ["PASS"]

            carrying_produce = sum(v for k, v in inv.items() if k not in ["COW", "SHEEP", "GOOSE"])
            carrying_animal = "COW" if inv.get("COW", 0) > 0 else ("GOOSE" if inv.get("GOOSE", 0) > 0 else ("SHEEP" if inv.get("SHEEP", 0) > 0 else None))
            wheat_count = inv.get("WHEAT", 0)

            # Assign Drop Tiles
            if u_idx == 0:
                default_drop_tile = (4, 4)
                my_cluster = [(4, 3), (4, 2), (4, 1), (4, 0)]
            elif u_idx == 1:
                default_drop_tile = (4, 4)
                my_cluster = [(3, 4), (3, 3), (3, 2), (3, 1)]
            elif u_idx == 2:
                default_drop_tile = (4, 4)
                my_cluster = [(2, 4), (2, 3), (2, 2)]
            elif u_idx == 3:
                default_drop_tile = (4, 4)
                my_cluster = [(1, 4), (1, 3), (0, 4)]
            elif u_idx in (4, 5):
                default_drop_tile = (4, 4)
                my_cluster = []
            elif u_idx in (6, 7, 8):
                default_drop_tile = (5, 4)
                my_cluster = []
            else:
                default_drop_tile = (4, 5)
                my_cluster = []

            # Endgame Rush
            if is_endgame_flush:
                if pos in SHED_ACCESS_TILES:
                    action = ["DROP"]
                else:
                    action = [self._get_step_towards(pos, default_drop_tile)]
                unit_actions.append(action)
                continue

            # =========================================================
            # SECTION A: SWEEP CREW (UNITS 0..3) - ANIMAL DEDICATED
            # =========================================================
            if u_idx < 4:
                if isinstance(current_tile, dict) and ("animal" in current_tile):
                    animal_type = current_tile.get("animal")
                    y_units = current_tile.get("yield_units", 0)

                    if not current_tile.get("fed_today", False) and wheat_count > 0:
                        action = ["FEED"]
                    elif not current_tile.get("cared_today", False):
                        action = ["CARE"]
                    elif animal_type == "GOOSE" and y_units >= 2:
                        action = ["HARVEST"]
                    elif (animal_type == "COW" and y_units >= 2) or (animal_type == "SHEEP" and y_units >= 3) or y_units >= 4:
                        action = ["HARVEST"]
                    elif current_tile.get("fertilizer_available", False):
                        action = ["COLLECT_FERTILIZER"]

                if action == ["PASS"] and pos in SHED_ACCESS_TILES:
                    if day < 18 and private["shed"].get("COW", 0) > 0 and not carrying_animal:
                        action = ["PICKUP", "COW", 1]
                    elif day < 18 and private["shed"].get("GOOSE", 0) > 0 and not carrying_animal:
                        action = ["PICKUP", "GOOSE", 1]
                    elif day < 18 and private["shed"].get("SHEEP", 0) > 0 and not carrying_animal:
                        action = ["PICKUP", "SHEEP", 1]
                    elif hour >= 16 and (carrying_produce - wheat_count) > 0:
                        action = ["DROP"]
                    elif wheat_count < 4 and shed_wheat > 0 and day < 30:
                        pickup_amt = min(5 - wheat_count, shed_wheat)
                        if pickup_amt > 0:
                            action = ["PICKUP", "WHEAT", pickup_amt]

                if action == ["PASS"] and carrying_animal:
                    if carrying_animal == "COW":
                        target_coords = self.cow_pastures
                        req_struct = "PASTURE"
                        build_act = "BUILD_PASTURE"
                    elif carrying_animal == "GOOSE":
                        target_coords = self.goose_coops
                        req_struct = "COOP"
                        build_act = "BUILD_COOP"
                    else:
                        target_coords = self.sheep_pastures
                        req_struct = "PASTURE"
                        build_act = "BUILD_PASTURE"

                    target_spot = None
                    for px, py in target_coords:
                        t = me["tiles"][py][px]
                        if isinstance(t, dict) and t.get("kind") == req_struct and "animal" not in t:
                            target_spot = (px, py)
                            break
                        elif t is None:
                            target_spot = (px, py)
                            break

                    if target_spot:
                        if pos == target_spot:
                            t = me["tiles"][uy][ux]
                            if t is None:
                                action = [build_act]
                            elif isinstance(t, dict) and t.get("kind") == req_struct:
                                action = ["PLACE", carrying_animal, 1]
                        else:
                            action = [self._get_step_towards(pos, target_spot)]

                if action == ["PASS"] and not carrying_animal:
                    if day < 18 and (shed_c > 0 or shed_g > 0 or shed_s > 0) and pos not in SHED_ACCESS_TILES and hour < 14:
                        action = [self._get_step_towards(pos, default_drop_tile)]
                    else:
                        best_target = None
                        best_score = -1e9

                        for px, py in my_cluster:
                            if (px, py) in claimed_targets:
                                continue
                            t = me["tiles"][py][px]
                            if isinstance(t, dict) and ("animal" in t):
                                is_unfed = (not t.get("fed_today", False))
                                is_uncared = (not t.get("cared_today", False))
                                has_fert = t.get("fertilizer_available", False)
                                has_yield = (t.get("yield_units", 0) >= 2)

                                if (is_unfed and wheat_count > 0) or is_uncared or has_fert or has_yield:
                                    priority = 100 if is_unfed else (90 if is_uncared else 80)
                                    score = priority * 10 - self._dist(pos, (px, py))
                                    if score > best_score:
                                        best_score = score
                                        best_target = (px, py)

                        if not best_target:
                            for px, py in self.cow_pastures + self.goose_coops:
                                if (px, py) in claimed_targets:
                                    continue
                                t = me["tiles"][py][px]
                                if t is None and total_c + total_g + total_s < 14 and day < 18:
                                    best_target = (px, py)
                                    break
                                elif isinstance(t, dict) and t.get("kind") == "WEED":
                                    best_target = (px, py)
                                    break
                                elif isinstance(t, dict) and ("animal" in t):
                                    is_unfed = (not t.get("fed_today", False))
                                    is_uncared = (not t.get("cared_today", False))
                                    if (is_unfed and wheat_count > 0) or is_uncared:
                                        priority = 95 if is_unfed else 85
                                        score = priority * 10 - self._dist(pos, (px, py))
                                        if score > best_score:
                                            best_score = score
                                            best_target = (px, py)

                        if best_target:
                            claimed_targets.add(best_target)
                            tx, ty = best_target
                            if pos == best_target:
                                t = me["tiles"][ty][tx]
                                is_coop_tile = (tx, ty) in self.goose_coops
                                if t is None:
                                    action = ["BUILD_COOP" if is_coop_tile else "BUILD_PASTURE"]
                                elif isinstance(t, dict) and t.get("kind") == "WEED":
                                    action = ["DIG"]
                                elif isinstance(t, dict) and ("animal" in t):
                                    if not t.get("fed_today", False) and wheat_count > 0:
                                        action = ["FEED"]
                                    elif not t.get("cared_today", False):
                                        action = ["CARE"]
                                    elif t.get("fertilizer_available", False):
                                        action = ["COLLECT_FERTILIZER"]
                                    elif t.get("yield_units", 0) >= 1:
                                        action = ["HARVEST"]
                            else:
                                action = [self._get_step_towards(pos, best_target)]
                        else:
                            if (carrying_produce - wheat_count) > 0 and hour >= 16:
                                action = [self._get_step_towards(pos, default_drop_tile)]
                            elif wheat_count == 0 and shed_wheat > 0 and hour < 14:
                                action = [self._get_step_towards(pos, default_drop_tile)]
                            else:
                                action = ["PASS"]

            # =========================================================
            # SECTION B: CROP CREWS (UNITS 4..12) - STRICT CROPS
            # =========================================================
            else:
                # Stand-and-Water: If standing on an unwatered plant, immediately water it!
                if isinstance(current_tile, dict) and current_tile.get("kind") == "PLANT" and not current_tile.get("watered_today", False):
                    action = ["WATER"]

                # Opportunistic Batch Drop if already adjacent to shed
                elif pos in SHED_ACCESS_TILES and carrying_produce > 0:
                    action = ["DROP"]

                if action == ["PASS"]:
                    # Mode dispatch for walk-to-shed interruption
                    walk_to_shed_now = False
                    if self.crop_drop_mode == "baseline":
                        if carrying_produce >= 15 or (carrying_produce > 0 and hour >= 18):
                            walk_to_shed_now = True
                    elif self.crop_drop_mode == "high_cap":
                        if carrying_produce >= 50:
                            walk_to_shed_now = True
                    elif self.crop_drop_mode in ("task_first", "pure_field"):
                        walk_to_shed_now = False

                    if walk_to_shed_now:
                        action = [self._get_step_towards(pos, default_drop_tile)]
                    else:
                        sector_tasks = []
                        if u_idx in (4, 5):
                            sector_tasks = nw_wheat_tasks_p1 or nw_wheat_tasks_p2 or ne_tasks or sw_tasks
                        elif u_idx in (6, 7, 8):
                            sector_tasks = ne_tasks or nw_wheat_tasks_p1 or nw_wheat_tasks_p2 or sw_tasks
                        else:
                            sector_tasks = sw_tasks or ne_tasks or nw_wheat_tasks_p1 or nw_wheat_tasks_p2

                        best_task = None
                        best_score = -1e9

                        for t in sector_tasks:
                            target = t["target"]
                            if target in claimed_targets:
                                continue
                            if "crop" in t and avail_seeds.get(t["crop"], 0) <= 0:
                                continue

                            d = self._dist(pos, target)
                            score = t["priority"] * 10 - d + (500 if d == 0 else 0)
                            if score > best_score:
                                best_score = score
                                best_task = t

                        if best_task:
                            target = best_task["target"]
                            claimed_targets.add(target)
                            tx, ty = target

                            if pos == target:
                                tact = best_task["action"]
                                if tact == "HARVEST":
                                    action = ["HARVEST"]
                                elif tact == "WATER":
                                    action = ["WATER"]
                                elif tact == "PLANT_WHEAT" and avail_seeds.get("WHEAT", 0) > 0:
                                    action = ["PLANT", "WHEAT"]
                                    avail_seeds["WHEAT"] -= 1
                                elif tact == "PLANT_STRAWBERRY" and avail_seeds.get("STRAWBERRY", 0) > 0:
                                    action = ["PLANT", "STRAWBERRY"]
                                    avail_seeds["STRAWBERRY"] -= 1
                                elif tact == "PLANT_MELON" and avail_seeds.get("MELON", 0) > 0:
                                    action = ["PLANT", "MELON"]
                                    avail_seeds["MELON"] -= 1
                                elif tact == "PLANT_CARROT" and avail_seeds.get("CARROT", 0) > 0:
                                    action = ["PLANT", "CARROT"]
                                    avail_seeds["CARROT"] -= 1
                                elif tact == "DIG":
                                    action = ["DIG"]
                            else:
                                action = [self._get_step_towards(pos, target)]
                        else:
                            # Idle fallback when no tasks available in sector
                            if self.crop_drop_mode == "pure_field":
                                action = ["PASS"]
                            elif self.crop_drop_mode in ("baseline", "task_first", "high_cap"):
                                if carrying_produce > 0:
                                    action = [self._get_step_towards(pos, default_drop_tile)]
                                else:
                                    action = ["PASS"]

            unit_actions.append(action)

        return {
            "farmer": unit_actions[0] if unit_actions else ["PASS"],
            "hands": unit_actions[1:] if len(unit_actions) > 1 else [],
            "market": market_orders[:10],
        }

    def _get_step_towards(self, curr: Tuple[int, int], target: Tuple[int, int]) -> str:
        cx, cy = curr
        tx, ty = target
        if cx == tx and cy == ty:
            return "PASS"
        dx = tx - cx
        dy = ty - cy
        if abs(dx) >= abs(dy) and dx != 0:
            return "EAST" if dx > 0 else "WEST"
        elif dy != 0:
            return "SOUTH" if dy > 0 else "NORTH"
        return "PASS"

    def _dist(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> int:
        return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])


def _build_agent(kind: str, mode: str):
    if kind == "pass":
        return lambda obs: {"farmer": ["PASS"], "hands": [], "market": []}
    elif mode == "dominant_meta":
        return make_spatial_dispatcher_agent(params={"cow_gate_day_early": 99, "cow_gate_day_mid": 99}, kw_early=10)
    elif mode == "dispatcher":
        return make_spatial_dispatcher_agent(kw_early=10)
    else:
        return ThroughputCropAgent(crop_drop_mode=mode, kw_early=10)


def _worker_match(task: Tuple[str, str, str, str, int]) -> Tuple[float, float]:
    p0_kind, p0_mode, p1_kind, p1_mode, seed = task
    a0 = _build_agent(p0_kind, p0_mode)
    a1 = _build_agent(p1_kind, p1_mode)
    game = FastGame(seed=seed)
    while not game.done:
        game.step_game(a0(game.get_observation(0)), a1(game.get_observation(1)))
    return float(game.farms[0].money), float(game.farms[1].money)


def run_self_play(mode: str, seeds: List[int], max_workers: int = 8) -> Tuple[float, float, float, float]:
    tasks = [("dispatcher", mode, "dispatcher", mode, s) for s in seeds]
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(_worker_match, tasks))
    all_scores = [r[0] for r in results] + [r[1] for r in results]
    return float(np.mean(all_scores)), float(np.median(all_scores)), float(np.min(all_scores)), float(np.max(all_scores))


def run_h2h(cand_mode: str, opp_mode: str, opp_kind: str, seeds: List[int], max_workers: int = 8) -> Dict[str, Any]:
    tasks = []
    for s in seeds:
        # Seat 0: Cand is P0, Opp is P1
        tasks.append(("dispatcher", cand_mode, opp_kind, opp_mode, s))
        # Seat 1: Opp is P0, Cand is P1
        tasks.append((opp_kind, opp_mode, "dispatcher", cand_mode, s))
        
    with ProcessPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(_worker_match, tasks))
        
    diffs, prod_sc, opp_sc = [], [], []
    wins = losses = ties = 0
    for i in range(0, len(results), 2):
        r_c0, r_o1 = results[i]
        d0 = r_c0 - r_o1; diffs.append(d0); prod_sc.append(r_c0); opp_sc.append(r_o1)
        if d0 > 0: wins += 1
        elif d0 < 0: losses += 1
        else: ties += 1
        
        r_o0, r_c1 = results[i+1]
        d1 = r_c1 - r_o0; diffs.append(d1); prod_sc.append(r_c1); opp_sc.append(r_o0)
        if d1 > 0: wins += 1
        elif d1 < 0: losses += 1
        else: ties += 1
        
    n = len(diffs)
    mean_d = float(np.mean(diffs))
    se_d = float(np.std(diffs, ddof=1) / np.sqrt(n))
    t_stat = mean_d / se_d if se_d > 0 else 0.0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1))
    wr = (wins / (wins + losses)) * 100.0 if (wins + losses) > 0 else 0.0
    return {
        "prod_mean": float(np.mean(prod_sc)), "opp_mean": float(np.mean(opp_sc)),
        "delta": mean_d, "se": se_d, "t": t_stat, "p": p_val,
        "wr": wr, "W": wins, "L": losses, "T": ties
    }


def eval_candidate(mode: str, label: str, workers: int = 8):
    print(f"\n{'='*105}", flush=True)
    print(f"  {label} (Mode: {mode})", flush=True)
    print(f"{'='*105}", flush=True)

    # 1. Self-Play Suites
    sp20_mean, sp20_med, sp20_min, sp20_max = run_self_play(mode, OFFICIAL_20, max_workers=workers)
    sp100_mean, sp100_med, sp100_min, sp100_max = run_self_play(mode, DISJOINT_100, max_workers=workers)
    
    print(f"  Self-Play Official 20:  ${sp20_mean:>9,.2f} (Med: ${sp20_med:>9,.2f}, Min: ${sp20_min:>9,.2f}) | Delta vs $47,224.93: {sp20_mean - 47224.93:>+,.2f}", flush=True)
    print(f"  Self-Play Disjoint 100: ${sp100_mean:>9,.2f} (Med: ${sp100_med:>9,.2f}, Min: ${sp100_min:>9,.2f}) | Delta vs $52,058.16: {sp100_mean - 52058.16:>+,.2f}", flush=True)

    # 2. H2H vs Dominant Meta (un-gated 10C/4S/0G)
    r_dm = run_h2h(mode, "dominant_meta", "dispatcher", DISJOINT_100, max_workers=workers)
    print(f"  vs Dominant Meta (10C/4S/0G, n=200): Prod ${r_dm['prod_mean']:>9,.2f} | Opp ${r_dm['opp_mean']:>9,.2f} | Delta ${r_dm['delta']:>+9,.2f} (t={r_dm['t']:>+5.2f}, p={r_dm['p']:.4e}) | WR: {r_dm['wr']:>5.1f}% ({r_dm['W']}W/{r_dm['L']}L/{r_dm['T']}T)", flush=True)

    # 3. Direct H2H vs Baseline (§2w Production)
    r_base = run_h2h(mode, "baseline", "dispatcher", DISJOINT_100, max_workers=workers)
    print(f"  vs Baseline (§2w Prod, n=200):        Prod ${r_base['prod_mean']:>9,.2f} | Opp ${r_base['opp_mean']:>9,.2f} | Delta ${r_base['delta']:>+9,.2f} (t={r_base['t']:>+5.2f}, p={r_base['p']:.4e}) | WR: {r_base['wr']:>5.1f}% ({r_base['W']}W/{r_base['L']}L/{r_base['T']}T)", flush=True)

    return {"label": label, "sp20": sp20_mean, "sp100": sp100_mean, "dm": r_dm, "base": r_base}


def main():
    workers = min(os.cpu_count() or 4, 8)
    print("=" * 105)
    print(f"THROUGHPUT EXPERIMENT §2y: CROP CREW AUTO-FLUSH FIELD RETENTION ({workers} WORKERS)")
    print("Baseline (§2w): Official 20 = $47,224.93, Disjoint 100 = $52,058.16, DM WR = 64.3%")
    print("=" * 105)

    # Canary Validation
    print("\n--- RUNNING STANDING CANARIES ---", flush=True)
    r_pass = run_h2h("baseline", "", "pass", DISJOINT_100, max_workers=workers)
    if abs(r_pass["opp_mean"] - 3000.0) > 1e-4 or r_pass["wr"] != 100.0:
        raise RuntimeError(f"CANARY 1 FAILED! Pass baseline opponent = ${r_pass['opp_mean']:.2f}, WR = {r_pass['wr']:.1f}%")
    print(f"  [PASS] Canary 1 (Pass Baseline): Opponent = $3,000.00, WR = 100.0% ({r_pass['W']}W/{r_pass['L']}L/{r_pass['T']}T)", flush=True)

    r_ident = run_h2h("baseline", "baseline", "dispatcher", DISJOINT_100, max_workers=workers)
    if abs(r_ident["wr"] - 50.0) > 1e-4 or abs(r_ident["delta"]) > 1e-4:
        raise RuntimeError(f"CANARY 2 FAILED! Identity control WR = {r_ident['wr']:.1f}%, Delta = ${r_ident['delta']:.2f}")
    print(f"  [PASS] Canary 2 (Identity Control): WR = 50.0%, Delta = $0.00 ({r_ident['W']}W/{r_ident['L']}L/{r_ident['T']}T)", flush=True)

    t0 = time.time()

    # Candidate 0: Baseline Verification
    eval_candidate("baseline", "Candidate 0: Baseline (carrying >= 15 or hour >= 18 forces shed drop)", workers=workers)

    # Candidate 1: Task Priority (work tasks first; only walk to shed when idle with produce)
    eval_candidate("task_first", "Candidate 1: Task Priority (no hour>=18 or cap>=15 interruption; shed drop only if idle)", workers=workers)

    # Candidate 2: Pure Field Retention (never walk to shed on days < 29; opportunistic drop if adjacent; auto-flush at midnight)
    eval_candidate("pure_field", "Candidate 2: Pure Field Retention (never walk to shed days < 29; 100% auto-flush at midnight)", workers=workers)

    # Candidate 3: High Capacity Buffer (only walk to shed if carrying >= 50 items or idle)
    eval_candidate("high_cap", "Candidate 3: High Capacity Buffer (walk to shed only if carrying >= 50 items or idle)", workers=workers)

    elapsed = time.time() - t0
    print(f"\n{'='*105}", flush=True)
    print(f"Throughput Experiment §2y completed in {elapsed:.1f}s", flush=True)
    print(f"{'='*105}", flush=True)


if __name__ == "__main__":
    main()
