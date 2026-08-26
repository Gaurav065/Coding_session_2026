"""Upgraded Symmetrical Spatial Dispatcher Agent - Project Maestro

Architectural Upgrades:
1. Symmetrical Pasture Ring: Cows in NW ring (Dist 1-2), Sheep in NE ring (Dist 1-2) around the shed.
2. Rationalized Wheat Allocation: 10 NW wheat plots strictly for self-sustaining animal feed.
3. High-Density Cash Crop Allocation: 18 NE Strawberries + 9 SW Melons + 6 SW Carrots.
4. Zero-Stagnation Pipelined Dispatch:
   - Eliminates the 4-turn single-worker animal freeze.
   - Workers with produce immediately drop when shed-adjacent or at threshold.
   - Idle animal workers seamlessly assist with crop watering and harvesting instead of executing PASS.
5. Dynamic Shop Elasticity:
   - Scales to 8 Sheep when YARN_STORE >= 2.
   - Plants Carrots when PET_CAFE >= 2.
"""

from typing import Dict, List, Tuple, Optional, Any, Set
from collections import defaultdict

MOVES = {
    (0, -1): "NORTH",
    (0, 1):  "SOUTH",
    (1, 0):  "EAST",
    (-1, 0): "WEST",
}

SHED_ACCESS_TILES_LIST = [(4, 4), (5, 4), (4, 5), (5, 5)]
SHED_ACCESS_TILES = set(SHED_ACCESS_TILES_LIST)

# Symmetrical Pasture Ring directly surrounding the shed center
COW_PASTURES = [
    (4, 3), (3, 4),
    (4, 2), (3, 3), (2, 4),
    (4, 1), (3, 2), (2, 3), (1, 4),
    (0, 4)
]

SHEEP_PASTURES = [
    (5, 3), (6, 4),
    (6, 3), (5, 2), (7, 4),
    (6, 2), (7, 3), (5, 1)
]

# 10 NW Wheat plots strictly for livestock feed (generates ~140 wheat every 2 days)
NW_WHEAT = [
    (0, 0), (1, 0), (2, 0), (3, 0),
    (0, 1), (1, 1), (2, 1),
    (0, 2), (1, 2),
    (0, 3)
]

# NE Quadrant: 18 Strawberry plots outside the Sheep ring
NE_STRAWBERRY = [
    (5, 0), (6, 0), (7, 0), (8, 0), (9, 0),
    (6, 1), (7, 1), (8, 1), (9, 1),
    (7, 2), (8, 2), (9, 2),
    (8, 3), (9, 3),
    (8, 4), (9, 4),
    (7, 1), (7, 0)
]

# SW Quadrant: 9 Melons + 6 Carrots
SW_MELON = [
    (0, 6), (1, 6), (2, 6),
    (0, 7), (1, 7), (2, 7),
    (0, 8), (1, 8), (2, 8)
]

SW_CARROT = [
    (3, 6), (4, 6),
    (3, 7), (4, 7),
    (3, 8), (4, 8)
]

BASE_PRICES = {
    "WHEAT": 25,
    "CARROT": 35,
    "TOMATO": 60,
    "STRAWBERRY": 120,
    "MELON": 250,
    "EGG": 50,
    "MILK": 160,
    "WOOL": 200,
    "FERTILIZER": 100,
}

ABOVE_TARGET = {
    "WHEAT": 0.20, "EGG": 0.20,
    "TOMATO": 0.60, "CARROT": 0.70, "FERTILIZER": 0.40,
    "STRAWBERRY": 1.60, "MILK": 1.60, "WOOL": 3.20, "MELON": 3.60,
}
GLUT_RESISTANT = {"WHEAT", "EGG"}

def get_step_towards(curr: Tuple[int, int], target: Tuple[int, int]) -> str:
    cx, cy = curr
    tx, ty = target
    if cx == tx and cy == ty:
        return "PASS"

    dx = tx - cx
    dy = ty - cy

    if abs(dx) >= abs(dy) and dx != 0:
        step = (1 if dx > 0 else -1, 0)
        return MOVES.get(step, "PASS")
    elif dy != 0:
        step = (0, 1 if dy > 0 else -1)
        return MOVES.get(step, "PASS")
    return "PASS"

def dist(p1: Tuple[int, int], p2: Tuple[int, int]) -> int:
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

DEFAULT_PARAMS = {
    "cow_cap_base": 9,
    "cow_cap_low": 6,
    "cow_cap_zero": 4,
    "sheep_cap_base": 4,
    "sheep_cap_high": 8,
    "strawberry_target": 18,
    "melon_target": 9,
    "carrot_target_base": 0,
    "carrot_target_high": 6,
    "crew_base": 9,
    "crew_late": 11,
}

class UpgradedSpatialAgent:
    def __init__(self, params=None, seed: Optional[int] = None):
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.seed = seed
        self.cow_pastures = list(COW_PASTURES)
        self.sheep_pastures = list(SHEEP_PASTURES)
        self.nw_wheat = list(NW_WHEAT)
        self.ne_strawberry = list(NE_STRAWBERRY)
        self.sw_melon = list(SW_MELON)
        self.sw_carrot = list(SW_CARROT)

    def __call__(self, obs: Dict[str, Any], config=None) -> Dict[str, Any]:
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        day = obs["day"]
        hour = obs["hour"]
        step = obs.get("step", day * 24 + hour)
        money = me["money"]
        unlocked_quads = set(me.get("unlocked_quadrants", []))
        market_prices = obs.get("market", {}).get("prices", {})
        unlocked_shops = obs.get("town", {}).get("unlocked_shops", [])

        # Shop Elasticity Triggers
        yarn_count = unlocked_shops.count("YARN_STORE")
        pet_cafe_count = unlocked_shops.count("PET_CAFE")
        milk_shops = sum(1 for s in unlocked_shops if s in {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"})

        sheep_cap = self.params["sheep_cap_high"] if yarn_count >= 2 else self.params["sheep_cap_base"]
        carrot_target = self.params["carrot_target_high"] if pet_cafe_count >= 2 else self.params["carrot_target_base"]

        if day >= 10 and milk_shops == 0:
            cow_cap = self.params["cow_cap_zero"]
        elif day >= 10 and milk_shops <= 1:
            cow_cap = self.params["cow_cap_low"]
        else:
            cow_cap = self.params["cow_cap_base"]

        # Crew Sizing
        if day >= 29:
            target_crew = 7
        elif day < 3:
            target_crew = 6
        elif "SW" in unlocked_quads:
            target_crew = self.params["crew_late"]
        else:
            target_crew = self.params["crew_base"]

        market_orders = []

        # Count placed animals
        placed_c, placed_s = 0, 0
        for py in range(10):
            for px in range(10):
                t = me["tiles"][py][px]
                if isinstance(t, dict) and "animal" in t:
                    if t["animal"] == "COW":
                        placed_c += 1
                    elif t["animal"] == "SHEEP":
                        placed_s += 1

        shed = private.get("shed", {})
        shed_total = sum(shed.values())
        shed_wheat = shed.get("WHEAT", 0)
        shed_c = shed.get("COW", 0)
        shed_s = shed.get("SHEEP", 0)

        carried_c = sum(inv.get("COW", 0) for inv in private.get("inventories", []))
        carried_s = sum(inv.get("SHEEP", 0) for inv in private.get("inventories", []))

        total_c = placed_c + shed_c + carried_c
        total_s = placed_s + shed_s + carried_s

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

        # Land and Seed Purchases
        if len(market_orders) < 8:
            if "NE" not in unlocked_quads and money >= 1000:
                market_orders.append(["BUY_LAND"])
            elif "NE" in unlocked_quads and "SW" not in unlocked_quads and money >= 2000 and day >= 6:
                market_orders.append(["BUY_LAND"])

            # Strawberries in NE
            if "NE" in unlocked_quads and day < 20:
                straw_plants = sum(1 for sx, sy in self.ne_strawberry if isinstance(me["tiles"][sy][sx], dict) and me["tiles"][sy][sx].get("crop") == "STRAWBERRY")
                straw_needed = max(0, self.params["strawberry_target"] - straw_plants - private["seeds"].get("STRAWBERRY", 0))
                if straw_needed > 0 and money >= 300:
                    buy_straw = min(straw_needed, int((money - 100) // 300))
                    if buy_straw > 0:
                        market_orders.append(["BUY_SEED", "STRAWBERRY", min(4, buy_straw)])

            # Melons in SW
            if "SW" in unlocked_quads and day <= 12:
                melon_plants = sum(1 for mx, my in self.sw_melon if isinstance(me["tiles"][my][mx], dict) and me["tiles"][my][mx].get("crop") == "MELON")
                melon_needed = max(0, self.params["melon_target"] - melon_plants - private["seeds"].get("MELON", 0))
                if melon_needed > 0 and money >= 300:
                    market_orders.append(["BUY_SEED", "MELON", min(melon_needed, 6)])

            # Carrots in SW (if Pet Cafe active)
            if "SW" in unlocked_quads and carrot_target > 0 and day <= 24:
                carrot_plants = sum(1 for cx, cy in self.sw_carrot if isinstance(me["tiles"][cy][cx], dict) and me["tiles"][cy][cx].get("crop") == "CARROT")
                carrot_needed = max(0, carrot_target - carrot_plants - private["seeds"].get("CARROT", 0))
                if carrot_needed > 0 and money >= 200:
                    market_orders.append(["BUY_SEED", "CARROT", min(carrot_needed, 6)])

            # Wheat Replenishment (10 plots max)
            wheat_seeds = private["seeds"].get("WHEAT", 0)
            if day <= 26 and wheat_seeds < 8 and money >= 150:
                market_orders.append(["BUY_SEED", "WHEAT", 10])

            # Animals
            if "NE" in unlocked_quads or day >= 4:
                if total_c < cow_cap and money >= 700 and shed_total <= 90 and day < 18:
                    buy_c = min(cow_cap - total_c, int((money - 300) // 400))
                    if buy_c > 0:
                        market_orders.append(["BUY_ANIMAL", "COW", min(2, buy_c)])

                if total_s < sheep_cap and money >= 800 and shed_total <= 90 and day < 20:
                    buy_s = min(sheep_cap - total_s, int((money - 300) // 500))
                    if buy_s > 0:
                        market_orders.append(["BUY_ANIMAL", "SHEEP", min(2, buy_s)])

        # AMM Selling
        for prod in ["EGG", "MILK", "WOOL", "STRAWBERRY", "MELON", "FERTILIZER", "CARROT", "TOMATO"]:
            qty = shed.get(prod, 0)
            if qty <= 0:
                continue
            if day >= 28 or prod == "FERTILIZER":
                market_orders.append(["SELL", prod, qty])
            elif prod in GLUT_RESISTANT:
                market_orders.append(["SELL", prod, min(qty, 20)])
            elif prod == "MILK":
                if (step % 4 == 1) or hour <= 4 or shed_total >= 85:
                    market_orders.append(["SELL", "MILK", min(qty, 6)])
            elif prod in {"WOOL", "STRAWBERRY", "MELON", "CARROT"}:
                if hour <= 4 or shed_total >= 85:
                    market_orders.append(["SELL", prod, min(qty, 4)])

        # 2. Worker Dispatch & Spatial Queues
        units = [me["farmer"]] + me.get("hands", [])
        unit_actions = []
        claimed_targets = set()
        avail_seeds = dict(private["seeds"])

        # Compile global Crop Tasks
        crop_tasks = []

        # NW Wheat Tasks
        for wx, wy in self.nw_wheat:
            t = me["tiles"][wy][wx]
            if t is None:
                if avail_seeds.get("WHEAT", 0) > 0:
                    crop_tasks.append({"target": (wx, wy), "action": "PLANT_WHEAT", "crop": "WHEAT", "priority": 70})
            elif isinstance(t, dict):
                if t.get("kind") == "WEED":
                    crop_tasks.append({"target": (wx, wy), "action": "DIG", "priority": 85})
                elif t.get("kind") == "PLANT":
                    if t.get("yield_units", 0) >= 1:
                        crop_tasks.append({"target": (wx, wy), "action": "HARVEST", "priority": 80})
                    elif not t.get("watered_today", False):
                        crop_tasks.append({"target": (wx, wy), "action": "WATER", "priority": 90})

        # NE Strawberry Tasks
        if "NE" in unlocked_quads:
            for sx, sy in self.ne_strawberry:
                t = me["tiles"][sy][sx]
                if t is None:
                    if avail_seeds.get("STRAWBERRY", 0) > 0:
                        crop_tasks.append({"target": (sx, sy), "action": "PLANT_STRAWBERRY", "crop": "STRAWBERRY", "priority": 95})
                elif isinstance(t, dict):
                    if t.get("kind") == "WEED":
                        crop_tasks.append({"target": (sx, sy), "action": "DIG", "priority": 90})
                    elif t.get("kind") == "PLANT":
                        if t.get("yield_units", 0) >= 1:
                            crop_tasks.append({"target": (sx, sy), "action": "HARVEST", "priority": 95})
                        elif not t.get("watered_today", False):
                            crop_tasks.append({"target": (sx, sy), "action": "WATER", "priority": 100})

        # SW Melon & Carrot Tasks
        if "SW" in unlocked_quads:
            for mx, my in self.sw_melon:
                t = me["tiles"][my][mx]
                if t is None:
                    if avail_seeds.get("MELON", 0) > 0:
                        crop_tasks.append({"target": (mx, my), "action": "PLANT_MELON", "crop": "MELON", "priority": 95})
                elif isinstance(t, dict):
                    if t.get("kind") == "WEED":
                        crop_tasks.append({"target": (mx, my), "action": "DIG", "priority": 90})
                    elif t.get("kind") == "PLANT":
                        if t.get("yield_units", 0) >= 1:
                            crop_tasks.append({"target": (mx, my), "action": "HARVEST", "priority": 95})
                        elif not t.get("watered_today", False):
                            crop_tasks.append({"target": (mx, my), "action": "WATER", "priority": 100})

            for cx, cy in self.sw_carrot:
                t = me["tiles"][cy][cx]
                if t is None:
                    if avail_seeds.get("CARROT", 0) > 0:
                        crop_tasks.append({"target": (cx, cy), "action": "PLANT_CARROT", "crop": "CARROT", "priority": 85})
                elif isinstance(t, dict):
                    if t.get("kind") == "WEED":
                        crop_tasks.append({"target": (cx, cy), "action": "DIG", "priority": 85})
                    elif t.get("kind") == "PLANT":
                        if t.get("yield_units", 0) >= 1:
                            crop_tasks.append({"target": (cx, cy), "action": "HARVEST", "priority": 90})
                        elif not t.get("watered_today", False):
                            crop_tasks.append({"target": (cx, cy), "action": "WATER", "priority": 95})

        # Process each unit
        for u_idx, (ux, uy) in enumerate(units):
            pos = (ux, uy)
            inv = private["inventories"][u_idx] if u_idx < len(private.get("inventories", [])) else {}
            carrying_animal = "COW" if inv.get("COW", 0) > 0 else ("SHEEP" if inv.get("SHEEP", 0) > 0 else None)
            wheat_count = inv.get("WHEAT", 0)
            carrying_produce = sum(v for k, v in inv.items() if k not in {"COW", "SHEEP", "WHEAT", "GOOSE"})
            current_tile = me["tiles"][uy][ux]

            action = ["PASS"]

            # Stand and Water / Harvest current tile
            if isinstance(current_tile, dict) and current_tile.get("kind") == "PLANT":
                if not current_tile.get("watered_today", False):
                    action = ["WATER"]
                elif current_tile.get("yield_units", 0) >= 1:
                    action = ["HARVEST"]

            # Carrying Animal -> Walk to and place on Pasture
            elif carrying_animal:
                target_coords = self.cow_pastures if carrying_animal == "COW" else self.sheep_pastures
                target_spot = None
                for px, py in target_coords:
                    t = me["tiles"][py][px]
                    if isinstance(t, dict) and t.get("kind") == "PASTURE" and "animal" not in t:
                        target_spot = (px, py)
                        break
                    elif t is None:
                        target_spot = (px, py)
                        break
                if target_spot:
                    if pos == target_spot:
                        t = me["tiles"][uy][ux]
                        if t is None:
                            action = ["BUILD_PASTURE"]
                        elif isinstance(t, dict) and t.get("kind") == "PASTURE":
                            action = ["PLACE", carrying_animal, 1]
                    else:
                        action = [get_step_towards(pos, target_spot)]

            # Shed Access Tile Actions (when NOT carrying animal)
            elif pos in SHED_ACCESS_TILES:
                # 1. Drop produce
                if (carrying_produce - wheat_count) > 0:
                    action = ["DROP"]
                # 2. Pick up animals waiting in shed
                elif day < 20 and private["shed"].get("COW", 0) > 0 and u_idx < 4:
                    action = ["PICKUP", "COW", 1]
                elif day < 20 and private["shed"].get("SHEEP", 0) > 0 and u_idx < 4:
                    action = ["PICKUP", "SHEEP", 1]
                # 3. Pick up wheat feed
                elif u_idx < 4 and wheat_count < 4 and shed_wheat > 0 and hour < 16:
                    pickup_amt = min(4 - wheat_count, shed_wheat)
                    if pickup_amt > 0:
                        action = ["PICKUP", "WHEAT", pickup_amt]

                if action == ["PASS"]:
                    # Look for Animal Tasks
                    best_target = None
                    best_score = -1e9

                    # Sweep Cow and Sheep Pastures
                    for px, py in self.cow_pastures + self.sheep_pastures:
                        if (px, py) in claimed_targets:
                            continue
                        t = me["tiles"][py][px]
                        if isinstance(t, dict) and ("animal" in t):
                            is_unfed = (not t.get("fed_today", False))
                            is_uncared = (not t.get("cared_today", False))
                            has_fert = t.get("fertilizer_available", False)
                            has_yield = (t.get("yield_units", 0) >= 1)

                            if (is_unfed and wheat_count > 0) or is_uncared or has_fert or has_yield:
                                priority = 100 if (is_unfed and wheat_count > 0) else (90 if is_uncared else 80)
                                score = priority * 10 - dist(pos, (px, py))
                                if score > best_score:
                                    best_score = score
                                    best_target = (px, py)

                    if best_target:
                        claimed_targets.add(best_target)
                        tx, ty = best_target
                        if pos == best_target:
                            t = me["tiles"][ty][tx]
                            if isinstance(t, dict) and ("animal" in t):
                                if not t.get("fed_today", False) and wheat_count > 0:
                                    action = ["FEED"]
                                elif not t.get("cared_today", False):
                                    action = ["CARE"]
                                elif t.get("fertilizer_available", False):
                                    action = ["COLLECT_FERTILIZER"]
                                elif t.get("yield_units", 0) >= 1:
                                    action = ["HARVEST"]
                        else:
                            action = [get_step_towards(pos, best_target)]
                    else:
                        # If carrying produce, drop to shed
                        if carrying_produce > 0:
                            drop_tile = min(SHED_ACCESS_TILES_LIST, key=lambda p: dist(pos, p))
                            action = [get_step_towards(pos, drop_tile)]
                        # Seamlessly assist with Crop Tasks
                        else:
                            best_crop = None
                            best_crop_score = -1e9
                            for ct in crop_tasks:
                                ct_target = ct["target"]
                                if ct_target in claimed_targets:
                                    continue
                                score = ct["priority"] * 10 - dist(pos, ct_target)
                                if score > best_crop_score:
                                    best_crop_score = score
                                    best_crop = ct

                            if best_crop:
                                claimed_targets.add(best_crop["target"])
                                cx, cy = best_crop["target"]
                                if pos == (cx, cy):
                                    tact = best_crop["action"]
                                    if tact == "WATER":
                                        action = ["WATER"]
                                    elif tact == "HARVEST":
                                        action = ["HARVEST"]
                                    elif tact == "DIG":
                                        action = ["DIG"]
                                    elif tact.startswith("PLANT_"):
                                        crop_name = best_crop["crop"]
                                        if avail_seeds.get(crop_name, 0) > 0:
                                            action = ["PLANT", crop_name]
                                            avail_seeds[crop_name] -= 1
                                else:
                                    action = [get_step_towards(pos, (cx, cy))]

            # Crop Crews (Units 4+)
            else:
                # Stand and Water / Harvest
                if isinstance(current_tile, dict) and current_tile.get("kind") == "PLANT":
                    if not current_tile.get("watered_today", False):
                        action = ["WATER"]
                    elif current_tile.get("yield_units", 0) >= 1:
                        action = ["HARVEST"]

                elif pos in SHED_ACCESS_TILES and carrying_produce > 0:
                    action = ["DROP"]

                if action == ["PASS"]:
                    if carrying_produce >= 3 or (carrying_produce > 0 and hour >= 16):
                        drop_tile = min(SHED_ACCESS_TILES_LIST, key=lambda p: dist(pos, p))
                        action = [get_step_towards(pos, drop_tile)]
                    else:
                        best_task = None
                        best_score = -1e9
                        for ct in crop_tasks:
                            ct_target = ct["target"]
                            if ct_target in claimed_targets:
                                continue
                            if "crop" in ct and avail_seeds.get(ct["crop"], 0) <= 0:
                                continue
                            d = dist(pos, ct_target)
                            score = ct["priority"] * 10 - d + (500 if d == 0 else 0)
                            if score > best_score:
                                best_score = score
                                best_task = ct

                        if best_task:
                            claimed_targets.add(best_task["target"])
                            tx, ty = best_task["target"]
                            if pos == (tx, ty):
                                tact = best_task["action"]
                                if tact == "WATER":
                                    action = ["WATER"]
                                elif tact == "HARVEST":
                                    action = ["HARVEST"]
                                elif tact == "DIG":
                                    action = ["DIG"]
                                elif tact.startswith("PLANT_"):
                                    crop_name = best_task["crop"]
                                    if avail_seeds.get(crop_name, 0) > 0:
                                        action = ["PLANT", crop_name]
                                        avail_seeds[crop_name] -= 1
                            else:
                                action = [get_step_towards(pos, (tx, ty))]

            unit_actions.append(action)

        return {
            "farmer": unit_actions[0] if unit_actions else ["PASS"],
            "hands": unit_actions[1:] if len(unit_actions) > 1 else [],
            "market": market_orders[:10],
        }

_global_agent = None

def agent(obs, config=None):
    global _global_agent
    if _global_agent is None:
        _global_agent = UpgradedSpatialAgent()
    return _global_agent(obs)
