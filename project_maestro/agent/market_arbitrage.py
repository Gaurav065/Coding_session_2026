"""Market Arbitrage & Predictive Front-Running Engine for Project Maestro

Handles:
1. Town Shop 4-turn consumption cycle tracking & front-running.
2. Pulse sales optimization to maximize AMM price multipliers.
3. Emergency liquidity protection for daily animal feed.
4. Shed capacity overflow prevention (100-item cap).
5. Strict 10-order-per-turn limit adherence.
"""

from typing import List, Dict, Any, Tuple, Optional

SHED_SAFE_LIMIT = 85
MIN_FEED_LIQUIDITY = 150.0

SHOPS_DEMAND = {
    "BAKERY":         {"EGG": 1, "WHEAT": 1},
    "PIZZA_SHOP":     {"MILK": 1, "TOMATO": 1, "WHEAT": 1},
    "BRUNCH_SPOT":    {"EGG": 1, "WHEAT": 1, "STRAWBERRY": 1},
    "YARN_STORE":     {"WOOL": 2},  # Single-product shop consumes 2x
    "ICE_CREAM_SHOP": {"STRAWBERRY": 1, "MILK": 1, "WHEAT": 1},
    "PET_CAFE":       {"CARROT": 2},  # Single-product shop consumes 2x
    "SMOOTHIE_SHOP":  {"STRAWBERRY": 1, "MILK": 1},
    "FARMERS_MARKET": {"WHEAT": 1, "CARROT": 1, "TOMATO": 1, "STRAWBERRY": 1},
}

class MarketArbitrageEngine:
    def __init__(self):
        pass

    def compute_market_orders(
        self,
        obs: Dict[str, Any],
        player: int,
        feed_wheat_needed_today: int,
        base_market_orders: List[List[Any]]
    ) -> List[List[Any]]:
        """
        Refines and augments market orders with front-running pulses, liquidity guards,
        and shed capacity flush orders, strictly respecting max 10 orders/turn.
        """
        me = obs["farms"][player]
        private = obs.get("private", {})
        shed = private.get("shed", {})
        money = me.get("money", 0.0)
        step = obs.get("step", 0)
        hour = obs.get("hour", 0)
        
        market_orders: List[List[Any]] = list(base_market_orders)
        
        # 1. Shed Capacity Guard
        total_shed_items = sum(v for k, v in shed.items() if k not in ("GOOSE", "COW", "SHEEP"))
        if total_shed_items >= SHED_SAFE_LIMIT:
            # Must flush excess goods to avoid 100-cap deletion
            for item in ["MILK", "STRAWBERRY", "MELON", "WOOL", "TOMATO", "CARROT"]:
                qty = shed.get(item, 0)
                if qty > 0:
                    market_orders.append(["SELL", item, min(qty, 20)])
                    if len(market_orders) >= 10:
                        break

        # 2. Emergency Liquidity Guard
        # If cash < $150 and we need feed wheat, sell high-value produce immediately
        if money < MIN_FEED_LIQUIDITY and feed_wheat_needed_today > 0:
            for item in ["MILK", "STRAWBERRY", "WOOL", "MELON"]:
                qty = shed.get(item, 0)
                if qty > 0:
                    market_orders.append(["SELL", item, min(qty, 10)])
                    if len(market_orders) >= 10:
                        break

        # 3. Town Shop Pulse Front-Running
        # On steps where town shops consume product (every 4 turns), price spikes
        # Ensure we sell product into town shop demand windows
        unlocked_shops = obs.get("town", {}).get("unlocked_shops", [])
        if step % 4 == 0 and unlocked_shops:
            for shop_name in set(unlocked_shops):
                demands = SHOPS_DEMAND.get(shop_name, {})
                for item, rate in demands.items():
                    qty = shed.get(item, 0)
                    # For wheat, ensure we never sell below feed reserve
                    if item == "WHEAT":
                        sellable = max(0, qty - feed_wheat_needed_today)
                    else:
                        sellable = qty
                    if sellable > 0 and len(market_orders) < 10:
                        # Batch sell to match active shop count
                        active_count = unlocked_shops.count(shop_name)
                        sell_batch = min(sellable, rate * active_count * 2)
                        if sell_batch > 0:
                            market_orders.append(["SELL", item, sell_batch])

        # 4. Deduplicate and cap strictly at 10 orders
        final_orders = []
        seen_keys = set()
        for ord_entry in market_orders:
            if not ord_entry:
                continue
            key = (ord_entry[0], ord_entry[1] if len(ord_entry) > 1 else None)
            if key not in seen_keys and len(final_orders) < 10:
                seen_keys.add(key)
                final_orders.append(ord_entry)

        return final_orders
