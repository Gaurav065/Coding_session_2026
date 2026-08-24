"""Shop-Adaptive Production Candidate Sweep — Project Maestro

Evaluates dynamic shop-revealed adaptation without seed dependency.
Tests different cow gating days and caps:
- Day 7: 2 shops revealed. If milk_shop_count == 0 (probability ~39%): cap cows.
- Day 10: 3 shops revealed. If milk_shop_count <= 1 (probability ~68%): cap cows.
- Also tests sheep and crop reallocation when milk demand is weak.

Evaluates:
1. Official 20 Seeds Self-Play
2. 100 Disjoint Seeds Self-Play (10000..10099)
3. Head-to-Head vs Dominant Meta (10C/4S/0G) across 100 Disjoint Seeds (200 matches)
"""

import sys
import numpy as np
from scipy import stats
from typing import Tuple, List, Dict, Any

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    make_spatial_dispatcher_agent, MaestroFullPortfolioAgent,
    COW_PASTURES, SHEEP_PASTURES, GOOSE_COOPS, NW_WHEAT, NE_STRAWBERRY, NE_WHEAT, SW_MELON, SW_WHEAT,
    GLUT_RESISTANT, GLUT_PRONE, BASE_PRICES
)

OFFICIAL_20 = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
               250, 300, 333, 404, 500, 600, 700, 777, 888, 999]
DISJOINT_100 = list(range(10000, 10100))

MILK_SHOPS = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}


class ConfigurableAdaptiveAgent(MaestroFullPortfolioAgent):
    def __init__(self,
                 cow_gate_day7_zero: int = 4,   # cow cap if day>=7 and milk_shops==0
                 cow_gate_day10_low: int = 6,   # cow cap if day>=10 and milk_shops<=1
                 sheep_cap_realloc: int = 4,    # sheep cap if yarn_store present
                 **kwargs):
        super().__init__(**kwargs)
        self.cow_gate_day7_zero = cow_gate_day7_zero
        self.cow_gate_day10_low = cow_gate_day10_low
        self.sheep_cap_realloc = sheep_cap_realloc

    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
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

        milk_shop_count = sum(1 for s in unlocked_shops if s in MILK_SHOPS)

        # Dynamic revealed-demand cow cap
        if day >= 7 and milk_shop_count == 0:
            cow_cap = self.cow_gate_day7_zero
        elif day >= 10 and milk_shop_count <= 1:
            cow_cap = self.cow_gate_day10_low
        elif day >= 15 and milk_shop_count <= 1:
            cow_cap = self.params["cow_cap_low"]
        else:
            cow_cap = self.params["cow_cap_base"]

        # If milk shops are 0 but yarn store is present, can expand sheep
        sheep_cap = self.sheep_cap_realloc if (has_yarn_store and milk_shop_count == 0) else self.params["sheep_cap"]

        # Standard Dispatcher Logic
        self.nw_wheat = list(NW_WHEAT)

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

        market_orders = []

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

        # Emergency Feed Guard
        if day < 29 and shed_wheat == 0 and money >= 120:
            if len(market_orders) < 8:
                market_orders.append(["BUY_PRODUCT", "WHEAT", 6])

        # Expansion Pipeline
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
                straw_target = self.params["strawberry_target"]
                straw_needed = max(0, straw_target - strawberry_plants - private["seeds"].get("STRAWBERRY", 0))
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

                if total_c < cow_cap and money >= 700 and shed_total_items <= 90 and day < 18:
                    buy_c = min(cow_cap - total_c, int((money - 300) // 400))
                    if buy_c > 0:
                        market_orders.append(["BUY_ANIMAL", "COW", min(2, buy_c)])
                else:
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

        avail_seeds = dict(private.get("seeds", {}))

        for u_idx, (ux, uy) in enumerate(all_units):
            inv = private["inventories"][u_idx] if u_idx < len(private["inventories"]) else {}
            carrying_produce = sum(v for k, v in inv.items() if k not in ["COW", "SHEEP", "GOOSE"])
            carrying_animal = "COW" if inv.get("COW", 0) > 0 else ("GOOSE" if inv.get("GOOSE", 0) > 0 else ("SHEEP" if inv.get("SHEEP", 0) > 0 else None))
            standing_on_shed = (ux, uy) in [(4, 4), (5, 4), (4, 5), (5, 5)]

            action = None

            if is_endgame_flush:
                if carrying_produce > 0:
                    if standing_on_shed:
                        action = ["DROP"]
                    else:
                        step_dir = self._get_step_to_shed((ux, uy))
                        action = [step_dir] if step_dir else ["PASS"]
                else:
                    action = ["PASS"]
                unit_actions.append(action)
                continue

            if carrying_produce >= 20:
                if standing_on_shed:
                    action = ["DROP"]
                else:
                    step_dir = self._get_step_to_shed((ux, uy))
                    action = [step_dir] if step_dir else ["PASS"]
                unit_actions.append(action)
                continue

            # Unit 1 & 2: Livestock Management
            if u_idx in [1, 2]:
                if standing_on_shed:
                    if private["shed"].get("WHEAT", 0) > 0 and inv.get("WHEAT", 0) == 0:
                        take_wheat = min(15, private["shed"].get("WHEAT", 0))
                        action = ["PICKUP", "WHEAT", take_wheat]
                    elif day < 18 and private["shed"].get("COW", 0) > 0 and not carrying_animal:
                        action = ["PICKUP", "COW", 1]
                    elif day < 20 and private["shed"].get("SHEEP", 0) > 0 and not carrying_animal:
                        action = ["PICKUP", "SHEEP", 1]

                if not action:
                    tile_here = me["tiles"][uy][ux]
                    animal_type = tile_here.get("animal") if isinstance(tile_here, dict) else None
                    is_animal_structure = isinstance(tile_here, dict) and (tile_here.get("kind") in ["PASTURE", "COOP"])
                    fed_today = tile_here.get("fed_today", False) if isinstance(tile_here, dict) else False
                    cared_today = tile_here.get("cared_today", False) if isinstance(tile_here, dict) else False
                    y_units = tile_here.get("yield_units", 0) if isinstance(tile_here, dict) else 0

                    if carrying_animal:
                        target_coords = self.cow_pastures if carrying_animal == "COW" else self.sheep_pastures
                        empty_structs = []
                        empty_unbuilt = []
                        for px, py in target_coords:
                            st = me["tiles"][py][px]
                            if isinstance(st, dict) and (st.get("kind") in ["PASTURE", "COOP"]) and ("animal" not in st):
                                empty_structs.append((px, py))
                            elif st is None:
                                empty_unbuilt.append((px, py))

                        if (ux, uy) in empty_structs:
                            action = ["PLACE", carrying_animal, 1]
                        elif (ux, uy) in empty_unbuilt:
                            action = ["BUILD_PASTURE"]
                        elif empty_structs:
                            action = [self._get_step_towards((ux, uy), empty_structs[0])]
                        elif empty_unbuilt:
                            action = [self._get_step_towards((ux, uy), empty_unbuilt[0])]
                        else:
                            action = ["PASS"]
                    elif is_animal_structure and animal_type:
                        if day < 29 and not fed_today and inv.get("WHEAT", 0) > 0:
                            action = ["FEED"]
                        elif y_units >= 2 and carrying_produce < 20:
                            action = ["HARVEST"]
                        elif animal_type == "COW" and y_units >= 1 and carrying_produce < 20:
                            action = ["HARVEST"]
                        elif not cared_today and day < 28:
                            action = ["CARE"]

                if not action:
                    livestock_targets = []
                    for px, py in self.cow_pastures + self.sheep_pastures:
                        st = me["tiles"][py][px]
                        if isinstance(st, dict) and ("animal" in st):
                            fed = st.get("fed_today", False)
                            cared = st.get("cared_today", False)
                            yu = st.get("yield_units", 0)
                            if (day < 29 and not fed) or (yu >= 1) or (not cared and day < 28):
                                livestock_targets.append((px, py))

                    if livestock_targets:
                        livestock_targets.sort(key=lambda pos: self._dist((ux, uy), pos))
                        action = [self._get_step_towards((ux, uy), livestock_targets[0])]
                    else:
                        if carrying_produce > 0:
                            if standing_on_shed:
                                action = ["DROP"]
                            else:
                                step_dir = self._get_step_to_shed((ux, uy))
                                action = [step_dir] if step_dir else ["PASS"]
                        elif (ux, uy) not in self.cow_pastures:
                            action = [self._get_step_towards((ux, uy), self.cow_pastures[0])]
                        else:
                            action = ["PASS"]

                unit_actions.append(action if action else ["PASS"])
                continue

            # Units 0, 3..9: Sector Field Workers
            # (Worker pool assignment identical to parent)
            pool = []
            if u_idx == 0:
                pool = nw_wheat_tasks_p1 + nw_wheat_tasks_p2 + ne_tasks + sw_tasks
            elif u_idx in [3, 4]:
                pool = nw_wheat_tasks_p1 + nw_wheat_tasks_p2
            elif u_idx in [5, 6, 7]:
                pool = ne_tasks + nw_wheat_tasks_p2
            else:
                pool = sw_tasks + ne_tasks + nw_wheat_tasks_p2

            assigned_task = None
            best_score = -1e9
            for t_item in pool:
                t_pos = t_item["target"]
                if t_pos in claimed_targets:
                    continue
                req_crop = t_item.get("crop")
                if req_crop and avail_seeds.get(req_crop, 0) <= 0:
                    continue
                d = self._dist((ux, uy), t_pos)
                score = t_item["priority"] * 10 - d
                if score > best_score:
                    best_score = score
                    assigned_task = t_item

            if assigned_task:
                claimed_targets.add(assigned_task["target"])
                tx, ty = assigned_task["target"]
                act_name = assigned_task["action"]
                if (ux, uy) == (tx, ty):
                    if act_name == "PLANT_WHEAT":
                        action = ["PLANT", "WHEAT"]
                        avail_seeds["WHEAT"] = max(0, avail_seeds.get("WHEAT", 0) - 1)
                    elif act_name == "PLANT_STRAWBERRY":
                        action = ["PLANT", "STRAWBERRY"]
                        avail_seeds["STRAWBERRY"] = max(0, avail_seeds.get("STRAWBERRY", 0) - 1)
                    elif act_name == "PLANT_CARROT":
                        action = ["PLANT", "CARROT"]
                        avail_seeds["CARROT"] = max(0, avail_seeds.get("CARROT", 0) - 1)
                    elif act_name == "PLANT_MELON":
                        action = ["PLANT", "MELON"]
                        avail_seeds["MELON"] = max(0, avail_seeds.get("MELON", 0) - 1)
                    elif act_name in ["WATER", "HARVEST", "DIG"]:
                        action = [act_name]
                    else:
                        action = ["PASS"]
                else:
                    action = [self._get_step_towards((ux, uy), (tx, ty))]
            else:
                if carrying_produce > 0:
                    if standing_on_shed:
                        action = ["DROP"]
                    else:
                        step_dir = self._get_step_to_shed((ux, uy))
                        action = [step_dir] if step_dir else ["PASS"]
                else:
                    action = ["PASS"]

            unit_actions.append(action if action else ["PASS"])

        farmer_act = unit_actions[0]
        hands_acts = unit_actions[1:]
        return {
            "farmer": farmer_act,
            "hands": hands_acts,
            "market": market_orders
        }

    def _get_step_towards(self, curr: Tuple[int, int], target: Tuple[int, int]) -> str:
        cx, cy = curr
        tx, ty = target
        dx = tx - cx
        dy = ty - cy
        if dx == 0 and dy == 0:
            return "PASS"
        if abs(dx) > abs(dy):
            return "EAST" if dx > 0 else "WEST"
        else:
            return "SOUTH" if dy > 0 else "NORTH"

    def _get_step_to_shed(self, curr: Tuple[int, int]) -> str:
        shed_tiles = [(4, 4), (5, 4), (4, 5), (5, 5)]
        best_dist = 999
        best_tile = shed_tiles[0]
        for st in shed_tiles:
            d = abs(curr[0] - st[0]) + abs(curr[1] - st[1])
            if d < best_dist:
                best_dist = d
                best_tile = st
        return self._get_step_towards(curr, best_tile)

    def _dist(self, p1: Tuple[int, int], p2: Tuple[int, int]) -> int:
        return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])


def run_match(a0, a1, seed: int) -> Tuple[float, float]:
    game = FastGame(seed=seed)
    while not game.done:
        act0 = a0(game.get_observation(0))
        act1 = a1(game.get_observation(1))
        game.step_game(act0, act1)
    return float(game.farms[0].money), float(game.farms[1].money)


def eval_candidate(candidate_factory, label: str):
    print(f"\nEvaluating: {label}")
    
    # 1. Official 20 Self-Play
    sp_20 = []
    for s in OFFICIAL_20:
        r0, r1 = run_match(candidate_factory(), candidate_factory(), s)
        sp_20.append((r0 + r1) / 2.0)
    mean_20 = float(np.mean(sp_20))
    
    # 2. 100 Disjoint Self-Play
    sp_100 = []
    for s in DISJOINT_100:
        r0, r1 = run_match(candidate_factory(), candidate_factory(), s)
        sp_100.append((r0 + r1) / 2.0)
    mean_100 = float(np.mean(sp_100))
    
    # 3. H2H vs Dominant Meta (100 Disjoint seeds x 2 seats = 200 matches)
    diffs = []
    wins = losses = ties = 0
    for s in DISJOINT_100:
        # Seat 0
        r0, r1 = run_match(candidate_factory(), make_spatial_dispatcher_agent(kw_early=10), s)
        d0 = r0 - r1; diffs.append(d0)
        if d0 > 0: wins += 1
        elif d0 < 0: losses += 1
        else: ties += 1
        # Seat 1
        r_opp, r_cand = run_match(make_spatial_dispatcher_agent(kw_early=10), candidate_factory(), s)
        d1 = r_cand - r_opp; diffs.append(d1)
        if d1 > 0: wins += 1
        elif d1 < 0: losses += 1
        else: ties += 1
        
    n = len(diffs)
    mean_diff = float(np.mean(diffs))
    se_diff = float(np.std(diffs, ddof=1) / np.sqrt(n))
    t_stat = mean_diff / se_diff if se_diff > 0 else 0.0
    p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n - 1))
    wr = (wins / (wins + losses)) * 100.0 if (wins + losses) > 0 else 0.0
    
    print(f"  Official 20 Self-Play:  ${mean_20:>10,.2f}  (Base: $44,743.35, Delta: {mean_20 - 44743.35:>+,.2f})")
    print(f"  Disjoint 100 Self-Play: ${mean_100:>10,.2f}  (Base: $49,613.06, Delta: {mean_100 - 49613.06:>+,.2f})")
    print(f"  H2H vs Dominant Meta:   WR={wr:.1f}% ({wins}W/{losses}L/{ties}T), Net Delta=${mean_diff:>+,.2f} (t={t_stat:>+.2f}, p={p_val:.4f})")
    
    return {
        "label": label, "mean_20": mean_20, "mean_100": mean_100,
        "wr_h2h": wr, "delta_h2h": mean_diff, "t_h2h": t_stat, "p_h2h": p_val
    }


def main():
    print("=" * 80)
    print("SHOP-ADAPTIVE PRODUCTION CANDIDATE SWEEP")
    print("Baseline: Official 20 = $44,743.35, Disjoint 100 = $49,613.06")
    print("Dominant Meta H2H Baseline: 50.0% WR (Identity Control)")
    print("=" * 80)
    
    # Candidate A: Day 7 (2 shops) milk_shops==0 -> cow_cap=4; Day 10 (3 shops) milk_shops<=1 -> cow_cap=6
    eval_candidate(lambda: ConfigurableAdaptiveAgent(cow_gate_day7_zero=4, cow_gate_day10_low=6),
                   "Cand A: Day 7 zero-milk -> cap 4, Day 10 <=1 milk -> cap 6")

    # Candidate B: Day 7 (2 shops) milk_shops==0 -> cow_cap=6; Day 10 (3 shops) milk_shops<=1 -> cow_cap=6
    eval_candidate(lambda: ConfigurableAdaptiveAgent(cow_gate_day7_zero=6, cow_gate_day10_low=6),
                   "Cand B: Day 7 zero-milk -> cap 6, Day 10 <=1 milk -> cap 6")

    # Candidate C: Day 10 (3 shops) milk_shops==0 -> cow_cap=4; Day 10 <=1 milk -> cap 6
    eval_candidate(lambda: ConfigurableAdaptiveAgent(cow_gate_day7_zero=10, cow_gate_day10_low=6),
                   "Cand C: Day 10 <=1 milk -> cap 6 (Day 7 unconstrained)")

    # Candidate D: Day 7 zero-milk -> cap 4, Day 10 <=1 milk -> cap 6 + sheep reallocation (cap 6 if yarn store & 0 milk)
    eval_candidate(lambda: ConfigurableAdaptiveAgent(cow_gate_day7_zero=4, cow_gate_day10_low=6, sheep_cap_realloc=6),
                   "Cand D: Cand A + Sheep Reallocation (cap 6 if yarn store & 0 milk)")


if __name__ == "__main__":
    main()
