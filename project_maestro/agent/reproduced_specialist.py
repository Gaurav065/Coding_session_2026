"""High-Fidelity Reproduced Specialist Agent (Ahmad Ali 14S / 33M / 0C Architecture)

Implements the complete empirical mechanism that generated $125,288 in Match 99064717:
1. Day 0 Opening: 4 Sheep in NW, 8 Melons in NW, 10 Wheat Feed, 5-8 Hires.
2. Livestock Engine: Daily FEED, CARE (+1 wool bonus), and COLLECT_FERTILIZER on all 14 sheep.
3. Crop Engine: Daily WATER + FERTILIZE during melon bonus window (Days 4-9) using collected fertilizer.
4. Capital Recycling: Day 10 Melon harvest generates $15k+ cash, funding NE (Day 6), SW (Day 10), SE (Day 11) unlocks and Sheep expansion to 14.
5. Dynamic Task-Priority Dispatcher: Units dynamically claim and execute highest-priority tasks (Livestock -> Melon Fertilize/Water -> Replant -> Shed).
"""

from typing import Dict, List, Tuple, Optional, Any, Set
from project_maestro.agent.dispatcher_agent import (
    BASE_PRICES,
    get_step_towards,
    dist,
    SHED_ACCESS_TILES_LIST
)

# 14 Sheep Pastures in NW
NW_SHEEP_PASTURES = [
    (4, 3), (3, 4),
    (4, 2), (3, 3), (2, 4),
    (4, 1), (3, 2), (2, 3), (1, 4),
    (4, 0), (3, 1), (2, 2), (1, 3), (0, 4)
]

# Day 0 Early Melons in NW
NW_EARLY_MELONS = [
    (0, 0), (1, 0), (2, 0), (3, 0),
    (0, 1), (1, 1), (2, 1), (0, 2)
]

# SW & SE Expansion Melons
SW_MELONS = [
    (0, 5), (1, 5), (2, 5), (3, 5), (4, 5),
    (0, 6), (1, 6), (2, 6), (3, 6), (4, 6),
    (0, 7), (1, 7), (2, 7), (3, 7), (4, 7),
    (0, 8), (1, 8), (2, 8), (3, 8), (4, 8),
    (0, 9), (1, 9), (2, 9), (3, 9), (4, 9)
]

SE_MELONS = [
    (5, 5), (6, 5), (7, 5), (8, 5), (9, 5),
    (5, 6), (6, 6), (7, 6), (8, 6), (9, 6),
    (5, 7), (6, 7), (7, 7), (8, 7), (9, 7)
]

# NE Strawberries
NE_STRAWBERRIES = [
    (5, 0), (6, 0), (7, 0), (8, 0), (9, 0),
    (5, 1), (6, 1), (7, 1), (8, 1), (9, 1),
    (5, 2), (6, 2), (7, 2), (8, 2), (9, 2)
]


class ReproducedSpecialistAgent:
    """Accurate, robust implementation of the $125k Specialist Architecture."""
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self.placed_sheep: Set[Tuple[int, int]] = set()
        self.target_sheep = 4

    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        player = obs["player"]
        day = obs["day"]
        hour = obs["hour"]
        me = obs["farms"][player]
        money = me["money"]
        tiles = me["tiles"]
        farmer = me["farmer"]
        hands = me.get("hands", [])
        num_units = 1 + len(hands)
        private = obs["private"]
        shed = private.get("shed", {})
        seeds = private.get("seeds", {})
        inventories = private.get("inventories", [{} for _ in range(num_units)])
        unlocked = me.get("unlocked_quadrants", ["NW"])

        market = []

        # -------------------------------------------------------------
        # 1. Market Engine (Spanning hours 0-2 to never exceed 10/turn)
        # -------------------------------------------------------------
        if hour == 0:
            # 1. FEED FIRST: Always ensure feed is bought before anything else!
            daily_feed = max(4, len(self.placed_sheep), self.target_sheep)
            shed_wheat = shed.get("WHEAT", 0)
            if day < 29 and shed_wheat < daily_feed * 2 and money >= 100:
                buy_feed = min(daily_feed * 2 - shed_wheat, int(money // 25), 8)
                if buy_feed > 0:
                    market.append(["BUY_PRODUCT", "WHEAT", buy_feed])

            # 2. Hires (Batch 1: 5 hires)
            target_hires = 5 if day < 3 else (8 if day < 7 else 10)
            hires_batch1 = min(5, target_hires - me.get("hires_today", 0))
            for _ in range(hires_batch1):
                if len(market) < 10:
                    market.append(["HIRE"])

            # Seed Purchases
            if day == 0 and seeds.get("MELON", 0) < 8 and money >= 800:
                market.append(["BUY_SEED", "MELON", 8])
            elif "NE" in unlocked and day <= 8 and seeds.get("MELON", 0) < 12 and money >= 1200:
                market.append(["BUY_SEED", "MELON", min(10, int(money // 100))])
            elif "SW" in unlocked and day <= 18 and seeds.get("MELON", 0) < 15 and money >= 1500:
                market.append(["BUY_SEED", "MELON", min(8, int(money // 100))])

        elif hour == 1:
            # Hires (Batch 2: remaining hires up to target)
            target_hires = 5 if day < 3 else (8 if day < 7 else 10)
            hires_batch2 = max(0, min(target_hires - me.get("hires_today", 0), 6))
            for _ in range(hires_batch2):
                if len(market) < 10:
                    market.append(["HIRE"])

            # Land Unlocks
            if "NE" not in unlocked and money >= 1000 and day >= 5:
                market.append(["BUY_LAND"])
            elif "SW" not in unlocked and money >= 2000 and day >= 9:
                market.append(["BUY_LAND"])
            elif "SE" not in unlocked and money >= 4000 and day >= 10:
                market.append(["BUY_LAND"])

            # Sheep Target Scaling & Purchasing
            if day >= 10 and money >= 2500:
                self.target_sheep = 14
            elif day >= 6 and money >= 1200:
                self.target_sheep = 8
            elif day >= 0:
                self.target_sheep = 4

            sheep_needed = max(0, self.target_sheep - len(self.placed_sheep))
            sheep_in_shed = shed.get("SHEEP", 0)
            if sheep_needed > sheep_in_shed and money >= 500:
                buy_n = min(sheep_needed - sheep_in_shed, int(money // 500), 4)
                if buy_n > 0 and len(market) < 10:
                    market.append(["BUY_ANIMAL", "SHEEP", buy_n])

        elif hour == 2:
            if "NE" in unlocked and seeds.get("STRAWBERRY", 0) < 15 and money >= 1200:
                market.append(["BUY_SEED", "STRAWBERRY", min(8, int(money // 150))])

        # Daily Sells (Never sell WHEAT - it is animal feed!)
        for prod in ["WOOL", "MELON", "STRAWBERRY", "FERTILIZER", "TOMATO", "CARROT"]:
            qty = shed.get(prod, 0)
            if qty > 0 and len(market) < 10:
                sell_n = min(qty, 20)
                market.append(["SELL", prod, sell_n])

        # -------------------------------------------------------------
        # 2. Dynamic Worker Task Dispatcher
        # -------------------------------------------------------------
        unit_positions = [farmer] + hands
        actions = [["PASS"] for _ in range(num_units)]
        assigned_targets = set()

        # Build list of active tasks with coordinates and priorities
        tasks = [] # (priority, (x, y), task_type, payload)

        # A. Pasture Tasks (NW)
        active_pastures = NW_SHEEP_PASTURES[:self.target_sheep]
        for px, py in active_pastures:
            ptile = tiles[py][px]
            if ptile is None:
                tasks.append((100, (px, py), "BUILD_PASTURE", None))
            elif isinstance(ptile, dict) and ptile.get("kind") == "PASTURE":
                if "animal" not in ptile:
                    tasks.append((95, (px, py), "PLACE_SHEEP", None))
                else:
                    self.placed_sheep.add((px, py))
                    # Harvest Wool
                    if ptile.get("yield_units", 0) > 0:
                        tasks.append((90, (px, py), "HARVEST", None))
                    # Collect Fertilizer
                    if ptile.get("fertilizer_available", False):
                        tasks.append((85, (px, py), "COLLECT_FERTILIZER", None))
                    # Feed
                    if not ptile.get("fed_today", False):
                        tasks.append((80, (px, py), "FEED", None))
                    # Care (+1 wool bonus payout)
                    if ptile.get("fed_today", False) and not ptile.get("cared_today", False):
                        tasks.append((75, (px, py), "CARE", None))

        # B. Crop Tasks (Melons in NW, NE, and SW)
        crop_targets = list(NW_EARLY_MELONS)
        if "NE" in unlocked: crop_targets.extend(NE_STRAWBERRIES) # Used for NE Melons
        if "SW" in unlocked: crop_targets.extend(SW_MELONS)
        if "SE" in unlocked: crop_targets.extend(SE_MELONS)

        for cx, cy in crop_targets:
            ctile = tiles[cy][cx]
            if ctile is None:
                if seeds.get("MELON", 0) > 0:
                    tasks.append((70, (cx, cy), "PLANT_MELON", None))
                elif seeds.get("STRAWBERRY", 0) > 0:
                    tasks.append((60, (cx, cy), "PLANT_STRAWBERRY", None))
            elif isinstance(ctile, dict) and ctile.get("kind") == "PLANT":
                crop = ctile.get("crop")
                age = day - ctile.get("planted_day", 0)
                # Harvest
                if (crop == "MELON" and age >= 10 and ctile.get("yield_units", 0) > 0) or \
                   (crop == "STRAWBERRY" and ctile.get("yield_units", 0) > 0):
                    tasks.append((92, (cx, cy), "HARVEST", None))
                # Fertilize (during melon bonus window Days 4-9)
                fert_until = ctile.get("fertilized_until_day", -1)
                if crop == "MELON" and 4 <= age <= 9 and fert_until < day:
                    tasks.append((86, (cx, cy), "FERTILIZE", None))
                # Water
                if not ctile.get("watered_today", False):
                    tasks.append((78, (cx, cy), "WATER", None))

        # Assign each unit to its best available task
        for u_idx in range(num_units):
            ux, uy = unit_positions[u_idx]
            u_inv = inventories[u_idx]
            curr_tile = tiles[uy][ux] if uy < len(tiles) and ux < len(tiles[0]) else None

            # Immediate on-tile execution if standing on task tile
            standing_act = None
            if curr_tile is None:
                if (ux, uy) in active_pastures:
                    standing_act = ["BUILD_PASTURE"]
                elif (ux, uy) in NW_EARLY_MELONS and seeds.get("MELON", 0) > 0:
                    standing_act = ["PLANT", "MELON"]
                elif ((ux, uy) in SW_MELONS or (ux, uy) in SE_MELONS) and seeds.get("MELON", 0) > 0:
                    standing_act = ["PLANT", "MELON"]
                elif (ux, uy) in NE_STRAWBERRIES and seeds.get("STRAWBERRY", 0) > 0:
                    standing_act = ["PLANT", "STRAWBERRY"]
            elif isinstance(curr_tile, dict):
                k = curr_tile.get("kind")
                if k == "PASTURE":
                    if "animal" not in curr_tile and u_inv.get("SHEEP", 0) > 0:
                        standing_act = ["PLACE", "SHEEP"]
                    elif curr_tile.get("yield_units", 0) > 0:
                        standing_act = ["HARVEST"]
                    elif curr_tile.get("fertilizer_available", False):
                        standing_act = ["COLLECT_FERTILIZER"]
                    elif not curr_tile.get("fed_today", False) and u_inv.get("WHEAT", 0) > 0:
                        standing_act = ["FEED"]
                    elif curr_tile.get("fed_today", False) and not curr_tile.get("cared_today", False):
                        standing_act = ["CARE"]
                elif k == "PLANT":
                    crop = curr_tile.get("crop")
                    age = day - curr_tile.get("planted_day", 0)
                    if (crop == "MELON" and age >= 10 and curr_tile.get("yield_units", 0) > 0) or \
                       (crop == "STRAWBERRY" and curr_tile.get("yield_units", 0) > 0):
                        standing_act = ["HARVEST"]
                    elif crop == "MELON" and 4 <= age <= 9 and curr_tile.get("fertilized_until_day", -1) < day and u_inv.get("FERTILIZER", 0) > 0:
                        standing_act = ["FERTILIZE"]
                    elif not curr_tile.get("watered_today", False):
                        standing_act = ["WATER"]

            if standing_act:
                actions[u_idx] = standing_act
                continue

            # Need items from shed?
            need_wheat = (u_inv.get("WHEAT", 0) == 0 and shed.get("WHEAT", 0) > 0 and u_idx < 4)
            need_sheep = (u_inv.get("SHEEP", 0) == 0 and shed.get("SHEEP", 0) > 0 and len(self.placed_sheep) < self.target_sheep and u_idx < 2)
            need_fert = (u_inv.get("FERTILIZER", 0) == 0 and shed.get("FERTILIZER", 0) > 0 and u_idx >= 4)

            if need_wheat or need_sheep or need_fert:
                if (ux, uy) in SHED_ACCESS_TILES_LIST:
                    if need_sheep:
                        actions[u_idx] = ["PICKUP", "SHEEP", 1]
                    elif need_wheat:
                        actions[u_idx] = ["PICKUP", "WHEAT", min(10, shed.get("WHEAT", 0))]
                    elif need_fert:
                        actions[u_idx] = ["PICKUP", "FERTILIZER", min(5, shed.get("FERTILIZER", 0))]
                    continue
                else:
                    target_shed = SHED_ACCESS_TILES_LIST[u_idx % len(SHED_ACCESS_TILES_LIST)]
                    actions[u_idx] = [get_step_towards((ux, uy), target_shed)]
                    continue

            # Path towards best unassigned task
            best_task = None
            best_score = -9999
            for prio, (tx, ty), ttype, _ in tasks:
                if (tx, ty) in assigned_targets:
                    continue
                d = dist((ux, uy), (tx, ty))
                score = prio * 10 - d
                if score > best_score:
                    best_score = score
                    best_task = (tx, ty)

            if best_task:
                assigned_targets.add(best_task)
                actions[u_idx] = [get_step_towards((ux, uy), best_task)]
            else:
                actions[u_idx] = ["PASS"]

        return {
            "farmer": actions[0],
            "hands": actions[1:],
            "market": market
        }


def make_reproduced_specialist(seed: Optional[int] = None):
    agent = ReproducedSpecialistAgent(seed=seed)
    return lambda obs: agent(obs)
