"""Instant Dynamic Calculator (IDC) Engine — High-Capacity Scaling

Calculates:
1. Dynamic labor crew scaling: expands to 13-14 workers when bank > $4,000 to farm 25 Strawberries + 14 Melons.
2. Dynamic livestock targets (C*, S*) driven by shop counts.
3. Zero-waste feed wheat budgeting.
4. AMM first-mover front-running orders.
"""

import math
from typing import Dict, List, Tuple, Any, Optional

BOARD_SIZE = 10
PRICE_FLOOR = 1

# Fibonacci hire cost table
FIB_COSTS = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987]

class InstantDynamicCalculator:
    def __init__(self):
        pass

    @staticmethod
    def calculate_daily_crew(day: int, unlocked_quads: List[str], bank_money: float) -> int:
        """
        Dynamically scales daily crew:
        - Day 0: 4 hands (setup)
        - Day 1-3: 5 hands (early pasture ramp)
        - Day 4-7: 9 hands (NE strawberry expansion)
        - Day 8-26: 10 hands base, expanding to 13-14 hands if bank > $4,000 (unlocks 25 Strawberries + 14 Melons)
        - Day 27+: 10 hands (slight late contraction to save final bank cash)
        """
        if day == 0:
            return 4
        elif day < 4:
            return 5
        elif day >= 27:
            return 10
        elif "SW" in unlocked_quads or day >= 8:
            if bank_money >= 5000:
                return 13  # High-throughput production crew
            elif bank_money >= 3000:
                return 12
            else:
                return 10
        elif "NE" in unlocked_quads or day >= 4:
            return 9
        else:
            return 5

    @staticmethod
    def calculate_livestock_targets(town_shops: List[str], day: int) -> Tuple[int, int]:
        """
        Calculates exact closed-form Cow and Sheep headcount targets (C*, S*).
        """
        if day >= 18:
            return 0, 0

        s_yarn = town_shops.count("YARN_STORE")
        s_dairy = sum(1 for s in town_shops if s in ("SMOOTHIE_SHOP", "ICE_CREAM_SHOP", "PIZZA_SHOP"))

        if s_yarn >= 2:
            return 4, 10
        elif s_dairy >= 2:
            return 12, 2
        else:
            return 9, 4

    @staticmethod
    def calculate_feed_wheat_budget(day: int, live_animals: int, total_current_wheat: int) -> Tuple[int, int]:
        remaining_days = max(0, 30 - day)
        required_lifetime_wheat = remaining_days * live_animals

        if total_current_wheat < required_lifetime_wheat:
            needed = min(10, required_lifetime_wheat - total_current_wheat)
            return needed, 0
        elif total_current_wheat > (required_lifetime_wheat + 5):
            surplus = total_current_wheat - required_lifetime_wheat
            return 0, min(10, surplus)
        else:
            return 0, 0

    @staticmethod
    def calculate_optimal_liquidation(
        shed: Dict[str, int],
        market_inv: Dict[str, int],
        town_shops: List[str],
        step: int,
        day: int
    ) -> List[List[Any]]:
        orders = []
        if day >= 28:
            for item in ["MILK", "WOOL", "STRAWBERRY", "MELON", "TOMATO", "CARROT", "WHEAT", "FERTILIZER"]:
                qty = shed.get(item, 0)
                if qty > 0 and len(orders) < 10:
                    orders.append(["SELL", item, min(qty, 20)])
            return orders[:10]
        return orders
