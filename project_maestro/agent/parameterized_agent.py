"""Configurable Parameterized Agent for Kaggriculture - Project Maestro

Generates agents parameterized by animal targets, quadrant unlock timing, dynamic crew sizing,
and cash crop profiles, implementing full daily CARE, FEED, FERTILIZER, HARVEST, and paced SELL loops.

References:
- kaggriculture.py:97 (LAND_PRICES)
- kaggriculture.py:99-101 (FARM_HAND_COST_MULT)
- kaggriculture.py:505 (FEED)
- kaggriculture.py:518 (CARE)
- kaggriculture.py:526 (COLLECT_FERTILIZER)
- kaggriculture.py:596-597 (SELL)
- kaggriculture.py:804-839 (pending_care_bonus, fertilizer_available)
"""

from typing import Dict, List, Any

def make_agent(
    target_cows: int,
    target_sheep: int,
    target_geese: int,
    wheat_plots: int = 8,
    cash_crop: str = "STRAWBERRY",
    cash_crop_plots: int = 4,
    day0_crew: int = 5,
    maint_crew: int = 5,
    peak_crew: int = 9,
):
    """Factory creating an autonomous agent with the specified target portfolio."""

    def agent(obs: Dict[str, Any]) -> Dict[str, Any]:
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        day = obs["day"]
        hour = obs["hour"]
        money = me["money"]

        market_orders = []
        unlocked_quads = me.get("unlocked_quadrants", [])

        # Determine daily target crew size
        is_peak = (day % 2 == 0 and day >= 6) or (day in [4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30])
        target_crew = day0_crew if day == 0 else (peak_crew if is_peak else maint_crew)

        # 1. Day-0 Purchases
        if day == 0 and hour == 0:
            for _ in range(day0_crew):
                market_orders.append(["HIRE"])
            market_orders.append(["BUY_SEED", "WHEAT", 16])
            
            init_c = min(target_cows, 4)
            init_g = min(target_geese, 4 if target_geese > 0 else 0)
            init_s = min(target_sheep, 2 if target_sheep > 0 and init_c >= 4 else 0)
            
            if init_c > 0: market_orders.append(["BUY_ANIMAL", "COW", init_c])
            if init_g > 0: market_orders.append(["BUY_ANIMAL", "GOOSE", init_g])
            if init_s > 0: market_orders.append(["BUY_ANIMAL", "SHEEP", init_s])
            
            return {"farmer": ["PASS"], "hands": [["PASS"] for _ in me.get("hands", [])], "market": market_orders[:10]}

        # 2. Daily Market Actions (Hour 0)
        if hour == 0:
            # Maintain target crew
            current_hands = len(me.get("hands", []))
            needed_hires = max(0, target_crew - current_hands)
            for _ in range(needed_hires):
                market_orders.append(["HIRE"])

            # Phased Land Unlocks
            if "NE" not in unlocked_quads and money >= 1000 and day >= 6:
                market_orders.append(["BUY_LAND"])
            elif "SW" not in unlocked_quads and money >= 2000 and day >= 10:
                market_orders.append(["BUY_LAND"])
            elif "SE" not in unlocked_quads and money >= 4000 and day >= 14 and (target_cows + target_sheep + target_geese) > 20:
                market_orders.append(["BUY_LAND"])

            # Phased Animal Expansion
            if day in [4, 6, 8, 10, 12] and money >= 800:
                if target_cows > 4 and money >= 800:
                    market_orders.append(["BUY_ANIMAL", "COW", min(4, target_cows - 4)])
                if target_sheep > 2 and money >= 1000:
                    market_orders.append(["BUY_ANIMAL", "SHEEP", min(4, target_sheep - 2)])
                if target_geese > 4 and money >= 600:
                    market_orders.append(["BUY_ANIMAL", "GOOSE", min(4, target_geese - 4)])

            # Seed Replenishment
            w_seeds = private["seeds"].get("WHEAT", 0)
            if w_seeds < 10 and money >= 100:
                market_orders.append(["BUY_SEED", "WHEAT", 16])
            
            if cash_crop and money >= 200:
                c_seeds = private["seeds"].get(cash_crop, 0)
                if c_seeds < 4:
                    market_orders.append(["BUY_SEED", cash_crop, 4])

        # 3. Market Selling from Shed (Paced)
        shed = private.get("shed", {})
        for prod in ["MILK", "WOOL", "EGG", "FERTILIZER", "WHEAT", "CARROT", "STRAWBERRY"]:
            qty = shed.get(prod, 0)
            if qty > 0:
                sell_qty = min(qty, 20) if day >= 28 else min(qty, 10)
                market_orders.append(["SELL", prod, sell_qty])

        # 4. Units Task Dispatcher
        units = [me["farmer"]] + me.get("hands", [])
        unit_actions = []

        animal_tiles = []
        plant_tiles = []
        for y in range(len(me["tiles"])):
            for x in range(len(me["tiles"][y])):
                t = me["tiles"][y][x]
                if isinstance(t, dict):
                    if "animal" in t:
                        animal_tiles.append((x, y, t))
                    elif t.get("kind") == "PLANT":
                        plant_tiles.append((x, y, t))

        for u_idx, (ux, uy) in enumerate(units):
            tile = me["tiles"][uy][ux]
            act = ["PASS"]

            if isinstance(tile, dict) and "animal" in tile:
                # Priority: Feed -> Care -> Fertilizer -> Harvest
                if not tile.get("fed_today", False):
                    act = ["FEED"]
                elif not tile.get("cared_today", False):
                    act = ["CARE"]
                elif tile.get("fertilizer_available", False):
                    act = ["COLLECT_FERTILIZER"]
                elif tile.get("yield_units", 0) > 0:
                    act = ["HARVEST"]
            elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
                if not tile.get("watered_today", False):
                    act = ["WATER"]
                elif tile.get("yield_units", 0) > 0 and (day - tile.get("planted_day", 0)) >= 2:
                    act = ["HARVEST"]
            elif tile is None:
                # Build or Plant on empty unlocked tile
                if private["seeds"].get("WHEAT", 0) > 0 and len(plant_tiles) < wheat_plots:
                    act = ["PLANT", "WHEAT"]
                elif cash_crop and private["seeds"].get(cash_crop, 0) > 0 and len(plant_tiles) < (wheat_plots + cash_crop_plots):
                    act = ["PLANT", cash_crop]
                elif len(animal_tiles) < (target_cows + target_sheep + target_geese) and money >= 100:
                    if target_geese > 0 and len(animal_tiles) < target_geese:
                        act = ["BUILD_COOP"]
                    else:
                        act = ["BUILD_PASTURE"]

            # Shed Drop when adjacent
            inv = private["inventories"][u_idx] if u_idx < len(private["inventories"]) else {}
            has_produce = sum(v for k, v in inv.items() if k not in ["WHEAT"]) > 0
            if (ux, uy) in [(4, 4), (4, 5), (5, 4), (5, 5)] and has_produce:
                act = ["DROP"]

            unit_actions.append(act)

        farmer_action = unit_actions[0] if unit_actions else ["PASS"]
        hands_actions = unit_actions[1:] if len(unit_actions) > 1 else []

        return {
            "farmer": farmer_action,
            "hands": hands_actions,
            "market": market_orders[:10],
        }

    return agent
