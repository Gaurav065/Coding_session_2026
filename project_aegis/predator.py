"""Project Aegis - Module 1: The Predator (Dynamic Opponent Forensics & Public Tile Estimator)

Tracks opponent's visible tiles, harvest state transitions, and shed-deposit timings
to calculate real-time shed accumulation and execute targeted front-running without hardcoded tables.
"""

from typing import Dict, List, Any, Optional, Set, Tuple
from project_aegis.core import (
    MARKET_PARAMS,
    PREMIUM_PRODUCTS,
    SHED_CAPACITY,
    MAX_MARKET_ORDERS,
    calculate_single_unit_price,
    PureDebtManager,
)

# Coordinates adjacent to the central shed (where items are deposited into the shed)
SHED_ADJACENT_TILES: Set[Tuple[int, int]] = {(4, 4), (5, 4), (4, 5), (5, 5)}

# Minimum estimated inventory held by opponent to trigger a front-running preemption
PREDATOR_DUMP_THRESHOLDS = {
    "MELON": 4,
    "MILK": 6,
    "STRAWBERRY": 8,
    "WOOL": 4,
    "WHEAT": 20,
    "FERTILIZER": 15,
}

# Minimum price ratio (current_price / base_price) to justify front-running
MIN_FRONTRUN_PRICE_RATIO = 0.70


class OpponentShedEstimator:
    """Forensic model that tracks opponent harvest events from public tiles and estimates shed contents."""

    def __init__(self):
        self.last_step = -1
        self.prev_tile_yields: Dict[Tuple[int, int], int] = {}
        self.prev_fertilizer_available: Dict[Tuple[int, int], bool] = {}
        self.estimated_shed: Dict[str, int] = {item: 0 for item in MARKET_PARAMS}
        self.carried_inventory: Dict[str, int] = {item: 0 for item in MARKET_PARAMS}

    def reset_if_new_game(self, step: int):
        if step == 0 or step < self.last_step:
            self.last_step = step
            self.prev_tile_yields = {}
            self.prev_fertilizer_available = {}
            self.estimated_shed = {item: 0 for item in MARKET_PARAMS}
            self.carried_inventory = {item: 0 for item in MARKET_PARAMS}
        self.last_step = step

    def update(self, obs: Dict[str, Any]):
        """Processes the current turn observation to update estimated opponent shed state."""
        step = obs.get("step", 0)
        self.reset_if_new_game(step)

        player = obs.get("player", 0)
        opp_player = 1 - player
        farms = obs.get("farms", [{}, {}])
        if len(farms) <= opp_player:
            return

        opp_farm = farms[opp_player]
        opp_tiles = opp_farm.get("tiles", [])
        opp_farmer = opp_farm.get("farmer", [4, 4])
        opp_hands = opp_farm.get("hands", [])

        # 1. Detect harvest events by comparing current tile yields to previous step
        current_yields: Dict[Tuple[int, int], int] = {}
        current_fert_avail: Dict[Tuple[int, int], bool] = {}

        for y, row in enumerate(opp_tiles):
            for x, tile in enumerate(row):
                pos = (x, y)
                if not isinstance(tile, dict):
                    continue

                kind = tile.get("kind")
                if kind == "PLANT":
                    crop = tile.get("crop")
                    y_units = int(tile.get("yield_units", 0) or 0)
                    current_yields[pos] = y_units

                    if pos in self.prev_tile_yields:
                        prev_y = self.prev_tile_yields[pos]
                        if prev_y > y_units:
                            # Harvest occurred: difference was picked up
                            harvested = prev_y - y_units
                            if crop in self.carried_inventory:
                                self.carried_inventory[crop] += harvested

                elif kind in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    y_units = int(tile.get("yield_units", 0) or 0)
                    fert_avail = bool(tile.get("fertilizer_available", False))
                    current_yields[pos] = y_units
                    current_fert_avail[pos] = fert_avail

                    # Animal product harvest
                    if animal and pos in self.prev_tile_yields:
                        prev_y = self.prev_tile_yields[pos]
                        if prev_y > y_units:
                            harvested = prev_y - y_units
                            prod = "MILK" if animal == "COW" else ("WOOL" if animal == "SHEEP" else "EGG")
                            if prod in self.carried_inventory:
                                self.carried_inventory[prod] += harvested

                    # Fertilizer collection
                    if pos in self.prev_fertilizer_available:
                        if self.prev_fertilizer_available[pos] and not fert_avail:
                            self.carried_inventory["FERTILIZER"] += 1

        self.prev_tile_yields = current_yields
        self.prev_fertilizer_available = current_fert_avail

        # 2. Check for deposit into shed:
        # Items are deposited into the shed when units are adjacent to the shed OR at end-of-day refresh (hour == 23)
        hour = obs.get("hour", 0)
        farmer_pos = (opp_farmer[0], opp_farmer[1]) if len(opp_farmer) >= 2 else (4, 4)
        is_adjacent = farmer_pos in SHED_ADJACENT_TILES or any(
            (h[0], h[1]) in SHED_ADJACENT_TILES for h in opp_hands if len(h) >= 2
        )

        if is_adjacent or hour == 23:
            # Transfer carried inventory into estimated shed
            for item, count in list(self.carried_inventory.items()):
                if count > 0:
                    self.estimated_shed[item] = self.estimated_shed.get(item, 0) + count
                    self.carried_inventory[item] = 0

        # Cap total estimated shed items at 100
        total_shed = sum(self.estimated_shed.values())
        if total_shed > SHED_CAPACITY:
            scale = SHED_CAPACITY / float(total_shed)
            for item in self.estimated_shed:
                self.estimated_shed[item] = int(self.estimated_shed[item] * scale)

    def get_estimated_volume(self, item: str) -> int:
        return self.estimated_shed.get(item, 0)

    def get_total_estimated_shed(self) -> int:
        return sum(self.estimated_shed.values())

    def record_observed_opponent_sell(self, item: str, quantity: int):
        """Reduces estimated shed when opponent executes a sell."""
        if item in self.estimated_shed:
            self.estimated_shed[item] = max(0, self.estimated_shed[item] - quantity)


class PredatorEngine:
    """Analyzes opponent shed estimates and issues front-running market orders ahead of predicted dumps."""

    def __init__(self, shed_estimator: Optional[OpponentShedEstimator] = None):
        self.estimator = shed_estimator or OpponentShedEstimator()

    def update(self, obs: Dict[str, Any]):
        self.estimator.update(obs)

    def evaluate_frontrun_opportunities(
        self,
        obs: Dict[str, Any],
        current_market_orders: List[List[Any]],
        debt_mgr: PureDebtManager,
        lookahead_scheduled_sells: Dict[str, Tuple[int, int]],  # item -> (found_step, found_qty)
    ) -> List[List[Any]]:
        """Evaluates whether to pull forward a scheduled premium sale to front-run the opponent.
        Returns list of new market orders to add.
        """
        step = obs.get("step", 0)
        my_shed = (obs.get("private") or {}).get("shed", {}) or {}
        market_prices = obs.get("market", {}).get("prices", {}) or {}
        market_inv = obs.get("market", {}).get("inventory", {}) or {}

        # Don't stack front-runs if an active debt is pending
        if debt_mgr.due:
            return []

        already_selling: Dict[str, int] = {}
        for order in current_market_orders:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                already_selling[order[1]] = already_selling.get(order[1], 0) + max(0, int(order[2] or 0))

        frontrun_orders: List[List[Any]] = []

        for item in PREMIUM_PRODUCTS:
            if len(current_market_orders) + len(frontrun_orders) >= MAX_MARKET_ORDERS:
                break

            opp_held = self.estimator.get_estimated_volume(item)
            dump_thresh = PREDATOR_DUMP_THRESHOLDS.get(item, 5)

            # Check if opponent is poised to dump this item
            is_dump_imminent = opp_held >= dump_thresh or self.estimator.get_total_estimated_shed() >= 60

            if not is_dump_imminent:
                continue

            # Verify current market price is healthy
            base_price = MARKET_PARAMS[item]["base"]
            cur_price = market_prices.get(item, calculate_single_unit_price(item, market_inv.get(item, 10000)))
            if cur_price < base_price * MIN_FRONTRUN_PRICE_RATIO:
                continue

            # Check if we have scheduled a future sell for this item in our tape
            if item not in lookahead_scheduled_sells:
                continue

            due_step, scheduled_qty = lookahead_scheduled_sells[item]
            if scheduled_qty <= 0:
                continue

            # Check our available shed inventory right now
            my_available = max(0, int(my_shed.get(item, 0) or 0) - already_selling.get(item, 0))
            if my_available <= 0:
                continue

            # Pull forward up to 50% of the scheduled quantity (or available)
            pull_qty = min(my_available, max(1, int(round(scheduled_qty * 0.5))))
            if pull_qty <= 0:
                continue

            frontrun_orders.append(["SELL", item, pull_qty])
            already_selling[item] = already_selling.get(item, 0) + pull_qty

            # Record repayment debt purely in memory without mutating base tape!
            debt_mgr.record_debt(due_step=due_step, item=item, quantity=pull_qty)

        return frontrun_orders
