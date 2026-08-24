"""Calibrated Reference 10C/4S/0G Baseline Agent - Project Maestro

Deterministic reference implementation of the standard 10-Cow / 4-Sheep core meta build
with daily FEED, CARE, FERTILIZER collection, wheat self-sufficiency, and paced market selling.

References:
- kaggriculture.py:97 (LAND_PRICES)
- kaggriculture.py:99-101 (FARM_HAND_COST_MULT)
- kaggriculture.py:505 (FEED)
- kaggriculture.py:518 (CARE)
- kaggriculture.py:526 (COLLECT_FERTILIZER)
- kaggriculture.py:596-597 (SELL)
- kaggriculture.py:804-839 (pending_care_bonus, fertilizer_available)
"""

from collections import defaultdict
from typing import Dict, List, Any

def create_reference_agent():
    """Factory function returning a stateful reference agent for kaggriculture."""
    
    # Internal agent memory
    state = {
        "initialized": False,
        "built_structures": set(),
        "target_cows": 10,
        "target_sheep": 4,
        "target_wheat_plots": 6,
    }

    def agent(obs: Dict[str, Any]) -> Dict[str, Any]:
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        day = obs["day"]
        hour = obs["hour"]
        money = me["money"]
        
        market_orders = []
        farmer_action = ["PASS"]
        hands_actions = [["PASS"] for _ in me.get("hands", [])]

        # 1. Day-0 Opening Purchases
        if day == 0 and hour == 0:
            # Hire 5 farmhands
            for _ in range(5):
                market_orders.append(["HIRE"])
            # Buy initial wheat seeds for feed self-sufficiency
            market_orders.append(["BUY_SEED", "WHEAT", 12])
            # Buy initial cows
            market_orders.append(["BUY_ANIMAL", "COW", 4])
            return {"farmer": ["PASS"], "hands": hands_actions, "market": market_orders}

        # 2. Daily Market Hires & Land Expansion
        if hour == 0:
            # Daily dynamic crew maintenance (5 hands)
            current_hands = len(me.get("hands", []))
            needed_hires = max(0, 5 - current_hands)
            for _ in range(needed_hires):
                market_orders.append(["HIRE"])

            # Phased Land Unlocks
            unlocked_quads = me.get("unlocked_quadrants", [])
            if "NE" not in unlocked_quads and money >= 1000 and day >= 6:
                market_orders.append(["BUY_LAND"])
            elif "SW" not in unlocked_quads and money >= 2000 and day >= 10:
                market_orders.append(["BUY_LAND"])

            # Phased Animal Expansion
            if day >= 4 and money >= 800:
                # Buy remaining cows/sheep
                market_orders.append(["BUY_ANIMAL", "COW", 2])
                market_orders.append(["BUY_ANIMAL", "SHEEP", 2])
            if day >= 8 and money >= 1200:
                market_orders.append(["BUY_ANIMAL", "COW", 4])
                market_orders.append(["BUY_ANIMAL", "SHEEP", 2])

            # Seed replenishments
            wheat_seeds = private["seeds"].get("WHEAT", 0)
            if wheat_seeds < 8 and money >= 100:
                market_orders.append(["BUY_SEED", "WHEAT", 12])

        # 3. Market Selling from Shed
        shed = private.get("shed", {})
        for prod in ["MILK", "WOOL", "EGG", "FERTILIZER", "WHEAT"]:
            qty = shed.get(prod, 0)
            if qty > 0:
                # Sell up to market order capacity
                sell_qty = min(qty, 20)
                market_orders.append(["SELL", prod, sell_qty])

        # 4. Units Task Dispatcher (Farmer + Hands)
        units = [me["farmer"]] + me.get("hands", [])
        unit_actions = []

        # Find all animal tiles and plant tiles
        animal_tiles = []
        plant_tiles = []
        empty_tiles = []
        for y in range(len(me["tiles"])):
            for x in range(len(me["tiles"][y])):
                t = me["tiles"][y][x]
                if t is None:
                    # Unlocked empty tile
                    empty_tiles.append((x, y))
                elif isinstance(t, dict):
                    if "animal" in t:
                        animal_tiles.append((x, y, t))
                    elif t.get("kind") == "PLANT":
                        plant_tiles.append((x, y, t))

        # Assign actions to units
        for u_idx, (ux, uy) in enumerate(units):
            tile = me["tiles"][uy][ux]
            act = ["PASS"]

            if isinstance(tile, dict) and "animal" in tile:
                # Priority 1: Feed if unfed
                if not tile.get("fed_today", False):
                    act = ["FEED"]
                # Priority 2: Care if not cared
                elif not tile.get("cared_today", False):
                    act = ["CARE"]
                # Priority 3: Collect fertilizer if available
                elif tile.get("fertilizer_available", False):
                    act = ["COLLECT_FERTILIZER"]
                # Priority 4: Harvest product if ready
                elif tile.get("yield_units", 0) > 0:
                    act = ["HARVEST"]
            elif isinstance(tile, dict) and tile.get("kind") == "PLANT":
                # Plant maintenance
                if not tile.get("watered_today", False):
                    act = ["WATER"]
                elif tile.get("yield_units", 0) > 0 and (day - tile.get("planted_day", 0)) >= 2:
                    act = ["HARVEST"]
            elif tile is None:
                # Empty tile: build or plant
                if private["seeds"].get("WHEAT", 0) > 0 and len(plant_tiles) < 8:
                    act = ["PLANT", "WHEAT"]
                elif len(animal_tiles) < 14 and money >= 100:
                    act = ["BUILD_PASTURE"]

            # If unit has items and standing adjacent to shed (4,4), (4,5), (5,4), (5,5)
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
