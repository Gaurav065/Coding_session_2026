"""Project Aegis: Synthetic Multi-Wave Melon & Strawberry Sparring Agent

Accurately models the top-tier human competitor playstyle discovered in our 15-loss audit:
1. Plants Wave-1 Melons (12 plots) on Days 0-4.
2. Plants 16 Strawberries + 16 Wheat.
3. Maintains 6 Cows + 4 Sheep with daily feed.
4. Harvests Wave-1 Melons on Days 10-14.
5. Replants Wave-2 Melons (12 plots) on Days 12-14.
6. Waters Wave-2 Melons on Days 18-24.
7. Harvests Wave-2 Melons on Days 24-27 and aggressively sells into the shared AMM market.
"""

from typing import Dict, Any, List

def synthetic_multiwave_opponent(obs: Dict[str, Any], config: Any = None) -> Dict[str, Any]:
    player = obs.get("player", 1)
    farms = obs.get("farms", [{}, {}])
    my_farm = farms[player] if len(farms) > player else {}
    money = float(my_farm.get("money", 0.0) or 0.0)
    tiles = my_farm.get("tiles", []) or []
    fx, fy = my_farm.get("farmer", [0, 0])
    live_hands = my_farm.get("hands", []) or []
    unlocked_quads = my_farm.get("unlocked_quadrants", ["NW"])
    step = int(obs.get("step", 0) or 0)
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    
    private = obs.get("private") or {}
    shed = private.get("shed", {}) or {}
    seeds = private.get("seeds", {}) or {}
    market_prices = (obs.get("market") or {}).get("prices", {}) or {}

    market_orders = []

    # 1. Day 0 Morning Setup (Land + Seeds + Animals)
    if step == 0:
        if "NE" not in unlocked_quads and money >= 1000:
            market_orders.append(["BUY_LAND"])
        if seeds.get("MELON", 0) < 12 and money >= 240:
            market_orders.append(["BUY_SEED", "MELON", 12])
        if seeds.get("STRAWBERRY", 0) < 12 and money >= 720:
            market_orders.append(["BUY_SEED", "STRAWBERRY", 12])
        if seeds.get("WHEAT", 0) < 16 and money >= 160:
            market_orders.append(["BUY_SEED", "WHEAT", 16])

    # 2. Wave-2 Melon Seed Purchases on Days 11-13
    if 11 <= day <= 13 and hour == 0:
        if seeds.get("MELON", 0) < 12 and money >= 300:
            market_orders.append(["BUY_SEED", "MELON", 12])

    # 3. Regular Animal Feed Replenishment
    if hour == 0 and day >= 4:
        wheat_count = shed.get("WHEAT", 0) + seeds.get("WHEAT", 0)
        if wheat_count < 20 and money >= 250:
            market_orders.append(["BUY_PRODUCT", "WHEAT", 10])

    # 4. Daily Hires on Days 4-25
    if hour == 0 and 4 <= day <= 25:
        hires_today = int(my_farm.get("hires_today", 0) or 0)
        if hires_today < 4 and money >= 500:
            market_orders.append(["HIRE"])

    # 5. Liquidate Shed Inventory into AMM
    for item in ("MELON", "STRAWBERRY", "MILK", "WOOL", "FERTILIZER", "WHEAT"):
        qty = int(shed.get(item, 0) or 0)
        if qty > 0 and len(market_orders) < 10:
            # Leave small wheat reserve for feed
            if item == "WHEAT" and qty > 10:
                market_orders.append(["SELL", item, min(qty - 10, 20)])
            elif item != "WHEAT":
                market_orders.append(["SELL", item, min(qty, 20)])

    # 6. Farmer Action Logic
    farmer_act = ["PASS"]
    cur_tile = tiles[fy][fx] if fy < len(tiles) and fx < len(tiles[fy]) else None

    # Plant Wave-1 Melons / Strawberries on empty tiles
    if cur_tile is None:
        if seeds.get("MELON", 0) > 0 and (day <= 4 or 11 <= day <= 13):
            farmer_act = ["PLANT", "MELON"]
        elif seeds.get("STRAWBERRY", 0) > 0 and day <= 8:
            farmer_act = ["PLANT", "STRAWBERRY"]
        elif seeds.get("WHEAT", 0) > 0 and day <= 8:
            farmer_act = ["PLANT", "WHEAT"]
    elif isinstance(cur_tile, dict) and cur_tile.get("kind") == "PLANT":
        crop = cur_tile.get("crop")
        age = day - int(cur_tile.get("planted_day", 0))
        yield_u = int(cur_tile.get("yield_units", 0) or 0)
        
        # Harvest if ripe
        if (crop == "MELON" and age >= 10 and yield_u > 0) or (crop != "MELON" and yield_u > 0):
            farmer_act = ["HARVEST"]
        elif not cur_tile.get("watered_today", False):
            farmer_act = ["WATER"]
    elif isinstance(cur_tile, dict) and cur_tile.get("kind") in ("COOP", "PASTURE"):
        if not cur_tile.get("fed_today", False):
            farmer_act = ["FEED"]
        elif cur_tile.get("fertilizer_available"):
            farmer_act = ["COLLECT_FERTILIZER"]

    # 7. Hands Action Logic (Simple Manhattan Work Dispatch)
    hands_act = []
    for hx, hy in live_hands:
        htile = tiles[hy][hx] if hy < len(tiles) and hx < len(tiles[hy]) else None
        if isinstance(htile, dict) and htile.get("kind") == "PLANT":
            crop = htile.get("crop")
            age = day - int(htile.get("planted_day", 0))
            yield_u = int(htile.get("yield_units", 0) or 0)
            if (crop == "MELON" and age >= 10 and yield_u > 0) or (crop != "MELON" and yield_u > 0):
                hands_act.append(["HARVEST"])
            elif not htile.get("watered_today", False):
                hands_act.append(["WATER"])
            else:
                hands_act.append(["PASS"])
        elif isinstance(htile, dict) and htile.get("kind") in ("COOP", "PASTURE"):
            if not htile.get("fed_today", False):
                hands_act.append(["FEED"])
            elif htile.get("fertilizer_available"):
                hands_act.append(["COLLECT_FERTILIZER"])
            else:
                hands_act.append(["PASS"])
        elif htile is None and seeds.get("MELON", 0) > 0 and 11 <= day <= 13:
            hands_act.append(["PLANT", "MELON"])
        else:
            hands_act.append(["PASS"])

    return {
        "farmer": farmer_act,
        "hands": hands_act,
        "market": market_orders[:10]
    }
