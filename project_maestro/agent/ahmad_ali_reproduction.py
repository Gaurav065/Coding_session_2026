"""Ahmad Ali Specialist Exact Reproduction Agent — Project Maestro

Faithfully replicates the observed high-scoring mechanics from match 99064717:
1. Day 0 Opening: 4 Sheep in NW, 8 Melons in NW, 10 Wheat Feed, 5 Hires.
2. Dedicated Animal Crew: Feeds, Cares (+1 yield payout on wool), and Collects Fertilizer daily.
3. Crop Crew: Waters and FERTILIZES melons/strawberries/crops using collected fertilizer.
4. Early Melon Cashflow: Day 0 NW Melons harvest on Day 10, funding NE/SW/SE unlocks and Sheep expansion to 14.
5. Market Operations: Daily feed replenishment (BUY_PRODUCT WHEAT) and daily excess fertilizer/wool/melon sales.
"""

from typing import Dict, List, Tuple, Optional, Any
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent,
    BASE_PRICES,
    get_step_towards,
    dist,
    SHED_ACCESS_TILES,
)

# 14 Sheep Pasture Coordinates (NW quadrant)
AHMAD_SHEEP_PASTURES = [
    (4, 3), (3, 4),
    (4, 2), (3, 3), (2, 4),
    (4, 1), (3, 2), (2, 3), (1, 4),
    (4, 0), (3, 1), (2, 2), (1, 3), (0, 4)
]

# Day 0 Early Melons (NW quadrant remaining tiles)
NW_EARLY_MELONS = [
    (0, 0), (1, 0), (2, 0), (3, 0),
    (0, 1), (1, 1), (2, 1),
    (0, 2)
]

# SW Expansion Melons
SW_MELONS = [
    (0, 5), (1, 5), (2, 5), (3, 5), (4, 5),
    (0, 6), (1, 6), (2, 6), (3, 6), (4, 6),
    (0, 7), (1, 7), (2, 7), (3, 7), (4, 7),
    (0, 8), (1, 8), (2, 8), (3, 8), (4, 8),
    (0, 9), (1, 9), (2, 9), (3, 9), (4, 9)
]

# NE Strawberries
NE_STRAWBERRIES = [
    (5, 0), (6, 0), (7, 0), (8, 0), (9, 0),
    (5, 1), (6, 1), (7, 1), (8, 1), (9, 1),
    (5, 2), (6, 2), (7, 2), (8, 2), (9, 2),
    (5, 3), (6, 3), (7, 3)
]


class AhmadAliSpecialistAgent:
    """Accurate behavioral clone of Ahmad Ali's 14S/33M/0C engine."""
    def __init__(self, seed: Optional[int] = None):
        self.seed = seed
        self.pastures_built = set()
        self.sheep_placed = set()
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
        # 1. Market Orders & Strategy
        # -------------------------------------------------------------
        if hour == 0:
            # Daily Hires (up to 10 hands/day as capital permits)
            target_hires = 5 if day < 3 else (8 if day < 10 else 10)
            hires_to_make = max(0, min(target_hires - me.get("hires_today", 0), 10))
            for _ in range(hires_to_make):
                if len(market) < 10:
                    market.append(["HIRE"])

            # Land Unlocks
            if "NE" not in unlocked and money >= 1000 and day >= 5:
                market.append(["BUY_LAND"])
            elif "SW" not in unlocked and money >= 2000 and day >= 9:
                market.append(["BUY_LAND"])
            elif "SE" not in unlocked and money >= 4000 and day >= 10:
                market.append(["BUY_LAND"])

            # Sheep Target Scaling
            if day >= 10 and money >= 3000:
                self.target_sheep = 14
            elif day >= 6 and money >= 1500:
                self.target_sheep = 8
            elif day >= 0:
                self.target_sheep = 4

            # Sheep Purchases
            sheep_needed = max(0, self.target_sheep - len(self.sheep_placed))
            sheep_in_shed = shed.get("SHEEP", 0)
            if sheep_needed > sheep_in_shed and money >= 500:
                buy_cnt = min(sheep_needed - sheep_in_shed, int(money // 500), 4)
                if buy_cnt > 0 and len(market) < 10:
                    market.append(["BUY_ANIMAL", "SHEEP", buy_cnt])

            # Feed Replenishment (BUY_PRODUCT WHEAT)
            daily_feed_req = len(self.sheep_placed)
            shed_wheat = shed.get("WHEAT", 0)
            if day < 29 and shed_wheat < daily_feed_req * 2 and money >= 100:
                feed_to_buy = min(daily_feed_req * 2 - shed_wheat, int(money // 25), 10)
                if feed_to_buy > 0 and len(market) < 10:
                    market.append(["BUY_PRODUCT", "WHEAT", feed_to_buy])

            # Seed Purchases
            if day == 0 and seeds.get("MELON", 0) < 8 and money >= 800:
                market.append(["BUY_SEED", "MELON", 8])
            if "SW" in unlocked and day <= 16 and seeds.get("MELON", 0) < 20 and money >= 1500:
                market.append(["BUY_SEED", "MELON", min(10, int(money // 100))])
            if "NE" in unlocked and seeds.get("STRAWBERRY", 0) < 15 and money >= 1000:
                market.append(["BUY_SEED", "STRAWBERRY", min(10, int(money // 150))])

        # Daily Sells (every turn or synchronized)
        for prod in ["WOOL", "MELON", "STRAWBERRY", "FERTILIZER", "TOMATO", "CARROT"]:
            qty = shed.get(prod, 0)
            if qty > 0 and len(market) < 10:
                # Sell in paced or full batches
                sell_n = min(qty, 20 if prod == "FERTILIZER" else 10)
                market.append(["SELL", prod, sell_n])

        # -------------------------------------------------------------
        # 2. Worker Unit Actions
        # -------------------------------------------------------------
        unit_positions = [farmer] + hands
        actions = [["PASS"] for _ in range(num_units)]

        # Classify active pastures and crops
        active_pastures = AHMAD_SHEEP_PASTURES[:self.target_sheep]
        
        # Dispatch workers:
        # Unit 0 (Farmer) + Unit 1-3: Livestock Masters (Feed, Care, Collect Fert, Build)
        # Unit 4+: Crop Crew (Water, Fertilize, Harvest, Plant)
        for u_idx in range(num_units):
            ux, uy = unit_positions[u_idx]
            u_inv = inventories[u_idx]
            curr_tile = tiles[uy][ux] if uy < len(tiles) and ux < len(tiles[0]) else None

            # ---------------- Livestock Worker ----------------
            if u_idx < 3:
                # 1. Pasture Maintenance on current tile
                if (ux, uy) in active_pastures:
                    if curr_tile is None:
                        actions[u_idx] = ["BUILD_PASTURE"]
                        continue
                    elif isinstance(curr_tile, dict) and curr_tile.get("kind") == "PASTURE":
                        if "animal" not in curr_tile:
                            if u_inv.get("SHEEP", 0) > 0:
                                actions[u_idx] = ["PLACE", "SHEEP"]
                                self.sheep_placed.add((ux, uy))
                                continue
                            elif (ux, uy) in SHED_ACCESS_TILES and shed.get("SHEEP", 0) > 0:
                                actions[u_idx] = ["PICKUP", "SHEEP", 1]
                                continue
                        else:
                            # Animal present
                            self.sheep_placed.add((ux, uy))
                            # Collect Fertilizer
                            if curr_tile.get("fertilizer_available", False):
                                actions[u_idx] = ["COLLECT_FERTILIZER"]
                                continue
                            # Feed
                            if not curr_tile.get("fed_today", False):
                                if u_inv.get("WHEAT", 0) > 0:
                                    actions[u_idx] = ["FEED"]
                                    continue
                                elif (ux, uy) in SHED_ACCESS_TILES and shed.get("WHEAT", 0) > 0:
                                    actions[u_idx] = ["PICKUP", "WHEAT", min(10, shed.get("WHEAT", 0))]
                                    continue
                            # Care (+1 yield payout)
                            if curr_tile.get("fed_today", False) and not curr_tile.get("cared_today", False):
                                actions[u_idx] = ["CARE"]
                                continue
                            # Harvest product on tile
                            if curr_tile.get("yield_units", 0) > 0:
                                actions[u_idx] = ["HARVEST"]
                                continue

                SHED_LIST = [(4, 4), (5, 4), (4, 5), (5, 5)]
                # 2. If needs wheat / sheep from shed, walk to shed
                if (u_inv.get("WHEAT", 0) == 0 and shed.get("WHEAT", 0) > 0) or (u_inv.get("SHEEP", 0) == 0 and shed.get("SHEEP", 0) > 0 and len(self.sheep_placed) < self.target_sheep):
                    if (ux, uy) in SHED_LIST:
                        if shed.get("SHEEP", 0) > 0 and len(self.sheep_placed) < self.target_sheep:
                            actions[u_idx] = ["PICKUP", "SHEEP", 1]
                        elif shed.get("WHEAT", 0) > 0:
                            actions[u_idx] = ["PICKUP", "WHEAT", min(10, shed.get("WHEAT", 0))]
                        continue
                    else:
                        target = SHED_LIST[u_idx % len(SHED_LIST)]
                        actions[u_idx] = [get_step_towards((ux, uy), target)]
                        continue

                # 3. Find next pasture needing action
                best_pasture = None
                best_dist = 999
                for px, py in active_pastures:
                    ptile = tiles[py][px]
                    needs_act = False
                    if ptile is None or (isinstance(ptile, dict) and ptile.get("kind") == "PASTURE" and (
                        "animal" not in ptile or
                        ptile.get("fertilizer_available", False) or
                        not ptile.get("fed_today", False) or
                        (ptile.get("fed_today", False) and not ptile.get("cared_today", False)) or
                        ptile.get("yield_units", 0) > 0
                    )):
                        needs_act = True
                    if needs_act:
                        d = dist((ux, uy), (px, py))
                        if d < best_dist:
                            best_dist = d
                            best_pasture = (px, py)

                if best_pasture:
                    actions[u_idx] = [get_step_towards((ux, uy), best_pasture)]
                    continue

            # ---------------- Crop Worker ----------------
            else:
                # Target plots: NW Early Melons + SW Melons + NE Strawberries
                target_plots = list(NW_EARLY_MELONS)
                if "SW" in unlocked:
                    target_plots.extend(SW_MELONS)
                if "NE" in unlocked:
                    target_plots.extend(NE_STRAWBERRIES)

                # If on crop plot
                if (ux, uy) in target_plots:
                    if curr_tile is None:
                        # Decide what to plant
                        if (ux, uy) in NW_EARLY_MELONS and seeds.get("MELON", 0) > 0:
                            actions[u_idx] = ["PLANT", "MELON"]
                            continue
                        elif (ux, uy) in SW_MELONS and seeds.get("MELON", 0) > 0:
                            actions[u_idx] = ["PLANT", "MELON"]
                            continue
                        elif (ux, uy) in NE_STRAWBERRIES and seeds.get("STRAWBERRY", 0) > 0:
                            actions[u_idx] = ["PLANT", "STRAWBERRY"]
                            continue
                    elif isinstance(curr_tile, dict) and curr_tile.get("kind") == "PLANT":
                        crop = curr_tile.get("crop")
                        age = day - curr_tile.get("planted_day", 0)
                        
                        # Harvest
                        if crop == "MELON" and age >= 10 and curr_tile.get("yield_units", 0) > 0:
                            actions[u_idx] = ["HARVEST"]
                            continue
                        elif crop == "STRAWBERRY" and curr_tile.get("yield_units", 0) > 0:
                            actions[u_idx] = ["HARVEST"]
                            continue
                            
                        # Fertilize (using collected fertilizer if available)
                        fert_until = curr_tile.get("fertilized_until_day", -1)
                        if fert_until < day and u_inv.get("FERTILIZER", 0) > 0:
                            actions[u_idx] = ["FERTILIZE"]
                            continue
                            
                        # Water
                        if not curr_tile.get("watered_today", False):
                            actions[u_idx] = ["WATER"]
                            continue

                # Find next crop plot needing care
                best_plot = None
                best_dist = 999
                for cx, cy in target_plots:
                    ctile = tiles[cy][cx]
                    needs_care = False
                    if ctile is None:
                        if ((cx, cy) in NW_EARLY_MELONS or (cx, cy) in SW_MELONS) and seeds.get("MELON", 0) > 0:
                            needs_care = True
                        elif (cx, cy) in NE_STRAWBERRIES and seeds.get("STRAWBERRY", 0) > 0:
                            needs_care = True
                    elif isinstance(ctile, dict) and ctile.get("kind") == "PLANT":
                        crop = ctile.get("crop")
                        age = day - ctile.get("planted_day", 0)
                        if (crop == "MELON" and age >= 10 and ctile.get("yield_units", 0) > 0) or \
                           (crop == "STRAWBERRY" and ctile.get("yield_units", 0) > 0) or \
                           (not ctile.get("watered_today", False)):
                            needs_care = True
                    if needs_care:
                        d = dist((ux, uy), (cx, cy))
                        if d < best_dist:
                            best_dist = d
                            best_plot = (cx, cy)

                if best_plot:
                    actions[u_idx] = [get_step_towards((ux, uy), best_plot)]
                    continue

            actions[u_idx] = ["PASS"]

        return {
            "farmer": actions[0],
            "hands": actions[1:],
            "market": market
        }


def make_ahmad_ali_reproduction(seed: Optional[int] = None):
    agent_instance = AhmadAliSpecialistAgent(seed=seed)
    return lambda obs: agent_instance(obs)
