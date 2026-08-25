"""Project Aegis: Self-Contained Master Submission for Kaggle Kaggriculture Competition

Standalone bundle containing Core AMM Engine, The Predator Forensics, The River Scaled Trickle,
The Ghost Protocol, Base Tape Oracle Selector, and Execution Guards.
"""

import base64
import copy
import json
import math
import zlib
from typing import Dict, List, Any, Optional, Tuple, Set


# ==================== CORE FOUNDATION & AMM ENGINE ====================
"""Project Aegis - Module 0: Core Architecture & Foundations

Contains:
1. Exact AMM Price Functions & Revenue Simulation for all 9 products.
2. Order Priority Dispatcher (strictly enforcing max 10 orders/turn).
3. Pure Mathematical Debt Tracker (Zero Tape Mutation).
4. Terminal Liquidation Engine (steps 716-720).
5. Universal Exception Safety Wrapper.
"""

import math
from typing import Dict, List, Any, Tuple, Optional

# --- Game Constants ---
MARKET_I0 = 10000
PRICE_FLOOR = 1.0
SHED_CAPACITY = 100
MAX_MARKET_ORDERS = 10
TERMINAL_LIQUIDATION_STEP = 716
TOTAL_STEPS = 720

# AMM Parameters from official Kaggriculture specification
MARKET_PARAMS = {
    "WHEAT":      {"base": 25,  "I0": MARKET_I0, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base": 35,  "I0": MARKET_I0, "T": 450, "below_func": "log",    "below_target": 0.20, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base": 60,  "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base": 50,  "I0": MARKET_I0, "T": 332, "below_func": "linear", "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

ALL_PRODUCTS = list(MARKET_PARAMS.keys())
PREMIUM_PRODUCTS = ("MELON", "MILK", "STRAWBERRY", "WOOL")
STAPLE_PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "EGG", "FERTILIZER")

# --- AMM Pricing Functions ---

def shape_function(func_name: str, x: float, T: float) -> float:
    """Evaluates the AMM shape function f(x) for distance x = |inv - I0|."""
    x = max(0.0, float(x))
    if func_name == "linear":
        return x
    elif func_name == "sq":
        return x * x
    elif func_name == "sqrt":
        return math.sqrt(x)
    elif func_name == "log":
        return math.log1p(x)
    elif func_name == "log10":
        return math.log10(1.0 + x)
    elif func_name == "hinge":
        u = x / max(1.0, float(T))
        return u + 8.0 * (max(0.0, u - 1.0) ** 2)
    return x

def calculate_single_unit_price(item: str, inventory: int) -> float:
    """Calculates the exact per-unit sale price at a given market inventory level."""
    if item not in MARKET_PARAMS:
        return PRICE_FLOOR
    p = MARKET_PARAMS[item]
    base = float(p["base"])
    I0 = float(p["I0"])
    T = float(p["T"])

    if inventory >= I0:
        # Glut side (supply surplus -> price decreases)
        f_above = p["above_func"]
        target = float(p["above_target"])
        denom = shape_function(f_above, T, T)
        amp = target * base / max(1e-6, denom)
        dist = inventory - I0
        price = base - amp * shape_function(f_above, dist, T)
    else:
        # Scarcity side (supply deficit -> price increases)
        f_below = p["below_func"]
        target = float(p["below_target"])
        denom = shape_function(f_below, T, T)
        amp = target * base / max(1e-6, denom)
        dist = I0 - inventory
        price = base + amp * shape_function(f_below, dist, T)

    return max(PRICE_FLOOR, round(price))

def simulate_sale_revenue(item: str, start_inventory: int, quantity: int) -> Tuple[float, int]:
    """Simulates selling `quantity` units of `item` starting at `start_inventory`.
    Returns (total_revenue, final_inventory)."""
    if quantity <= 0:
        return 0.0, start_inventory
    revenue = 0.0
    inv = start_inventory
    for _ in range(quantity):
        unit_price = calculate_single_unit_price(item, inv)
        revenue += unit_price
        # According to game rules, if price hits floor ($1), inventory is NOT incremented
        if unit_price > PRICE_FLOOR:
            inv += 1
    return revenue, inv


# --- Pure Debt Manager (Zero In-Memory Tape Mutation) ---

class PureDebtManager:
    """Tracks sale shifting debt purely in memory per seat without ever mutating the base tape array."""
    def __init__(self):
        self.last_step = -1
        self.due_step = -1
        self.due: Dict[str, int] = {}

    def reset_if_new_game(self, step: int):
        if step == 0 or step < self.last_step:
            self.last_step = step
            self.due_step = -1
            self.due = {}
        self.last_step = step

    def record_debt(self, due_step: int, item: str, quantity: int):
        """Records a pulled-forward sale that must be subtracted on `due_step`."""
        if quantity <= 0:
            return
        if self.due_step == -1:
            self.due_step = due_step
        elif self.due_step != due_step:
            # If multiple items shift to different due_steps, keep the earliest
            self.due_step = min(self.due_step, due_step)
        self.due[item] = self.due.get(item, 0) + quantity

    def apply_repayment(self, action: Dict[str, Any], step: int) -> Dict[str, Any]:
        """Intercepts the tape's scheduled action and reduces SELL orders to repay debt."""
        self.reset_if_new_game(step)
        if self.due_step != step or not self.due:
            if self.due_step < step:
                self.due_step = -1
                self.due = {}
            return action

        market_orders = action.get("market", [])
        if not market_orders:
            return action

        repaid_market = []
        for raw_order in market_orders:
            order = list(raw_order)
            if len(order) >= 3 and order[0] == "SELL":
                item = order[1]
                qty = max(0, int(order[2] or 0))
                debt_qty = self.due.get(item, 0)
                if debt_qty > 0:
                    reduction = min(qty, debt_qty)
                    qty -= reduction
                    self.due[item] -= reduction
                    if self.due[item] <= 0:
                        del self.due[item]
                    if qty <= 0:
                        continue
                    order[2] = qty
            repaid_market.append(order)

        # Clear due_step once processed
        if not self.due:
            self.due_step = -1
            self.due = {}

        action["market"] = repaid_market
        return action


# --- Priority Order Dispatcher ---

def prioritize_and_dispatch_market(market_orders: List[List[Any]]) -> List[List[Any]]:
    """Strictly enforces the 10 market orders per turn limit with deterministic priority:
    1. Capital Expenditure (BUY_LAND, HIRE, BUY_SEED)
    2. High-priority Front-run Sells
    3. Standard / Trickle Sells
    4. Other operations (BUY_PRODUCT, BUY_ANIMAL)
    """
    if not market_orders:
        return []

    def get_order_priority(order: List[Any]) -> int:
        if not isinstance(order, list) or len(order) == 0:
            return 99
        op = order[0]
        if op == "BUY_LAND":
            return 0  # Highest priority - preventing spatial desync
        if op == "HIRE":
            return 1  # Daily farmhand spawning
        if op == "BUY_SEED":
            return 2  # Planting pipeline
        if op == "BUY_ANIMAL":
            return 3
        if op == "BUY_PRODUCT":
            return 4
        if op == "SELL":
            # Premium items prioritized over staples
            if len(order) >= 2 and order[1] in PREMIUM_PRODUCTS:
                return 5
            return 6
        return 10

    # Sort with stable key preserving relative insertion order
    sorted_orders = sorted(market_orders, key=get_order_priority)
    return sorted_orders[:MAX_MARKET_ORDERS]


# --- Terminal Liquidation Engine ---

def execute_terminal_liquidation(obs: Dict[str, Any], action: Dict[str, Any], step: int) -> Dict[str, Any]:
    """In the final steps (716-720), liquidate all remaining non-seed shed inventory."""
    if step < TERMINAL_LIQUIDATION_STEP:
        return action

    shed = (obs.get("private") or {}).get("shed", {}) or {}
    market = action.setdefault("market", [])

    # Tally already planned sales
    planned_sells: Dict[str, int] = {}
    for order in market:
        if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
            planned_sells[order[1]] = planned_sells.get(order[1], 0) + max(0, int(order[2] or 0))

    # Queue liquidation for all available shed inventory
    for item in ALL_PRODUCTS:
        available = max(0, int(shed.get(item, 0) or 0) - planned_sells.get(item, 0))
        if available > 0 and len(market) < MAX_MARKET_ORDERS:
            market.append(["SELL", item, available])

    action["market"] = prioritize_and_dispatch_market(market)
    return action


# --- Universal Exception Safety Fallback ---

def get_active_animal_count(obs: Dict[str, Any]) -> int:
    """Counts total live animals across coops and pastures on player's farm."""
    player = obs.get("player", 0) if isinstance(obs, dict) else 0
    farms = obs.get("farms", [{}, {}]) if isinstance(obs, dict) else []
    if len(farms) <= player or not isinstance(farms[player], dict):
        return 0
    my_tiles = farms[player].get("tiles", [])
    count = 0
    for row in my_tiles:
        for tile in row or []:
            if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE") and tile.get("animal"):
                count += 1
    return count


def safe_agent_fallback(obs: Dict[str, Any]) -> Dict[str, Any]:
    """Generates a guaranteed legal action (PASS for farmer and all active hands) on fatal error."""
    player = obs.get("player", 0) if isinstance(obs, dict) else 0
    farms = obs.get("farms", []) if isinstance(obs, dict) else []
    me = farms[player] if len(farms) > player and isinstance(farms[player], dict) else {}
    hands_count = len(me.get("hands", []) or [])
    return {
        "farmer": ["PASS"],
        "hands": [["PASS"] for _ in range(hands_count)],
        "market": []
    }





# ==================== PREDATOR FORENSICS ENGINE ====================
"""Project Aegis - Module 1: The Predator (Dynamic Opponent Forensics & Public Tile Estimator)

Tracks opponent's visible tiles, harvest state transitions, and shed-deposit timings
to calculate real-time shed accumulation and execute targeted front-running without hardcoded tables.
"""

from typing import Dict, List, Any, Optional, Set, Tuple


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


# ==================== RIVER SCALED TRICKLE ENGINE ====================
"""Project Aegis - Module 2: The River (Continuous Trickle-Selling & Queue Engine)

Contains:
1. Dynamic Scaled Trickle-Selling (Production Phase).
2. Shed Pressure Valve with Wave-2 Melon & Harvest Protection (keeps shed < 40 on Days 20-27).
3. Defensive Liquidity Guard (3-step Lookahead Capex).
4. AMM Quadratic Price Floor Protection for Melons and Premium goods.
"""

from typing import Dict, List, Any, Optional


PRODUCTION_PHASE_START_STEP = 288  # Day 12
SHED_FLUSH_THRESHOLD = 75
DEFAULT_SHED_FLUSH_THRESHOLD = SHED_FLUSH_THRESHOLD
PRE_HARVEST_SHED_FLUSH_THRESHOLD = 40
PRICE_FLOOR_PAUSE_RATIO = 0.60


class LiquidityGuard:
    """Defensive 3-step Lookahead Capex and Urgent Liquidation Engine."""

    @staticmethod
    def calculate_upcoming_capex(future_tape_slice: List[Dict[str, Any]], current_quadrants_count: int) -> float:
        total_capex = 0.0
        quad_idx = current_quadrants_count

        for action_dict in future_tape_slice:
            market_orders = action_dict.get("market", []) or []
            for order in market_orders:
                if not isinstance(order, list) or len(order) == 0:
                    continue
                op = order[0]
                if op == "BUY_LAND":
                    cost = 1000.0 if quad_idx == 1 else (2000.0 if quad_idx == 2 else 4000.0)
                    total_capex += cost
                    quad_idx += 1
                elif op == "BUY_ANIMAL" and len(order) >= 2:
                    animal = order[1]
                    n = int(order[2]) if len(order) >= 3 else 1
                    unit_c = 800.0 if animal == "COW" else (600.0 if animal == "SHEEP" else 300.0)
                    total_capex += unit_c * n
                elif op == "BUY_SEED" and len(order) >= 2:
                    seed = order[1]
                    n = int(order[2]) if len(order) >= 3 else 1
                    unit_c = 60.0 if seed == "STRAWBERRY" else (20.0 if seed == "MELON" else (10.0 if seed == "WHEAT" else 5.0))
                    total_capex += unit_c * n
                elif op == "BUY_PRODUCT" and len(order) >= 2:
                    prod = order[1]
                    n = int(order[2]) if len(order) >= 3 else 1
                    unit_c = 25.0 if prod == "WHEAT" else 40.0
                    total_capex += unit_c * n

        return total_capex

    @staticmethod
    def ensure_liquidity(
        obs: Dict[str, Any],
        current_market_orders: List[List[Any]],
        upcoming_capex: float = 0.0,
        needed_cash: Optional[float] = None,
    ) -> List[List[Any]]:
        required_cash = needed_cash if needed_cash is not None else upcoming_capex
        player = obs.get("player", 0)
        farms = obs.get("farms", [{}, {}])
        my_farm = farms[player] if len(farms) > player else {}
        money = float(my_farm.get("money", 0.0) or 0.0)

        if money >= required_cash:
            return []

        shortfall = required_cash - money
        shed = (obs.get("private") or {}).get("shed", {}) or {}
        market_prices = obs.get("market", {}).get("prices", {}) or {}

        already_selling: Dict[str, int] = {}
        for order in current_market_orders:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                already_selling[order[1]] = already_selling.get(order[1], 0) + max(0, int(order[2] or 0))

        live_animals = get_active_animal_count(obs)
        wheat_feed_reserve = live_animals * 2

        urgent_orders: List[List[Any]] = []
        recovered_cash = 0.0

        sellable_products = [p for p in ALL_PRODUCTS if p != "WHEAT"] + ["WHEAT"]
        sorted_products = sorted(
            sellable_products,
            key=lambda item: market_prices.get(item, MARKET_PARAMS[item]["base"]),
            reverse=True
        )

        for item in sorted_products:
            if recovered_cash >= shortfall or len(current_market_orders) + len(urgent_orders) >= MAX_MARKET_ORDERS:
                break

            total_held = int(shed.get(item, 0) or 0)
            avail = max(0, total_held - already_selling.get(item, 0))

            if item == "WHEAT":
                avail = max(0, avail - wheat_feed_reserve)

            if avail <= 0:
                continue

            unit_p = max(PRICE_FLOOR, market_prices.get(item, MARKET_PARAMS[item]["base"]))
            needed_units = int((shortfall - recovered_cash + unit_p - 1) // unit_p)
            sell_qty = min(avail, max(1, needed_units))

            urgent_orders.append(["SELL", item, sell_qty])
            already_selling[item] = already_selling.get(item, 0) + sell_qty
            recovered_cash += sell_qty * unit_p

        return urgent_orders


class RiverEngine:
    """Continuous trickle-selling and queue management engine."""

    def __init__(self):
        self.pending_sell_queue: Dict[str, int] = {item: 0 for item in ALL_PRODUCTS}

    def process_tape_orders(self, tape_market_orders: List[List[Any]], step: int) -> List[List[Any]]:
        has_buys = any(
            isinstance(o, list) and len(o) > 0 and (o[0].startswith("BUY") or o[0] == "HIRE")
            for o in tape_market_orders
        )

        if step < PRODUCTION_PHASE_START_STEP or has_buys:
            return list(tape_market_orders)

        retained_orders = []
        for order in tape_market_orders:
            if not isinstance(order, list) or len(order) == 0:
                continue
            if order[0] == "SELL" and len(order) >= 3:
                item = order[1]
                qty = max(0, int(order[2] or 0))
                if item in self.pending_sell_queue:
                    self.pending_sell_queue[item] += qty
            else:
                retained_orders.append(order)
        return retained_orders

    def generate_trickle_orders(
        self,
        obs: Dict[str, Any],
        current_market_orders: List[List[Any]],
        future_tape_slice: List[Dict[str, Any]],
    ) -> List[List[Any]]:
        step = int(obs.get("step", 0) or 0)
        day = int(obs.get("day", 0) or 0)
        player = obs.get("player", 0)
        farms = obs.get("farms", [{}, {}])
        my_farm = farms[player] if len(farms) > player else {}
        my_quads_count = len(my_farm.get("unlocked_quadrants", ["NW"]))

        shed = (obs.get("private") or {}).get("shed", {}) or {}
        market_prices = obs.get("market", {}).get("prices", {}) or {}
        market_inv = obs.get("market", {}).get("inventory", {}) or {}

        total_shed_count = sum(max(0, int(v or 0)) for v in shed.values())
        live_animals = get_active_animal_count(obs)
        wheat_feed_reserve = live_animals * 2

        # 1. Defensive Liquidity Check for next 3 steps
        immediate_slice = future_tape_slice[:3]
        upcoming_capex = LiquidityGuard.calculate_upcoming_capex(immediate_slice, my_quads_count)
        liquidity_orders = LiquidityGuard.ensure_liquidity(obs, current_market_orders, upcoming_capex)

        dispatched_orders = list(current_market_orders) + liquidity_orders

        if step < PRODUCTION_PHASE_START_STEP:
            return dispatched_orders[:MAX_MARKET_ORDERS]

        already_selling: Dict[str, int] = {}
        for order in dispatched_orders:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                already_selling[order[1]] = already_selling.get(order[1], 0) + max(0, int(order[2] or 0))

        # 2. Pre-Harvest Shed Pressure Valve (Protects Wave-2 Melon deposits from 100-cap discard)
        flush_threshold = PRE_HARVEST_SHED_FLUSH_THRESHOLD if (20 <= day <= 27) else DEFAULT_SHED_FLUSH_THRESHOLD
        is_pressure_valve_active = total_shed_count >= flush_threshold

        if is_pressure_valve_active:
            # Flush Fertilizer & Wheat first
            avail_fert = max(0, int(shed.get("FERTILIZER", 0) or 0) - already_selling.get("FERTILIZER", 0))
            if avail_fert > 0 and len(dispatched_orders) < MAX_MARKET_ORDERS:
                flush_qty = min(avail_fert, 15)
                dispatched_orders.append(["SELL", "FERTILIZER", flush_qty])
                already_selling["FERTILIZER"] = already_selling.get("FERTILIZER", 0) + flush_qty

            avail_wheat = max(0, int(shed.get("WHEAT", 0) or 0) - already_selling.get("WHEAT", 0) - wheat_feed_reserve)
            if avail_wheat > 0 and len(dispatched_orders) < MAX_MARKET_ORDERS:
                flush_qty = min(avail_wheat, 15)
                dispatched_orders.append(["SELL", "WHEAT", flush_qty])
                already_selling["WHEAT"] = already_selling.get("WHEAT", 0) + flush_qty

            # Flush non-feed items (Wool, Milk, Strawberry) if shed is still crowded
            for prod in ("WOOL", "MILK", "STRAWBERRY"):
                if len(dispatched_orders) >= MAX_MARKET_ORDERS:
                    break
                avail_prod = max(0, int(shed.get(prod, 0) or 0) - already_selling.get(prod, 0))
                if avail_prod > 0:
                    flush_qty = min(avail_prod, 10)
                    dispatched_orders.append(["SELL", prod, flush_qty])
                    already_selling[prod] = already_selling.get(prod, 0) + flush_qty

        # 3. Dynamic Scaled Trickle-Selling & Melon AMM Protection
        dynamic_batch_size = max(1, min(8, int(total_shed_count // 8)))

        # Prioritize selling Melons if held in shed
        melon_held = int(shed.get("MELON", 0) or 0)
        melon_avail = max(0, melon_held - already_selling.get("MELON", 0))
        if melon_avail > 0 and len(dispatched_orders) < MAX_MARKET_ORDERS:
            melon_price = market_prices.get("MELON", 250)
            melon_inv = market_inv.get("MELON", 10000)
            # Quadratic AMM guard: sell if price >= 120 or if pressure valve is active
            if melon_price >= 120 or melon_inv < 10020 or is_pressure_valve_active:
                melon_sell_qty = min(melon_avail, 10)
                dispatched_orders.append(["SELL", "MELON", melon_sell_qty])
                already_selling["MELON"] = already_selling.get("MELON", 0) + melon_sell_qty

        for item in ALL_PRODUCTS:
            if len(dispatched_orders) >= MAX_MARKET_ORDERS:
                break

            queued_qty = self.pending_sell_queue.get(item, 0)
            avail_in_shed = max(0, int(shed.get(item, 0) or 0) - already_selling.get(item, 0))
            if item == "WHEAT":
                avail_in_shed = max(0, avail_in_shed - wheat_feed_reserve)

            if queued_qty <= 0 or avail_in_shed <= 0:
                continue

            base_price = MARKET_PARAMS[item]["base"]
            cur_price = market_prices.get(item, calculate_single_unit_price(item, market_inv.get(item, 10000)))

            if not is_pressure_valve_active and cur_price < base_price * PRICE_FLOOR_PAUSE_RATIO:
                continue

            sell_qty = min(queued_qty, avail_in_shed, dynamic_batch_size)
            if sell_qty <= 0:
                continue

            dispatched_orders.append(["SELL", item, sell_qty])
            already_selling[item] = already_selling.get(item, 0) + sell_qty
            self.pending_sell_queue[item] -= sell_qty

        return dispatched_orders[:MAX_MARKET_ORDERS]


# ==================== GHOST PROTOCOL & SCAVENGER ====================
"""Project Aegis - Module 3: The Ghost Protocol & Non-Colliding Scavenger Overlay

Architecture:
1. The Ghost Protocol: Non-spatial signature noise (seed purchase on Step 0) to confuse opponent fingerprinting.
2. Non-Colliding Scavenger Overlay:
   - Only routes naturally occurring unscripted hands toward weed clearing (DIG) and fertilizer collection (COLLECT_FERTILIZER).
   - STRICT INVARIANT: Never issues auxiliary HIRE orders (preserves 100% tape capex).
   - STRICT INVARIANT: Never initiates PLANT orders on empty tiles (preserves 100% future pasture/crop reservations).
"""

from typing import Dict, List, Any, Optional, Tuple, Set

GHOST_SPOOF_STEP = 0
MAX_OPPORTUNISTIC_PLANT_DAY = 18
SHED_ACCESS_TILES: Set[Tuple[int, int]] = {(4, 4), (5, 4), (4, 5), (5, 5)}
_MOVE_DELTA = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
_CLAIMS_TILE = {"BUILD_PASTURE", "BUILD_COOP", "PLANT"}


def _project_reserved_tiles(obs: Dict[str, Any], active_tape: List[Dict[str, Any]], step: int, lookahead: int = 20) -> Set[Tuple[int, int]]:
    """Projects forward, from REAL current positions, which tiles the tape's own
    scripted farmer/hands will BUILD_PASTURE/BUILD_COOP/PLANT on within the
    lookahead window. Tape actions carry no coordinates -- they act wherever
    the actor currently stands -- so the only way to know which tile a future
    scripted action targets is to simulate movement forward from ground truth.
    Anchoring to the REAL observed position (not a from-scratch full-game
    simulation) means any real-world drift (weed detours, etc.) self-corrects
    every time this is called, since it's called fresh every step.

    Root cause this prevents: an auxiliary hand planting on a tile the tape
    reserves for a future BUILD_PASTURE silently voids that build (engine:
    `if tile is not None: return`) with no error -- confirmed to cost 6 cows
    and $60k+ milk revenue in a real ablation test.

    Known limitation: if the tape's own hand count grows mid-window (a new
    hire lands within the lookahead), that new hand's targets aren't tracked
    since its spawn tile isn't known in advance -- a narrow residual risk,
    much smaller in scope than reserving nothing at all.
    """
    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return set()
    farm = farms[player]

    positions: List[Tuple[int, int]] = [tuple(farm.get("farmer", [4, 4]))]
    live_hands = farm.get("hands", []) or []
    tape_hand_count = len(active_tape[step].get("hands", []) or []) if step < len(active_tape) else 0
    for i in range(min(tape_hand_count, len(live_hands))):
        positions.append(tuple(live_hands[i]))

    reserved: Set[Tuple[int, int]] = set()
    end = min(step + lookahead, len(active_tape))
    for future_step in range(step, end):
        raw = active_tape[future_step]
        acts = [raw.get("farmer", ["PASS"])] + list(raw.get("hands", []) or [])[:len(positions) - 1]
        for idx, act in enumerate(acts):
            if not act or idx >= len(positions):
                continue
            op = act[0]
            if op in _MOVE_DELTA:
                dx, dy = _MOVE_DELTA[op]
                x, y = positions[idx]
                positions[idx] = (x + dx, y + dy)
            elif op in _CLAIMS_TILE:
                reserved.add(positions[idx])
    return reserved


def apply_ghost_signature_spoof(
    obs: Dict[str, Any],
    action: Dict[str, Any]
) -> Dict[str, Any]:
    """Injects safe, non-spatial market noise on Step 0 (e.g. buying 1 cheap Carrot seed)
    to disrupt opponent fingerprinting algorithms while preserving 100% of spatial pathing.
    """
    step = obs.get("step", 0)
    if step != GHOST_SPOOF_STEP:
        return action

    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    money = float(farms[player].get("money", 0.0)) if len(farms) > player else 0.0

    if money < 2500.0:
        return action

    market = action.setdefault("market", [])
    has_carrot_buy = any(
        isinstance(o, list) and len(o) >= 2 and o[0] == "BUY_SEED" and o[1] == "CARROT"
        for o in market
    )

    if not has_carrot_buy and len(market) < 10:
        market.append(["BUY_SEED", "CARROT", 1])

    return action


_FIB = [1, 1]
while len(_FIB) < 20:
    _FIB.append(_FIB[-1] + _FIB[-2])

AUX_HIRE_MIN_DAY = 10
AUX_HIRE_MAX_DAY = 26
AUX_HIRE_SCARCITY_MIN_DAY = 4
AUX_HIRE_SCARCITY_MAX_DAY = 9
AUX_HIRE_MIN_CASH_BUFFER = 500.0

# Measured via real ablation (8 seeds, env.run() vs "starter"): even after fixing
# the tile-reservation collision (0/34 BUILD_PASTURE failures, confirmed), hiring
# an auxiliary hand at all -- regardless of what it's tasked with -- costs
# -$47,652 avg vs not hiring one. Isolated and ruled out: hire cost (~$100-150
# total, trivial), crop-tending vs weed/fertilizer-only (both regress similarly),
# fertilizer-collection specifically (removing it changes nothing). Traced to a
# real step where an IDENTICAL market order nets $2,933 with the aux hand absent
# and $0 with it present -- the extra hand's mere presence disrupts shed
# inventory the tape's own scripted hands expect to have accumulated, most
# likely the same hand-index fragility found in a different tape entirely
# (project_doppelganger's YARN route: hand roles are positional, and any
# divergence from the exact count/order the tape assumes compounds over time).
# This is the 5th documented failure of "graft extra production onto a fixed
# tape via an auxiliary hand" in this project's history. Kept disabled until a
# fix addresses hand-identity stability, not just tile occupancy.
AUX_HIRE_ENABLED = False


def schedule_auxiliary_farmhand_hire(
    action: Dict[str, Any],
    obs: Dict[str, Any],
    scarcity_active: bool = False,
) -> Dict[str, Any]:
    """Adds ONE extra HIRE order on top of whatever the tape already schedules
    this morning, so the scavenger overlay has an unscripted hand to route into
    Wave-2 Melon Replanter / scarcity-crop work. Must be ADDITIVE: the tape
    re-hires its full crew every morning (hands wipe nightly), so "already has
    HIRE orders queued" is the normal case, not a reason to skip -- a prior
    version of this gated on `if no HIRE already queued`, which meant it never
    fired on any day the tape hires at all (confirmed empirically: 0/5 games).

    DISABLED by default (see AUX_HIRE_ENABLED docstring above) pending a fix
    for the hand-identity fragility this causes even though the tile-reservation
    collision it was originally built to fix is confirmed resolved.
    """
    if not AUX_HIRE_ENABLED:
        return action
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    if hour != 0:
        return action

    in_window = (AUX_HIRE_MIN_DAY <= day <= AUX_HIRE_MAX_DAY) or (
        scarcity_active and AUX_HIRE_SCARCITY_MIN_DAY <= day <= AUX_HIRE_SCARCITY_MAX_DAY
    )
    if not in_window:
        return action

    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return action
    farm = farms[player]
    money = float(farm.get("money", 0.0) or 0.0)

    market = action.setdefault("market", [])
    hires_already_queued = sum(1 for o in market if isinstance(o, list) and len(o) > 0 and o[0] == "HIRE")
    this_hire_cost = float(_FIB[min(hires_already_queued, len(_FIB) - 1)])

    if money < AUX_HIRE_MIN_CASH_BUFFER + this_hire_cost or len(market) >= 10:
        return action

    market.append(["HIRE"])
    return action


WAVE2_PLANT_START_DAY = 10
WAVE2_PLANT_END_DAY = 12
WAVE2_HARVEST_END_DAY = 27


class OpportunisticCropManager:
    """Detects extreme shop demand surges for Tomato/Carrot (scarcity window,
    days 4-9) and drives Wave-2 Melon replanting (days 10-27) on tiles the
    tape's own future schedule does NOT claim -- verified via
    `_project_reserved_tiles`, never on raw "tile is empty right now"."""

    @staticmethod
    def detect_scarcity_opportunity(obs: Dict[str, Any]) -> Optional[str]:
        day = int(obs.get("day", 0) or 0)
        if not (AUX_HIRE_SCARCITY_MIN_DAY <= day <= AUX_HIRE_SCARCITY_MAX_DAY):
            return None
        player = obs.get("player", 0)
        farms = obs.get("farms", [{}, {}])
        if len(farms) <= player:
            return None
        money = float(farms[player].get("money", 0.0) or 0.0)
        if money < 500.0:
            return None

        shops = (obs.get("town") or {}).get("unlocked_shops", []) or []
        market_prices = (obs.get("market") or {}).get("prices", {}) or {}

        tomato_shops = shops.count("PIZZA_SHOP") + shops.count("FARMERS_MARKET")
        if tomato_shops >= 2 or market_prices.get("TOMATO", 60) >= 110:
            return "TOMATO"
        carrot_shops = (shops.count("PET_CAFE") * 2) + shops.count("FARMERS_MARKET")
        if carrot_shops >= 2 or market_prices.get("CARROT", 30) >= 80:
            return "CARROT"
        return None

    @staticmethod
    def find_safe_tiles(
        tiles: List[List[Any]],
        unlocked_quads: List[str],
        reserved: Set[Tuple[int, int]],
        crop: Optional[str],
        max_tiles: int = 12,
    ) -> List[Tuple[int, int]]:
        """Existing plants of `crop` first (to keep tending them), then empty
        tiles not in `reserved` and not a shed-access tile."""
        existing_plants = []
        empty_tiles = []
        for y, row in enumerate(tiles):
            for x, tile in enumerate(row or []):
                if (x, y) in SHED_ACCESS_TILES or (x, y) in reserved:
                    continue
                quad = "NW" if x < 5 and y < 5 else ("NE" if x >= 5 and y < 5 else ("SW" if x < 5 and y >= 5 else "SE"))
                if quad not in unlocked_quads:
                    continue
                if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == crop:
                    existing_plants.append((x, y))
                elif tile is None:
                    empty_tiles.append((x, y))
        return (existing_plants + empty_tiles)[:max_tiles]


def scavenger_farmhand_overlay(
    action: Dict[str, Any],
    obs: Dict[str, Any],
    active_tape: Optional[List[Dict[str, Any]]] = None,
    step: int = 0,
) -> Dict[str, Any]:
    """Routes unscripted farmhands, in priority order:
    1. Tomato/Carrot scarcity micro-plots (days 4-9) or Wave-2 Melon replant
       (days 10-27) -- ONLY on tiles `_project_reserved_tiles` confirms the
       tape's own future schedule does not claim.
    2. Nearest weed (DIG).
    3. Nearest ready fertilizer (COLLECT_FERTILIZER).

    If `active_tape` is not supplied, crop-planting is skipped entirely and
    this behaves exactly like the previous DIG/COLLECT_FERTILIZER-only,
    zero-collision-risk version.
    """
    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return action

    farm = farms[player]
    live_hands = farm.get("hands", []) or []
    tape_hands = list(action.get("hands", []) or [])
    tiles = farm.get("tiles", []) or []
    unlocked_quads = farm.get("unlocked_quadrants", ["NW"])
    private = obs.get("private") or {}
    seeds = private.get("seeds", {}) or {}
    day = int(obs.get("day", 0) or 0)

    if len(tape_hands) >= len(live_hands):
        return action

    crop: Optional[str] = None
    safe_tiles: List[Tuple[int, int]] = []
    if active_tape is not None:
        if AUX_HIRE_SCARCITY_MIN_DAY <= day <= AUX_HIRE_SCARCITY_MAX_DAY:
            crop = OpportunisticCropManager.detect_scarcity_opportunity(obs)
        elif WAVE2_PLANT_START_DAY <= day <= WAVE2_HARVEST_END_DAY:
            crop = "MELON"
        if crop:
            reserved = _project_reserved_tiles(obs, active_tape, step)
            safe_tiles = OpportunisticCropManager.find_safe_tiles(tiles, unlocked_quads, reserved, crop)

    weeds: List[Tuple[int, int]] = []
    fertilizers: List[Tuple[int, int]] = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row or []):
            if isinstance(tile, dict):
                kind = tile.get("kind")
                if kind == "WEED":
                    weeds.append((x, y))
                elif kind in ("COOP", "PASTURE") and tile.get("fertilizer_available"):
                    fertilizers.append((x, y))

    while len(tape_hands) < len(live_hands):
        hand_idx = len(tape_hands)
        hx, hy = live_hands[hand_idx]

        best_target = None
        best_dist = 9999
        target_action_type = "PASS"

        # 1. Crop task on a verified-safe tile
        if crop and safe_tiles:
            for mx, my in safe_tiles:
                mtile = tiles[my][mx] if my < len(tiles) and mx < len(tiles[my]) else None
                if isinstance(mtile, dict) and mtile.get("kind") == "PLANT":
                    yield_u = int(mtile.get("yield_units", 0) or 0)
                    if yield_u > 0:
                        d = abs(hx - mx) + abs(hy - my)
                        if d < best_dist:
                            best_dist, best_target, target_action_type = d, (mx, my), "HARVEST"
                    elif not mtile.get("watered_today", False):
                        d = abs(hx - mx) + abs(hy - my)
                        if d < best_dist:
                            best_dist, best_target, target_action_type = d, (mx, my), "WATER"
                elif mtile is None:
                    d = abs(hx - mx) + abs(hy - my)
                    if d < best_dist:
                        best_dist, best_target, target_action_type = d, (mx, my), "PLANT"

        # 2. Nearest weed
        if not best_target:
            for wx, wy in weeds:
                d = abs(hx - wx) + abs(hy - wy)
                if d < best_dist:
                    best_dist, best_target, target_action_type = d, (wx, wy), "DIG"

        # 3. Nearest ready fertilizer
        if not best_target:
            for fx, fy in fertilizers:
                d = abs(hx - fx) + abs(hy - fy)
                if d < best_dist:
                    best_dist, best_target, target_action_type = d, (fx, fy), "COLLECT_FERTILIZER"

        if best_target:
            tx, ty = best_target
            if best_dist == 0:
                if target_action_type == "PLANT":
                    if seeds.get(crop, 0) > 0:
                        tape_hands.append(["PLANT", crop])
                    else:
                        market = action.setdefault("market", [])
                        has_pending = any(
                            isinstance(o, list) and len(o) >= 2 and o[0] == "BUY_SEED" and o[1] == crop
                            for o in market
                        )
                        if not has_pending and len(market) < 10:
                            market.append(["BUY_SEED", crop, 2])
                        tape_hands.append(["PASS"])
                else:
                    tape_hands.append([target_action_type])
                    if target_action_type == "DIG" and (tx, ty) in weeds:
                        weeds.remove((tx, ty))
                    elif target_action_type == "COLLECT_FERTILIZER" and (tx, ty) in fertilizers:
                        fertilizers.remove((tx, ty))
            else:
                if hx < tx:
                    tape_hands.append(["EAST"])
                elif hx > tx:
                    tape_hands.append(["WEST"])
                elif hy < ty:
                    tape_hands.append(["SOUTH"])
                elif hy > ty:
                    tape_hands.append(["NORTH"])
        else:
            tape_hands.append(["PASS"])

    action["hands"] = tape_hands
    return action


# ==================== EXECUTION & WEED/FEED GUARDS ====================
"""Project Aegis - Execution Guards & Repair Subsystems

Contains:
1. Weed Repair Guard: Dynamically clears unexpected random weeds (0.5% spawn) blocking farmer pathing.
2. Feed Rescue Guard: Ensures live animals never starve if wheat feed buffer runs out at hour 18+.
3. Room Evac & Capacity Guard: Prevents shed overflow at end-of-day (hour 23).
"""

from typing import Dict, List, Any, Optional, Tuple, Set

# Central shed access coordinates
SHED_ACCESS = {(4, 4), (5, 4), (4, 5), (5, 5)}


def weed_repair_overlay(
    action: Dict[str, Any],
    obs: Dict[str, Any],
    step: int
) -> Dict[str, Any]:
    """If a unit is about to execute a tile action (PLANT, WATER, HARVEST, BUILD) on a square
    where an unexpected weed spawned, swap the action to DIG for 1 turn to clear the tile.
    """
    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return action

    farm = farms[player]
    tiles = farm.get("tiles", []) or []
    farmer_pos = farm.get("farmer", [4, 4])
    hands_pos = farm.get("hands", []) or []

    all_positions = [farmer_pos] + hands_pos
    farmer_act = list(action.get("farmer", ["PASS"]))
    hands_act = [list(h) for h in action.get("hands", [])]
    all_acts = [farmer_act] + hands_act

    for i, pos in enumerate(all_positions):
        if i >= len(all_acts):
            break
        if not pos or len(pos) < 2:
            continue
        x, y = pos[0], pos[1]
        if y < len(tiles) and x < len(tiles[y]):
            tile = tiles[y][x]
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                curr_op = all_acts[i][0] if len(all_acts[i]) > 0 else "PASS"
                # If trying to plant, build, water, or pass on a weed, clear it first
                if curr_op in ("PLANT", "BUILD_COOP", "BUILD_PASTURE", "WATER", "HARVEST"):
                    all_acts[i] = ["DIG"]

    action["farmer"] = all_acts[0]
    action["hands"] = all_acts[1:]
    return action


def feed_rescue_guard(
    action: Dict[str, Any],
    obs: Dict[str, Any],
    step: int
) -> Dict[str, Any]:
    """If live animals remain unfed late in the day (hour >= 18) and shed has 0 wheat,
    automatically dispatches a BUY_PRODUCT WHEAT order to prevent animal starvation and escape.
    """
    hour = int(obs.get("hour", 0) or 0)
    if hour < 18:
        return action

    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return action

    farm = farms[player]
    tiles = farm.get("tiles", []) or []
    unfed_animals = 0

    for row in tiles:
        for tile in row or []:
            if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE") and tile.get("animal"):
                if not tile.get("fed_today", False):
                    unfed_animals += 1

    if unfed_animals <= 0:
        return action

    private = obs.get("private") or {}
    shed = private.get("shed", {}) or {}
    wheat_in_shed = int(shed.get("WHEAT", 0) or 0)

    if wheat_in_shed < unfed_animals:
        needed = unfed_animals - wheat_in_shed
        money = float(farm.get("money", 0.0) or 0.0)
        market = action.setdefault("market", [])
        if money >= needed * 25 and len(market) < 10:
            market.append(["BUY_PRODUCT", "WHEAT", needed])

    return action


# ==================== BASE TAPE ORACLE LOADER ====================
"""Project Aegis - Module 4: Base Tape Multi-Route Loader & Oracle Selector

Embeds verified, high-scoring mathematical base tapes compressed via base85 + zlib.
Provides dynamic town-shop matching and lookahead sell-schedule inspection for The Predator.
"""

import base64
import json
import zlib
from typing import Dict, List, Any, Optional, Tuple, Set

_ACTIONS_10C4S_3Q = json.loads(zlib.decompress(base64.b85decode('c-rk<U2j`ia{MoP)`Lk=UwPBm+}K#n$dK(2n}IMGAR7b-HV>1$1^eIQSR#3OPjz)wpF`SS_{juC-+R7KcXf63um5}Y@4x@?x4-^z_D{c_{q*VG{hQz3-+lP_>2ZDbbbj_9zyH_2{rBg;eE#^i-~af}zy8nX&%d6%efQ<B+J~P${pGj2U*7$EcYk(%_WEIScD`)B{_u9aen0uchxPi+=dU+!*LNS!&aY=*|Gd6`_~q<;vHSV^$A>qcUVq&GkE^Grzn@P#_Ws@LKYx0^f74>pw_ndT>kl8lwDp&V$B%EneA<0A`*1iAAJ+Hx`?p@q-@1L=<W-;{)7S1l&8Gr2VD`Fj_FxZpE%`Dhi-W$t{EEEm{r%nRbu^x+KimHR-ZpDDdF#u6nT}`EjxXQ+vR@1beSMj!;AiOwukYsX-!G55kL$<zBAS19xO(8yUCtNLhlfw|Mbs|NKmGsCIQVAPJ2sW=;2aL{Y?Su>dwut^G`Bx`-kFoGTXVS|uJ)zdQJDTJoi4Ed(By!f(5ztcmY1;yV>TI%X2#mz=ri^*?sVu5o;%-p`yp(nDOi^a;cx?+Av{|7*>cbYZDi4*lTY5ZrTSRP-{kWMhVbQt0dthin?8uUckDiVK6^i)58lA-$GzvlFTbRdKKA)^!iRKV`+p~I8v5My!&i9h>{hu5tjXjsH7<}bPo1Bw&h|Zd3+DC+`DtTDjA_B^hx_~W>yN+vY5n-|-Tk|NJv<Wz4PN;r#u6#N<4AL`y|pLp3HQ*>5t;osxXLe|3=8m^UjN4Y&ilBkd$+0m*J+ag^R6);Cq_6}xD`JG7$a~`;9k8fZOcsNeVFz(>ti~Az_B+BQs%0_PuT<6SfEeo1DQu4+K(OnXx!wY0~HUdWcw-`i2COF{1Z>7&-GP+r}S~qTQ-~rVBGH?*&2iS=5K)$Vq50zvmTe4ssuMXv0?q=Y2%+J-}}IZT44Zt(Pb1MAXzju*u~a&#W6G|xSdn$pl}UlhCnA&CtVCf3<QKThL=Y1Ze-y4{<!WN74S0W(bQM~Z;9qVy%97UqGX<s;o(+W{%8tN131kB013`TM`XwW4Oi*VlYfq-{o^2KKOXzzu_h)JTQ7F39t6{asC;5+T~^M_iZ5=0BSn|b07Lqshnd|~F;F~6$!R|ciT8S;>`o8H=I!0%zeFAD1&k)$(OrEp1dWDj*O%fDO~;~#AJ7g?8$jGK0lH8SKIprSJ-^j-W`I4i8<got<yZy)M-G<VevNJiWgo7T2YvrUbg4|=H@B~>=<t?cL2oYbhDvz2eQ?Wh`e7jacx*4ibLrSfmtXe$0gdlQ2Yo^#>cv$0@bU3(^V9nA@h^ZKD8-G~B^EXuynXT11BK)<ro)yD2`+8)BiT2i^!QmiZiZnvhp+k}B_oQ#f=-)b8BJ4rV+v7um=O<Vb*+!xhutNeKTd;Tw|DGh8)7c%z{q2lzcC+y;wp&xZGHXR%&LutK0P<I67g*BEy6z&sMF5lDmdTK*l|DNOkXQ%b!FQ$C$dyx^q}2oFR%K%5g#8=x`YX|EB-NczcYNLa<4D|VsZ;^9v<$$q^Uq7>gA6wGxYg@d?Q2x_rAClt}D}r&f%ms+%iT^7{nHt4{CG)$VTjTa^xYeL1)0w0a-tzZ~4(NFp~IExojm=s4IY~J05*Zqc-lF0#_24+I%X*kLyBM5i}8?nEOu^unvKK6aEpf7`wNEF#_$JqZ4g@HdOWk8*B8*92s!_w8-u}_FUsp0oP(?r5?)|x~k-$+CejjxWKU4DmSiRj;L*M9fwks*-ZQ8(olAGz3~nMl;P<{#%jFEc4j~bC^aX8uQPLv!vyLH0=)A)?f1N#5iO_dl3c`$o-)gM^(;k{2Ta#HPwSO21p$8DMWbMQT4O?m9j&{3AIG!UQ>Jy=zPCL##JT7TwOi&kZXLVlbz?ESZi9vxw=&p-?GZrkebA!W--;Qo%qB=blpI9R->_4~4wE^qbkjHL$aGH+J!Gm=j$MG>X0{u%F?X*?0ZWhW*ABt%Y@MepoDYgYf^P1`5#(@p?cHF#%a1Lla{#mA*stsf9#>x}rbWhnM?d-Q7JCtv)XbE}*WNhrXO>4%NQR)s&hC#rl)D-$ZntTtIBsOvZ+|O<Q8OVS(P*T6P;4J;--;<irRcZ^9fG5Ae;mJD%s;=o|MSbri`=31mwC=y59<B0rJvuoSmrx*$*=%>D#7BiVFB*M=rc$tw_wGAtu4sGSbn7$C=!x2k15~;j^;fbb828UFh|SU^jxsoSng(WdSv8G&+{a0R|pU`V|kGyqAlNIBKw7nR^(%~t;7drA5;$J9XJ_mcLC9|_5sDnXv<dxE{lka#C}Z9ef4nU)~aR>oa67+5DYM8U>*w}s`=W~lRQQ1*Z~;xyNh6i(jYhxXd{5TEIU(<KC$gd95hK9P_sL=En&=>g+5d<k~i=ESyn^?^d|yfR3M{lHG1wX!)g5g(aZ2R0G;k6&+aIpL<2YDgT9--if(@LJ53Dg82&r3RWkRTP;b4ErtZz>LAu8D(VY4o_r7ryV9pOVNM%P?{$Xz(BXjfHHM~dS+m$q~C*|zVLq^#OFDhVR0q1BP#=~g<mWGE3Yi&jFiPWv1-lvECFVhQo%ub26(asu{CR580-D>G@sN}VRgNnT?fjtE;d<>U>@}8LFRttN8%}~j6mR#=EhX$4^*^-064Jk?LPVi~L-$WG=owOZ6(k!V+@_&J;2f7&lsxxs}SqrUMsst=sgSAfk<J<h$Ew-0{$X)1l4s!hrAxsGwrhSpcv|SZ7yc0AFm~ca0dCJi`S*yO$!5U5m7$amenlDgmm7MS=LkVS<I;ZJ;y>LC@&s4(ob+t4ZjwprgsflNb;sh(}`l(NuSm};D=tm)pf|b!H7g=>BEA&smc9odpFhYu+(XA~2=^Kep9aHf`52hHrA+J&s@Uq;_Vv1MmPlExPzC?`n_GX8vk7iAQVR@xY*%T1IbqOg@EJ<^TX*ijz!~m(+N$lXo**w!Gg8!Vhx266R17)}wP(mye&&peS(*{B=pY&URah&<OZNCANR%-uM2#GEhhH1f8G2=;qdEvQ%a<>e8&J43Rsx1d47e}qHgNG)aqdao4k#IPKTfU9p(k^5Z7niMET;}VM;li_lxJo8>!wwNZkCtcjN;pI`G#T6`<}BjHL6&PerHf8~3HWrVjj6R1)vr`nY_50;lEK(~Y%~KZ?1AJ^olBS`$rix-rezM2BZbw(3{ByDvGw)KLk^1oD{5p1d~!gtz6uT!lDz#ajWQ@<ds$AZ;Ly#tl3)>46t;Zxqf<5ZxdHugav}R#B5)WICBX9(KpciT$cf@j@dwLgmU$T6DI?x<4|G3fp<=yow6fsr@H$vTX(tL1?3P`^n`P}<Pnb`*p>Lil08$G10XLY0ZaFu-i=ly-%Sslv#v_QxV~JV7jA_7El9CAMif>FIbMfeiLSrN&>4+n*j$#-bjJ&yMxC1|a)wD@mY|(g%p4=(O2<iROM*A?8%$s)=N!Y%sE-T`e@dd54j#0FT3SxNlpBKBdiR%<lfD-_4alcFVThbLOUY0F1(0Yo2D1|kuNkSAL1TR(=Q~Mi7x{j<8@mS<Ca_FxEmx@w1m229?U(@@9el=|6&_EwxQi*VEP34ddErsiIeTd-aLvE?znidimBuGm412`R07$ZTL-Ivq$+$5OI@j)4Y&bYbW>$)P*?p{LqF%FYP##T%oM3M+oBg&9KNE?}~sSEj;PyJfWPOgaVv4E9PQDw=ntBPhC<C-vW0s{$@)r)VRDg-Ht#xT<S{3}5T-bgXfsa)LO7$jH?>}WZeNFi!ji>`$uMCXgSy5b}*D~uN^C@AGIR^|-(V`*()HBSh;*0pJ*LCcJEr6|@^y+;;vWnMb-wOnr4@~PsAX`x|33TVVIQg;KC`%C;@r`8a2mQsICLS_{YPsj)t$}Uk5M*L26>4KH0AxgCEb<Z<g<^C38Ep)tmjqZ1p_Lir4)RGknGYN&w1AKzPM~DX@wa@jVpVOMJr$h+qS+5Y$>U(jvPey@gU28~Y)^eCbgrMMd@7=)NpNheC*|w_Su2N1!CY%OfxK5HknBUzd&Yab%h(U?F&<W18s|1ZI|4t&KJ)b^{ke+&DFxfTvl$;KedJk^?fF;kEz7z@ir3HXgkqg>vkE!1NErUahw4H*+BwVA6D`97o^r$mxYW)0@G}VPUbyk%}@f)J2K=aV3#}NOla}v2wDRXfoE^mcKjj#qfCMi{+vnZIdm&B_jOi=1CWUw{Xr_UE6T@mMA(S{vzpD_QP#Uf+66~YH*|IJ4Lv@ma8tQIedsCy#<>6^8xZsLlgR1`WpTLXwzezRKFxL4kUW(;JB93#^jln)bjt5Q-~Yh*1dejE7im#y!<_<FuO&sIP?b)a9qUz$j*EkqT%>X!mPs|_Q<l+`TO-0NExGY85cR%M2|RVFsY5%bs!%pEI_k5a8nFA<U=HFEIzrlx*KovSU$`XJ%))$`E4e3O|NlPb)eer&e-5bHZWEOc>qiA~RPku*-hKy4Kg_RZ$4PfJ7O)E9<abiJwCe#Kh@gAQ*2g|o{#tk!=~Ge|<G$E*Q?7Z~>FqzXKFIvuf~jY6(NP&F1xRww|)BIVTcTEm@8UTjDIE{uS`G3VpPfZ`5>iXJ-NMH_8us7@z?XXm&%Ad1IZ(159Ns|Ry|F9M<c?;>L9xIrfkSfX8#xJ`r7wT}?XluDZAX1huvCLglF7A{Mp)Qi9?27#wKPaEE6m3;b6igCMg4vYOgi(?q$Ke5&|&Tm@z56Qs1GSVq~`QX!e$3{RN6{>iYl1~B_B@3Wo_MPbBrKZfa!?DayD9QJ!lxY_+`kN<%Crtxw)FDi*TVJv4RjJ}VY=xGIE|J3v?e_EqJxfsQW!~rm1+^Far9#&B;<BM%C|-b?zN5zCW-A^x$I7oQEE^IBP6(1(B5NXIAj%~Qo}Z#Cnf(!;`Q*qM+;WZOog6-t7f_d{T$G$|Ev+Mw5AGlgqn=zy1+8phMq=8e;)Y}T(Ov=K)|9X+#_Okn)oORNI6tGq63B&|{lgS#m;FK$a^WN;)rM!h)EDAqJ^kUi#O3~977(X&`0WECj>J(r)>YGSc|&>hQ|Uj@#M^H*7GI;ykBQ3HorE#*_{@*i1LnsG((A<xx>%upd_HZ(VBANU-&SmDkeFj<EFZZ4Y3Rksbk?HuddM5y*z}q$1mIa@yPBJ#6seaY@v2-Ssz4@3g%qMOc){VqkxY%_2+x_)giL9m8}<~$l9m6gEFe}7k~mdKi48|ONr3^VA|!EtDgl1UjJ0DT1<hOy6@wNBWkGjRQMF`pMeK~i!qrf)7A4m-6^7{;Fh;f{(ytNZ(?tf_!6#uY$cDzz^%3JlWJ+D&Emv$TOe3XS4bgHtCign>_f}uexdX)JuSzih<XM?xKrW&YlmZ%u)5W(t$q^Or5Z+q)mpmv};Bd+gWA=B!!N#b6e;)RDiMz~B1qZMk$X6qGaklmCQ^9vl&F9D=$vOs?<lKT)u)vZxOhfG=qh9jHvV~U%-4!?cuzkAs#FIz|&zQ!Jr_o8ZK2T3c+~Km2FcNnOH4(USlf8U!u|x&>50u_LCaOtb0#ytkV6HHbV@O=nIHTEdCQ?Jx$P{{9Pd&lwhC{M2s4z4SBY?vwd7#~jlmDD|@VaZxlBlj!Y9%{>$IRMQHRdj<3L?d9#bLFkN(xzP<PI%WBV2`aZ;d!W>hWssCon7%vkJcOYo{*pRqD`Xoo$|$@myFvf{oJIwR)_OVa)ru>YXNu4??;Zu`TkZUs+==CDK@3=%J={>?0y408|WGxrX)|K%a<j0kLn#gT0okxOOSouisD(&hp!l=qI&lM9nn;(;Jd-V}Ub90GF0}EN0!vY6|E2fA3eDKZUmcMy*pYSV_T3#VMrT%gS=JU!A1@G93o$Z>0cjQuB0Ri2(E|La$0YSrUYtp2)YQQUc7&z$0r+f_U3nIW!`xM6A0xl$x(pCBRu(iFKS$#PqY}+m&h;@Hz@odJwIWuEJW^Mh=a*AP$u4nwAMW!d^yd#dJG83-uV8K?GARq-Q~};Jmxq0^iv<WksF8m}qq@Y(xbPg?g2y=s`!nR`qG5s0Ypcq4_4zwyb4jDBw@)nro$D8R|V)fxpKoZ%=-j0@G3bV0Z@|o(%0ulT2~qnaVptV~RpS&kWY@sRmN*)6kkF-@;a6buVcBO5Rrl3qOm$(T7&f{Pq>ewAx76!5da`MUAhR_OriYzKv=b$R^^%Xq9PoF&qrbC~GoO0Nqa+u?R2#B|F^kfDOl4ruCGFFH2)tS*oUW_F2~9Fu<IjU$@4>tQ5<X=L#9=#u7yn`3ms?3~PY_Y=Ynjt2CZ~ZmxGBY)-O@Sq*woo>GG#%}##dYb=+-EV9$IP}r4I&or<p?`u4H%NkQaVn?dn4{l${oxJK>hm`cCnt)EOp4bbr;Aq_xbvw~#$RL@{wM8dW%9z*OLtkY{Ii#hGx9GTzz#ls7)l;k|!EvLIGu4_VzH=j-vpg4z=+e-ty0lnrVY>nshUS21iHdnyq(1P_O5-bLK9Y%H_uLSwa*{c`wz)&cn~DxNULj;l3r|?5<A7UoJh7FQP{kxNk}Wb*JElNInz%-dLZ?EtWCkc5)p?d$6)CM2PTKAA(z_VM54(63L2*k~tmb>KOfy&&2OE8Qxti4A8^96E@PQO-GJHZqo0-91ltwY6oNISA-CQ-@t5%z~({R;vPSp4uOJI#3dJSfRTS{W&cDlyL(t==iAzDXAyt_sVQe`GQnaGvXI43nx7{CqV;82p*k+oG(hhbO|Lo}m&CXJoy1Dcn{MJ4$p>JFtYwC>?tRgiNh7mzkDQFirPPrxCX01I0|6XzH~M|II&)gU6K7Aq|oye&&m_p;v;qo_NFfOs-lAv|&MRA4r9O^9eaP}C9~V}*1mVBM<+AZ1bnhika6Rp;u`g1j=Vb5RMHk!XtfLvu;hJWDOfNJXEb`@j&GIyH(!urD?XTlULyEN$gXX&ja)${Ww!{8?jlU@$$rp|*3w0=h}rqMiAoI+!CVqPYw-MF65F-|v;!7g0!!(I7*PZp&m1p{{~a(Z|o?O3l+cVUUIL1DjIHg;DKR2wSa=r|orsF_8=q5f>U)7feZ_loh><x)(k5!B9qgw~m)n+^nM{wxWv!7mJ^^s=#M@>Zq1$#?*0J-(;Q02Fr>tg(&30NK}OPjtXlgdb{$vD`cOs6rgC|0?DN{FR~0q2Lcz0t0Jq|u%t%CQazUm3VMm)3W;q|;;_M^BB|Rf*V1MY^Nv9IGMwBSBWrTwiIQc7oQW1!Wi~H`*(6z&Ty%}mOZ54!94yvsTBY#hLY!dRI=V(f9Mx7b?7}F6#wS<Jwa%c7Q;~)l5WytT@P=fkGple{oJK=re3}S}MWhawp+Z1P;y-;Neu*sAb*X5SPy!^c7+>eBMtiYOW6UI5Nwo@w2ryndo6Rfntb7PpI_Xlh>W1#c5UTSe(9XU3Z)tyTjQ(CY)ejXlvTcg3yfN*~cj@WoYvWEMA&U54f$BR#U95%i{&8xiji-qn$VcQvu`t8(<UFxdA>Dz^PD>f9)MWd%d0|J8tN$7tv9vZhx`C*EolF9gND-6;rYZy{EN>e~sHNQME1%L)sN~X^4B`RAu?kXEq`8>{vb8dzLNQs(<68|PkI}EvA$4g>m!l|S0Xl-IgbC-+!ERT5tg(dUlFCm>h2s5i2IG#oiZOlxK3_5Ys-HQQskc*oDV=Czq<mHd-NcIbq;*z>k-=G@n#>s`nT7RVlsa^!#Pyq+t^$WfXCicS){;a25enZOSIJ0WHtk$`(pVN9kZ!P^DOJg80L$Tmg4FJ9f4&_kV8pd`;QJVA8lQ<WD>W@Ux<W&BzR!o><3q1{zCP1R$CE3qUF1~suTV<3*u|Hjl=*l-oD3YVZ7yreOPl6~29(4&`;zIfRl&;3v8=aCh4r@hp4e@mmls{_?`OSnD%p`MSSG|Jm+y9@vXw`pydAHO<=0}ojV)uT39T!hFDERefT3Qo-Bw1qE&0I`WacmwnX0dmfRs~p#0qfDvX#p|a5@AZoiPrJ=q$rE8Dt;mRKWv#u(1l3r7Ao*yN(sT6xnqu38Y7bDB?XV0Z}KPXF>oC=UJ!XI)yF9(0PnqtYi{W2h;vE4qli~^~yko63V1)x){|{x{Glx1jvZ+>{8`QG;2YQ;+U>p13G1q&`jqN%qmU%4iDZw#BW(r#LuX$G3=i_Vy4<&BoL-6vh7hqHxgyOLfQdA<cD4}I=zl&WQ!F`8MHU9gDaVLx2*8))H)+nRhD{Zy@gq8Y)LLf-y&b}`kvr=w)UB|YRiCbPR>hsT?FP-t7)BJME0m)YBcf{sloIHU#{Nm%lbl4dabJ5h=nG=Q@X8;19<Z2#Yk^~b@$D}ohPq5>I;x;1c(h!_4QX!nbUEO-tr4KPhJWzt2bIznoBgSOro7qr&O#Bprl9{;9G?PN$QYht0j%-bJ4EOYNN8{Dv4!Fqen2A*0(iP?pZ+>8aFnaQl$N^-IN-;(pq@Tw@9h84A>L%3-q)=#(flYl8&(KsQM#SCs!pM(sgE*<IF(T3e7GbIjOEDr(ALM^w9H7t-*_O${2`cio6B2>Wf;qrm<Jhww<<ImlWkwk(GgPrPM81HMG@IY+k&!#>MrbhQPoOAwQuhQC#PO5+56MsfFw|Rb<qgCl$ruMrdbgDuQYSpb!tSKsiAaomEdrb510>8CBKtb?lAyGm79^DHgj0+j6d9nTfpgPKI3FRfEWH#JKCYe%XMCRu1zz5F+?)s#3O;wiDH<^kvT!5V@^YdO|*!fT%E|skiLprciTIE%jDldmV-{jz#zq^X59`&!aY}?5%`G((B)~q%4Miuw+5CcmdpesS=At!1C4sIAK(E^$IwD)knPojRb##C!?GutajysL{j?5R#{UG1Tz+NjV4oZD7t7>c}cD`^^6?JBG0irZ)9=GOD)kwQsmG}rBh3)bDks_F}an(s-jw;I(s*jWf^7>si`c*Z6#`tRb#d7GG$uVLER@IJIR)8vCh#})Zlp{(1LBJ2%I?Wk5J~}#LVy2BYS?-Wu0V0(g~UDK1s)tHf>##XVtZ3DSXrJRjsZFq2qMdseYc|g*?HX_#8W~*kAyB2O$p6&Y%n{EX~baryybUEfMdZj2BC%>@9VA9%qRSC)QCeV7$XwDyBlwo_6dyBEKxXop0r2E=psh#J<?yc;wqyB(IL5ZpidAeO(_rUa}go`v*gi(_Ob+Qqj8n&QefcZW^=c9r+<FU2~ec0KZJ?Ff8)NDhhE0x<UIP&F=&RHdZi2k2SLoRY5nI!d76H6gguhvRogTu0~(b`D2;Vx?12M2a$o63YcRa#?%G3W1)YBWiEP-nY7|haSAkYn;IId!6_(DR?z#ifP78xB~2K-H8?V9j#!#brsTP>eq4u@lk`K(V7{o@x0!7?P)%Pgb)X^rc8q^j%A{dj$q9Xdh~EhVQ432{t#S3FM+CEVtd^$$-C;_e=0Nl070SnhK1JHl3zN0Zpl2l=QiVLF^TyGE$^`aI$F$XOo1hnZ(cJQ)hts50c2MrCUd5*iC%3Cx#LZ4^^k$Zla-GnLR2YJ!BPW_8oL)+acHLQRdV1r^61L}aK*^g_F(cl;gW*Me6^m2F;UqFLC8}qOr5|SR4d3Qq{R2TazSJWfO1ciZvm2E&td`t(8Ns{Y0$C!s?czJc)(+O$1zwV;QGAm!Zgj#QY><LTr2=R)(<Q}EpsOl+M+~X7lzS}YHzHu`mS$yg_GaD4zOoK{Q$z;~L!_{LTY}V-7&N^CbwjH8wdtL1V3uc0v3nv9xhxD^K~D~JV8ujF+vQBQ44Iq$gs+4UEZRpRL)fUtw<tlU)UcyjFVmLKXa?S#ET1X~gL!!X8JqKjzw>>xbc&a1DMm8?PmDI3wxL!Vh9-ka2bTwAT^p7Y%z`JlVKS(#fTh(?!j1=m3j_(I!gTXWELIb>VgtJ3owG-CBjY+H`UTf%qANzlWfGls1rv8maVo$P5sCEkxH-%=;w(`?Buda^U}Aib7Md@Rt-zWfoXMs-BRo^$li%7EWcg&m5*{##xE~>3u$FQ*PM?hFZsf(V)M_c4>h0?k1Z~NDo0?9Nx6F=;D8+JFOKi_)pv;gu0_`LmHG{ODv9;{WB#rEAQK-L$bjZ9Wu%?+oN)ZJCRJt%!OuJRRima(2RRvTaPFE*mj&Lo1lvm~xm0~yvM%z%D%tDG3X81=EdN%6QZQ>Hjd9_}#WSgE5m##H-JZ%WsG9RRNbx~KFYIn7a4W1TIOi0&N#xs?tN~K|y9xf_dLB$cPLAigf7v!WH&{KKi^<J!?0rLwi{GFP>+^Kgf;0kV{#ulj+*<mG4jO4ATrC`1_BRff)j5m$dJa!#zjJ+ZjP#rUVi9niE0650t{WfCm5+)iW!p5xl8Z68<tMk@5$$N*pdC>vUsHG>g|6%^O-Z&q7SI>w3DIMFMF>^_M?rT~qZ|Wwa`X?>zqED45VPf*z54l}+x(7uyglN2y+L9ErOmC~O+@A9CWUMJ+G|`#QUd^tQB>t4KTXRJoYPV#Hh@8fr8l1UNBFbgzx)15l!(&}cIZf(<>hA^@TtIA9>X8a$E^<e)J9cny@sN|(R*n?%I6ksQXE)AG2(%poW5xp{lsA!ARvg&&O;VM$-kuU|N>aF{tEV6wl}MHPbxA=_>EWjo={ap*bxK};U*lGi*S>jtcz^iTmv1H?cwfQKp1)%0;s%Fa&`)Z2UE7J>hux27-=y(D(6+;nVPgbu4d|!8Km8w;Fh$h')).decode('utf-8'))
_ACTIONS_8C6S_3Q = json.loads(zlib.decompress(base64.b85decode('c-rk<U2j`ia{MoP)`Lk=UwPBm+}K#n$dK(2n}IMGAR7b-HV>1$1^eIQSR#3OPjz)wpF`SS_{juC-+R7KcXf63um5}Y@4x@?x4-^z_D{c_{q*VG{hQz3-+lP_>2ZDbbbj_9zyH_2{rBg;eE#^i-~af}zy8nX&%d6%efQ<B+J~P${pGj2U*7$EcYk(%_WEIScD`)B{_u9aen0uchxPi+=dU+!*LNS!&aY=*|Gd6`_~q<;vHSV^$A>qcUVq&GkE^Grzn@P#_Ws@LKYx0^f74>pw_ndT>kl8lwDp&V$B%EneA<0A`*1iAAJ+Hx`?p@q-@1L=<W-;{)7S1l&8Gr2VD`Fj_FxZpE%`Dhi-W$t{EEEm{r%nRbu^x+KimHR-ZpDDdF#u6nT}`EjxXQ+vR@1beSMj!;AiOwukYsX-!G55kL$<zBAS19xO(8yUCtNLhlfw|Mbs|NKmGsCIQVAPJ2sW=;2aL{Y?Su>dwut^G`Bx`-kFoGTXVS|uJ)zdQJDTJoi4Ed(By!f(5ztcmY1;yV>TI%X2#mz=ri^*?sVu5o;%-p`yp(nDOi^a;cx?+Av{|7*>cbYZDi4*lTY5ZrTSRP-{kWMhVbQt0dthin?8uUckDiVK6^i)58lA-$GzvlFTbRdKKA)^!iRKV`+p~I8v5My!&i9h>{hu5tjXjsH7<}bPo1Bw&h|Zd3+DC+`DtTDjA_B^hx_~W>yN+vY5n-|-Tk|NJv<Wz4PN;r#u6#N<4AL`y|pLp3HQ*>5t;osxXLe|3=8m^UjN4Y&ilBkd$+0m*J+ag^R6);Cq_6}xD`JG7$a~`;9k8fZOcsNeVFz(>ti~Az_B+BQs%0_PuT<6SfEeo1DQu4+K(OnXx!wY0~HUdWcw-`i2COF{1Z>7&-GP+r}S~qTQ-~rVBGH?*&2iS=5K)$Vq50zvmTe4ssuMXv0?q=Y2%+J-}}IZT44Zt(Pb1MAXzju*u~a&#W6G|xSdn$pl}UlhCnA&CtVCf3<QKThL=Y1Ze-y4{<!WN74S0W(bQM~Z;9qVy%97UqGX<s;o(+W{%8tN131kB013`TM`XwW4Oi*VlYfq-{o^2KKOXzzu_h)JTQ7F39t6{asC;5+T~^M_iZ5=0BSn|b07Lqshnd|~F;F~6$!R|ciT8S;>`o8H=I!0%zeFAD1&k)$(OrEp1dWDj*O%fDO~;~#AJ7g?8$jGK0lH8SKIprSJ-^j-W`I4i8<got<yZy)M-G<VevNJiWgo7T2YvrUbg4|=H@B~>=<t?cL2oYbhDvz2eQ?Wh`e7jacx*4ibLrSfmtXe$0gdlQ2Yo^#>cv$0@bU3(^V9nA@h^ZKD8-G~B^EXuynXT11BK)<ro)yD2`+8)BiT2i^!QmiZiZnvhp+k}B_oQ#f=-)b8BJ4rV+v7um=O<Vb*+!xhutNeKTd;Tw|DGh8)7c%z{q2lzcC+y;wp&xZGHXR%&LutK0P<I67g*BEy6z&sMF5lDmdTK*l|DNOkXQ%b!FQ$C$dyx^q}2oFR%K%5g#8=x`YX|EB-NczcYNLa<4D|VsZ;^9v<$$q^Uq7>gA6wGxYg@d?Q2x_rAClt}D}r&f%ms+%iT^7{nHt4{CG)$VTjTa^xYeL1)0w0a-tzZ~4(NFp~IExojm=s4IY~J05*Zqc-lF0#_24+I%X*kLyBM5i}8?nEOu^unvKK6aEpf7`wNEF#_$JqZ4g@HdOWk8*B8*92s!_w8-u}_FUsp0oP(?r5?)|x~k-$+CejjxWKU4DmSiRj;L*M9fwks*-ZQ8(olAGz3~nMl;P<{#%jFEc4j~bC^aX8uQPLv!vyLH0=)A)?f1N#5iO_dl3c`$o-)gM^(;k{2Ta#HPwSO21p$8DMWbMQT4O?m9j&{3AIG!UQ>Jy=zPCL##JT7TwOi&kZXLVlbz?ESZi9vxw=&p-?GZrkebA!W--;Qo%qB=blpI9R->_4~4wE^qbkjHL$aGH+J!Gm=j$MG>X0{u%F?X*?0ZWhW*ABt%Y@MepoDYgYf^P1`5#(@p?cHF#%a1Lla{#mA*stsf9#>x}rbWhnM?d-Q7JCtv)XbE}*WNhrXO>4%NQR)s&hC#rl)D-$ZntTtIBsOvZ+|O<Q8OVS(P*T6P;4J;--;<irRcZ^9fG5Ae;mJD%s;=o|MSbri`=31mwC=y59<B0rJvuoSmrx*$*=%>D#7BiVFB*M=rc$tw_wGAtu4sGSbn7$C=!x2k15~;j^;fbb828UFh|SU^jxsoSng(WdSv8G&+{a0R|pU`V|kGyqAlNIBKw7nR^(%~t;7drA5;$J9XJ_mcLC9|_5sDnXv<dxE{lka#C}Z9ef4nU)~aR>oa67+5DYM8U>*w}s`=W~lRQQ1*Z~;xyNh6i(jYhxXd{5TEIU(<KC$gd95hK9P_sL=En&=>g+5d<k~i=ESyn^?^d|yfR3M{lHG1wX!)g5g(aZ2R0G;k6&+aIpL<2YDgT9--if(@LJ53Dg82&r3RWkRTP;b4ErtZz>LAu8D(VY4o_r7ryV9pOVNM%P?{$Xz(BXjfHHM~dS+m$q~C*|zVLq^#OFDhVR0q1BP#=~g<mWGE3Yi&jFiPWv1-lvECFVhQo%ub26(asu{CR580-D>G@sN}VRgNnT?fjtE;d<>U>@}8LFRttN8%}~j6mR#=EhX$4^*^-064Jk?LPVi~L-$WG=owOZ6(k!V+@_&J;2f7&lsxxs}SqrUMsst=sgSAfk<J<h$Ew-0{$X)1l4s!hrAxsGwrhSpcv|SZ7yc0AFm~ca0dCJi`S*yO$!5U5m7$amenlDgmm7MS=LkVS<I;ZJ;y>LC@&s4(ob+t4ZjwprgsflNb;sh(}`l(NuSm};D=tm)pf|b!H7g=>BEA&smc9odpFhYu+(XA~2=^Kep9aHf`52hHrA+J&s@Uq;_Vv1MmPlExPzC?`n_GX8vk7iAQVR@xY*%T1IbqOg@EJ<^TX*ijz!~m(+N$lXo**w!Gg8!Vhx266R17)}wP(mye&&peS(*{B=pY&URah&<OZNCANR%-uM2#GEhhH1f8G2=;qdEvQ%a<>e8&J43Rsx1d47e}qHgNG)aqdao4k#IPKTfU9p(k^5Z7niMET;}VM;li_lxJo8>!wwNZkCtcjN;pI`G#T6`<}BjHL6&PerHf8~3HWrVjj6R1)vr`nY_50;lEK(~Y%~KZ?1AJ^olBS`$rix-rezM2BZbw(3{ByDvGw)KLk^1oD{5p1d~!gtz6uT!S}FKh9A!|-_OhH-!NHqvCB-7DDQtP?M<;9SvjZsMU5u3r8Q2nu!;mQf-lqWMFyui_7N3q(MZQR8V{|8uc+Wjh|7dvfdI4!=+1X)su#nPj6e8Iz%Y-+}+Pj`WpKw#(JXL_C6#4`1FbUyuj(QhU12LGDY;KKD5Ru3d^MD!EfVU(i6VMgkm_+8{(UFD5SU$KEPPIOY0dX+)=Ca|g{P=a#rgO1n<7s<x_aLLD_lq3u16DGF-qj{yJFB{^h=ax#w9-08)*^a{;o*N??9wK#SU{mp0L8`qF5PfRSE!6xw$MQ9DH@`b*r=upQK%5SSXoT%ZyXUjvP#5bkqgS9zYbg~N(EJ}ZWn(|?-Tmfu$4nYet=UY0<$%}Lprn+xX+a$f}an$rG~3pNU)F~F5M61bckY%1Y>qzPTO;nU^mAHX8=m$W__>g+C;m131!MSoEjNnF&Pm_N=%J1LqZ~LjIyRP<mW*3t2R4XBf7@|Rz^jiB}1?(>S>I1!ej~zJW$p#zJ01tr6?Z5==1Zh1WkA&*+3_CaerfwbTzP}<+LJ&vSls07LX8~FXrlslenyKU#PU8l+jq3Gvtq@ResfsA?#Y$rjdp(Gy0XHT~qZQS@e~8>CD%1Sz^nliYulCi3L%h5yME`4N&+m@q3-BL(Ex9{W%GnRXjW)H(V&dL_rwwJJF>JR-%R|(YDt;&v2FdTZpyL@$xm|-%;9Ip5{?YRw&UVlsFIY2?ie_MugNp*N=WqaK4^WBB*D*LX@lT#o0a?6{2;mA+1@<W)2a8g4?}!19yKa2H0iWs)D;p*%6t98i3(C>Hc7TcbhnKR;zLbCH_JuIMc2YG^+eNiI(<!`Yb}C>W#r^*MwAZQcUVSxS0f&P-FU1B<+`$0#fBJXtO=edi%Ew4lxpV3Tl&ZjWV``ombMM)2Qk4^H0)L7v|JiRUXxEh_V9BNTVJ@{IkwU<dUV##gSOO6+$(_8t9m$RE5s+V9H(+ua+=XslTMb)>xlDUx;)??0ZEecF29g{CgIQj0sl=ADI0&9|6$9ym{GLyeOjXjR>S~)~e2lE0a>u>g;R{AX@p&YF*=Ap%a=rkfn5tOmI*>O!%!zab>NMwW#=Q;JaV8zWd_q`R+Vx0qxX*e))cBBHgwSRp_c@3jC}#j0lrgvsiPlZ(YnED2G^;8S2)X*c3<1V=pjwtUNwS-7>vcNQ%_R!RMQr4kC4~wlwR5)W=uPL;LbgW@1e0F?ag0+3G{A@A$CLW!@z|J<CYaI0XY$R!G=4o3}ny4Utn{7;@3|rn>tTZw(AOyag1_F6*#b2}aE!37sCZ8U$Wo*rStb@#IN$#DX?Tx(-3rSSVSc02IrWQ_pJ+cQSdg9sRp70{+IFj~fGuI}j>*=y(@xw5g#woeZ9x<K}=U9&bSnrpB!v%muy(B=^6Ih^6BOoit#Hc17Yg4NBWSLM&4%ZkC(vDv6kU$Oc=uERCWs0<RbZp6Wbpc%N0W>N_dM?aDbU`}Zu9VT}L8TGu$gX$?Rm2=mHFr|ji}Pv;#Q0eMuY;!#RI30RaYfQH$3qKlWBGS?2rGC!dt-=|WrUBu{bo(!He4YW~*Ftu)d?J{9|B(9cLltHW$FH4oZ>Qfr@EJ3Z8d7}@s)L!tH3R&BW%Z7fTcmZlkj~a`ct$5fRE5Ej|Y)Bk9AxLV8tci$$D4ZyGeu~0m_D6i?lOtzv%QcpFa`;eQKwYSEQF6Yuw2nkbxPvf^dU7F^wz4G}iD{F{9FFNndj*JFQ^Kkkub&21tKHG!{EQAuAQy7>57VYy_6tqOC6ts@8=mn}Ux=6W^oQqSm-~NNK%COyw-1Oo5=ZS=S9Qnb4du~KB>+JaZ@<-8e2q3gCMsWd62`>iGe24nm>(xdua`CGVukwg`Lq>-aUW%VTd}D@l8&9ReBl14p%)|5S&P!^A#ZeJ(`&X6fM=2IYHo^Bu3n17tAdTF7MUCsQi#Uj1&0eqGBu7PJZFj%GNplT*i(>AR{pcHfLLWn;#4KYHXP|B1qPs+ki`9|1o$O0){co3lyfyy3|btN1>H$S)so2-u`>z_S3|*Clw8wP7^Y*u7}=6szebQx7a3>=pM<p_8yZK~M~oAZDRqIjT(Pk*jg)dVM9b}%-0R5STYWv}4iKBaD#ZYhXJw87xrjzk3TPZom*4IrM^wB+cx&lj@}OLS!znwA+1~{R8>9aHdD!D6?lL<S9KdoQUya<w+19sD1>ZF_pCgAP>lj>;a|>3%0!!X74YiAmddVBh7G526SKREw_UYaePa+*WV;Vc2Mkm!uK|LXHhs#33NZcjVMBvIz_VU5SA{FRAP<r>6s3w64R55^nxxzq>A#qLPjAqA~NDWaVQ|NI$l?AUG4#~ox!q7a701l(%fp#lS{&U{J>#jLVqPkMCmFxf>Giz7Xn7gDZh!nFGht--YDP*mYJG4}da23+MHR1rN$E&%Yz_3irDtIoYGI5EoQim?<Z1c2?=fdg{Y?RKf)nkPWW8TMA?=(q#5YoMfZIL(q${KSik;dvm4>hf09}zhLpkmO<HMHLV`b2ySh<!UA?6q9QRZPi#{f2UImfwy<KdDV4YOV>G-jIYF3!E_mxU}SBG3!QFQ#jZEd%xQJDYX4JYMp|?N(xpgP9gPPR+gjv>MRA2=`c`#D+Oqi+NT3c1fWk5dR5xVk|5;tM7}MR5@22i9$8}&#M{=&p%GanV&%=D)O@8X0nW-wtmAwlrk^d}u2j2#*HMttgJ`{U71p{oa%jW_aiCn+v`p9$_A*jyr`zdSsK>|*BA99+Jqv;b=iSv7_|C>DE9(5kM5|+ABPwtx)T=Z_4?6m_s!t<DJ!tL^%{PIzWi2B^0e@Q8Tq_OBQ18JC{5?*2d-Bs1n2zcP!#n8kWN25KWQr5dRNfI9Qxpn%X0U!wHIQnbhSn_k7Pb<rdqL}0^1dQi_*wjoKD2V?x35U1)keY&-msD@YJA1CpZyi{ZB)xZHW4RAt4ynl;b2%sS(A|h=zhwGMSuY)+2Mu<Y&gy`t*1nMSsKgAQZ=o!&$14O0p|Stx-}MNrC6psSI9^=mMEIYSBMW_SPKkb69h+CrSSxGbG-{;bCOleYS4@Flo|wScJd2fW4RP&k)5W6!mgZprh!d)U*pMJ)|dhkJ5uF-aQjN`<W=7~q@*v^1axxs#9ojEN9(4j+lf9y2FY};EjpP}#=Pbp`YKDxAuVORMaOjn{?K8so?<--jvIxXsn#^{og3kt<+)fymxfl=rNwFs+ZDJlGzUaWRLsjF^?`?08ecK<kxUG`=Y~*~lg#0@%^f=4RCK`c3L#rsc)~gz2i%h5iLJDRDkhPUY>}DTF$F5p#5HOZIu)uVGeGI6&a>32NNKfj(r%ZR-o+q(*u|>|id(W`HQ#$>n!&0#*yz*C)uaaB0FGFO52RR=;S(C#%nbgbG>ReRT)V63=Bnvlwc50uhO4G?qQ>V~0&D!xYcLbsQW7J#(=|Sp76h{k(K<Tf-8EW}Dl_59M6R61IjM=l0B#ruhmy38tgVVV48w{Tq8a5gY3x)V(7ZG*D#<5NcPMqCbr0vNf}A_KfV6puva8>E0uIpxSl9}hIL8P&s*Coj1`#o}SZT@NZCQf4m;Ig?Mcp|B#FNPi;faf<0<)QGLPXnvqL%0wE2KjK>s~zoDU%{NT*G~>I#-t#<dtcii%P(ZL{rQknoFwYS!zi}D*6=N2Zq4ZsZk_?eX&{CvR|HKX)9++<FG_g-gxfj&l;-(gX!T7wVfLl&`rt~?aUX|!5m2u&1Ik|0uVj<ey_y7h(c<N1{rd6TPAA=brp<?K7JNgYM#~!gDjLE*pyN(jB2++*lKk=ZLb52iDZC?xX`$|U`i6DtmtLbz38bAhBD&2b-bM7W*sH56<s8_Sp2kA1wPYLN3~otrjFbCChJ5tSXP87L?IVOq9VL^R9G|7+m+W{A^VJ_07d&2NG`2;k!3JC5V%lW6<NiGB{eFR>bXo%&`ShYNNkG|hYcPTN!@0-mNtu+cLd6p;pE;JS(6)2lq@UcOtiQvvw11ZCdsPgqHBy^qR)5bV6kS?DupK(;so2)(KQ<4sJ4<}7e*O0KDlbHbp~aeiZslC2quY!HzYfqS%tgeG#Vn~(?m!tB6YY76#`Nc|LGI)OJu38OGTrE5+HfS_&Q%T+KYV}V<y>3s#P#VfbrVdY+i|H<wLmANtdEkH*_zCP@N}%cJ9@GOZ$6c^!LK4eyFICZBuOJjcISbOHVgn8+RHBQN;fWRNoQmVl9mKk5e;kJWcFCJ|ZWIg&CG7=ZU2X=?-jmTFO|ZCfm2o3p;{b{ny}#rM1b?4Mg?pWD=M}il8hoRUtTGdD}ojE#+2U`IL@AC6~rz5Dy@ZRgkJ8&CMi`t(6fKipg3Y-)azfjDD34sY_eB97P!m&=E`}OgM)QcDw3hjU_CXRDMb-6z_*K7<bH7jPVQb`HJaR{mijUy`Aby=|meN<+Cd2CRV&Bt+OhO49)`8WX>qbEUf>c)S)XSuHV#j6*x3H6QP^4mK^$zQ26e+N=6E^Y3I_D#<J*ubc6LwsY+G@SPmByq;_xn^X)(ZBd)Cj-^WnX_)L^pscG5K6&kAZeLnmiA9~gE^_f;Wo?L0|BB!E%g;K)BF1`$<%*O-bWZ-yhb6Hzn+B7#bpd`lGmrRGP3RYf@WxZW0thdGY#BKw<yy$9wKkJQC$&OsXG9fOxe77T&tvnj#?Ra%8zZT<dY#B>UXkGDqIbkUU4E2ibwld0X$q$wwGl!wbRDF#Eq@1cFR)A}ktz7nj(;@iijB!{*XBn=^Ap1b43Le;lja9HLRpH6mb*$*6$gWdKAU!HX5$|CMh&uT^69Q;B&pH*?DQq!@&SUIiC6kaknD(b}@WOnmR|YbaP$q5D#i*XrU5s-fKt_aTmnv7HSqpL$$8_}?&?$?AW;&N(R%zmQc<}Zie#?>~enxGLVgKY2Gu8GYfiPW>ZI2SVktp*O(hdkBKlGZ>>2)+CTdY{hpuKS&T*<t<WrcUA))}FyveY~4EzDYDOL8gt7Ws<T_XO9owa=_oTLyG<a$dsgA~2^~P3r_BvPT6|qmi#j4W>8va`kRs))#`(YgOe&EHnY0(rslNz>`NWMtTdZyKffmJbB$wUw~vIKx}xbufKxIoQ`w!mS4De@=}0Vz0s=DT%uuR677^arDAOWB}K{r-zpSHQin8KEonrbi*|KZ8<j0rNi16$J%Y)!zOAWp&kDNGxUu1sBJFqWrqtM#*1}`HMM|Azz@C_2pr-{g?xUcSbcAI`)gP%kxhm<9t~0Y7X9luXXm<I?Np&?j<%+APhn{b04PKN}#y~7n<SnRGU(~`ijlF`l?X=~(q$r<?tPF%JrEbZpp{<r;^WwENF0L0f1O|o(`3X&l;yM?U_}HLJEo8T;BBS0ssVD|FLOV-S5mYMxg?NYs$_b+Ata?J4b0X2rsH&E)V{f#dQ3TgYvDhuxmU9iuOys3^GUV#68bp30#$Ctt%LYWWa+ueF5W#m-m9nL@ov2QwFMFnd$Zf6C6Y{|XM1>hmy=5mig_@IUskZ{#>oAmYEW($VH`ghD9<@njZzVL6UjMEoWikANB@3#>3*hEUl~^nSmbVVT38Sj3SHStJKI#={B={RV8Rax#wJR4SlF~=E%9?5*n6aR1G?|J+(M7AuOLC>DXXHp0d5-0IBa2gBYKbnAB8Ofoomx_z^CZcL$*mMt71aXO*}JJM%P@;bO=T%=D^Yu_8mn!WDbu<R>OKkCNw#E*b&j^82G0|L7Hm63;KXTvgfb5&W`3_8+4G|=>m(bJPRL~UNjjFaY3rIitFA3e;hT1^YIQ{j9jCia_45QT<O%M?=h$(@1_R(b2yu9J24z@bX>R5^1qq{XiFp5HyjVJAZ>iJsI7@6ev5s;9;~maYF%^pTv}4y1`DN+td@Cn&Q5qv9_Qn3jBj3g%d36+ZL#ChU>-yO7lGTXaKNy0X?z-)giq_?KmV)|n)0j=~$PZ!Zn$y$;_+?UuVUa&pQHU$h4cZTBekUNXv4SajteJhN3cAS@wgS7P$Qdh<<@(5UHTr_iAIp^1)dB}Ohzzt;z#Q{1rY^W03;i=JbJ26mq!oXPQ=pOC)X-oJPC<FHg5IA6<ZFU2X~N*G!I4RG#L{#!CC`QR<2tOIq#t4i^F`IZ&1}PgYWixa0}bi7WBjX9CJp0CPUs6n{7x8%T3DiLjjJa;BABgXwLAsr4pZ_p2bw3ZP(B{?Dbj{sn5=aMJuB&uD&#4hH;xWeCa`BZrmcqC1ijFU=9U*doF=WZgK}T>Dn4B}xn12NZgy&;H?x$K>x53E!Vn}KInf;9^ioQ+>&|M^(;HWousxpxO5UW38S(xd3@_@dSez;jCy|jUQ9WBM{V;oP_%;XY9|*efr5@=}(sj_C-Kd;lwdBUj2;K!3$P&SA7vCYacCgMa@RB@@;+vFlqZ9sMgA_z66+okzE-8KjT~*OLVo0T>++!)f5dmAbG%J&{H|s|Bm382oB05+YB8BDK5~QZYpy?H;8&b`$P49FAvpi#p-4l7pWnth7dUBuxD<*o{E@!f3$lUZNd?kcn(LNFx!bUy5MF~2kh8@j%nYMgJGw|kQ`BX_5%*zAF*qkT)o$sTiQ@m75F_QUzVzk+`4Yk@ZG#N}fxI7^1+OV8p7CgZXlR<3-EUktTc03SVAV?q;rkht{v6`qA8_*T+oIRQw8P_S%FSt$<T`?*yljyW7n7CVtQvsHUNTi>~&0)3?XNd|TQGzA|6XS!l(0qYx1=a-NOg7aS;h7Sj{MN1@%O?|-@PJ9g{RsJjwUo1Q`eaOZBQJ)fR!iAbZ(pY%XiMhX)O3=(Wp-3VDVEDxVtYOVWroxdXeZ&Q8KnJ;tz};(X=GoELj5(QL*_MsHO&lCiYN%6(uJX7+O6tUWK9jJDxd;!x;hziglqYuyfUAt6vIg{+J@3(7E+`z!#|SHvr(UJ6PHlVtM!T{+w_dMbgi-DX+y}C`5?8ci@MrWyQ^hv@U(zpLb|Rpo~b-lDh;dja8cO`DvnqU%KdY_ASc~`p2{1q_hJPNm|tMw@6-h5PQ6<JS8x+Gwn(kW4l8kDByUA61@o;L*-7GLylJfFvFm7K>=m(q>X`9M1k$7ez%dr@w-IxfFwqzhHfF`wU}3gdowv?O-aFjQiw=lJEj^+A5A(nE#`)O0dOq||>Dcy+nM>+(U(-@~Q#TpaKWS+feX2wW6O-S5$nC1rJt(RnMB|mzmZX?vdRv9%_LP?=V@(O8iOziXYIdb0@u!U4nk({9yCqXZ<TUow;LME@Q7%*0eMpBM9_wPtX;K$de>b?`0%EIDk5nLYkvodrv4eYyhn&2&a-@*Q@sTw;yK!zppzRnKGaewJyotQB;=s0VlB%rr_LOK-lEO7zJq6*YM5@%UOA2~Q4?m?y&uROrQ}X)z8n=?X_RZtN`@^@sd^7pL`wD*c{1r<VH#qcyep0*Z+D_~~?0!7^CXEk*wjG8H8zXpYKtKKc>Hh$n7D$l')).decode('utf-8'))
_ACTIONS_6C8S_3Q = json.loads(zlib.decompress(base64.b85decode('c-rk<U2j`ia{MoP)`Lk=UwPBm+}K#n$dK(2n}IMGAR7b-HV>1$1^eIQSR#3OPjz)wpF`SS_{juC-+R7KcXf63um5}Y@4x@?x4-^z_D{c_{q*VG{hQz3-+lP_>2ZDbbbj_9zyH_2{rBg;eE#^i-~af}zy8nX&%d6%efQ<B+J~P${pGj2U*7$EcYk(%_WEIScD`)B{_u9aen0uchxPi+=dU+!*LNS!&aY=*|Gd6`_~q<;vHSV^$A>qcUVq&GkE^Grzn@P#_Ws@LKYx0^f74>pw_ndT>kl8lwDp&V$B%EneA<0A`*1iAAJ+Hx`?p@q-@1L=<W-;{)7S1l&8Gr2VD`Fj_FxZpE%`Dhi-W$t{EEEm{r%nRbu^x+KimHR-ZpDDdF#u6nT}`EjxXQ+vR@1beSMj!;AiOwukYsX-!G55kL$<zBAS19xO(8yUCtNLhlfw|Mbs|NKmGsCIQVAPJ2sW=;2aL{Y?Su>dwut^G`Bx`-kFoGTXVS|uJ)zdQJDTJoi4Ed(By!f(5ztcmY1;yV>TI%X2#mz=ri^*?sVu5o;%-p`yp(nDOi^a;cx?+Av{|7*>cbYZDi4*lTY5ZrTSRP-{kWMhVbQt0dthin?8uUckDiVK6^i)58lA-$GzvlFTbRdKKA)^!iRKV`+p~I8v5My!&i9h>{hu5tjXjsH7<}bPo1Bw&h|Zd3+DC+`DtTDjA_B^hx_~W>yN+vY5n-|-Tk|NJv<Wz4PN;r#u6#N<4AL`y|pLp3HQ*>5t;osxXLe|3=8m^UjN4Y&ilBkd$+0m*J+ag^R6);Cq_6}xD`JG7$a~`;9k8fZOcsNeVFz(>ti~Az_B+BQs%0_PuT<6SfEeo1DQu4+K(OnXx!wY0~HUdWcw-`i2COF{1Z>7&-GP+r}S~qTQ-~rVBGH?*&2iS=5K)$Vq50zvmTe4ssuMXv0?q=Y2%+J-}}IZT44Zt(Pb1MAXzju*u~a&#W6G|xSdn$pl}UlhCnA&CtVCf3<QKThL=Y1Ze-y4{<!WN74S0W(bQM~Z;9qVy%97UqGX<s;o(+W{%8tN131kB013`TM`XwW4Oi*VlYfq-{o^2KKOXzzu_h)JTQ7F39t6{asC;5+T~^M_iZ5=0BSn|b07Lqshnd|~F;F~6$!R|ciT8S;>`o8H=I!0%zeFAD1&k)$(OrEp1dWDj*O%fDO~;~#AJ7g?8$jGK0lH8SKIprSJ-^j-W`I4i8<got<yZy)M-G<VevNJiWgo7T2YvrUbg4|=H@B~>=<t?cL2oYbhDvz2eQ?Wh`e7jacx*4ibLrSfmtXe$0gdlQ2Yo^#>cv$0@bU3(^V9nA@h^ZKD8-G~B^EXuynXT11BK)<ro)yD2`+8)BiT2i^!QmiZiZnvhp+k}B_oQ#f=-)b8BJ4rV+v7um=O<Vb*+!xhutNeKTd;Tw|DGh8)7c%z{q2lzcC+y;wp&xZGHXR%&LutK0P<I67g*BEy6z&sMF5lDmdTK*l|DNOkXQ%b!FQ$C$dyx^q}2oFR%K%5g#8=x`YX|EB-NczcYNLa<4D|VsZ;^9v<$$q^Uq7>gA6wGxYg@d?Q2x_rAClt}D}r&f%ms+%iT^7{nHt4{CG)$VTjTa^xYeL1)0w0a-tzZ~4(NFp~IExojm=s4IY~J05*Zqc-lF0#_24+I%X*kLyBM5i}8?nEOu^unvKK6aEpf7`wNEF#_$JqZ4g@HdOWk8*B8*92s!_w8-u}_FUsp0oP(?r5?)|x~k-$+CejjxWKU4DmSiRj;L*M9fwks*-ZQ8(olAGz3~nMl;P<{#%jFEc4j~bC^aX8uQPLv!vyLH0=)A)?f1N#5iO_dl3c`$o-)gM^(;k{2Ta#HPwSO21p$8DMWbMQT4O?m9j&{3AIG!UQ>Jy=zPCL##JT7TwOi&kZXLVlbz?ESZi9vxw=&p-?GZrkebA!W--;Qo%qB=blpI9R->_4~4wE^qbkjHL$aGH+J!Gm=j$MG>X0{u%F?X*?0ZWhW*ABt%Y@MepoDYgYf^P1`5#(@p?cHF#%a1Lla{#mA*stsf9#>x}rbWhnM?d-Q7JCtv)XbE}*WNhrXO>4%NQR)s&hC#rl)D-$ZntTtIBsOvZ+|O<Q8OVS(P*T6P;4J;--;<irRcZ^9fG5Ae;mJD%s;=o|MSbri`=31mwC=y59<B0rJvuoSmrx*$*=%>D#7BiVFB*M=rc$tw_wGAtu4sGSbn7$C=!x2k15~;j^;fbb828UFh|SU^jxsoSng(WdSv8G&+{a0R|pU`V|kGyqAlNIBKw7nR^(%~t;7drA5;$J9XJ_mcLC9|_5sDnXv<dxE{lka#C}Z9ef4nU)~aR>oa67+5DYM8U>*w}s`=W~lRQQ1*Z~;xyNh6i(jYhxXd{5TEIU(<KC$gd95hK9P_sL=En&=>g+5d<k~i=ESyn^?^d|yfR3M{lHG1wX!)g5g(aZ2R0G;k6&+aH;Mgy-!2z^I=72W;hcbXj3F+6x+tz-^7A>VpIP2Hc*!*q@Dqq+4x4u0b*z^or^lFF{G{KMW%M&{_ZYnb~v<N8w006k=tt?;q}Ru*uO)_F`kG5byK+KQkQsdGQQRS!p?Ofuw=J0<2uJ8RgREfo_BaZ~qNIwC6ht>Cy~?@HiL!5bgLDWLo(CcVYsk1k0T$@y-*X<)OGZ8-?$kkX~@1n(C7P1F<7>Dv)F&C-h`PZ$_|po{UZI#ZaHwa^-<O6amRUF!ruzR{1}VtWaQEQVe;Ay?860+x_#+81L?+f~uUJ3+I6DL3SmryQ-5wdxxktl_kPF_Jc;nFF;}$*F%bs8DvTbHdKo3)~YXO(k$&*G-dQiBbTcns}x>PO!4BpZYY4mF~!ceiZ5`SQ&l7kyUrHLIef8SBXOoW2NXB-6{i+$dUNfF)2UvV2WWJ@+vhIFU#^QCVRCWH5j1jOT@TuZ=RU?Xx0=MpjQf(O@ZNCmzn})lQfr@2A0W63^040&JJFj%`<Hx_|Iv3TM|$)WQLmo#l%7xt-Q52ZAj$uNxuac+nKN1_8Ty1rS@Niu;^l8m=<gmGsXm%7oH_3cgsNN%z%5N-*QlVan$-ccxci&$|x5b35P?t<=a>;?LszjaRJN4WxgI6GCUiIt7LLF><|G&X?aGkghNEblfi9b&LUnMWVxnOy6E(mfKP|om|9CwB};Y1=GvzqEsV{_Ml+zo9!L(=xr9lQyaBv#S`HyOQdo7&&=k%WTVKCC<gf^^qDFSWCkJ%vtKcA^HG`jJQU)b&FUtuQ9K88fk}aa@!j^Y_bkfE?Phdp6T*$?i$Q*`X3GhAzAcr9ja@zQGq$)y2GAE-ug~WUAfeuI$GS*8;E6dIfw1b6|cB2r<Zn-ABS=Qe5r22%L`sS$uB&E<FaED0<m$TKoxEhGdtmJiTe1eEfmY4_3s0QpMDXoC6_{JnM7mtoCG{*A5rEseCQ4ENKu{W0ucjd>gn>MkFEgMhele-5QNxfh0XdkeWx%93|3ENrKWknn`zMz%XF}fB}Mhp-C^J14aaqR*Mbpj|Z?sw^iOS(b@&9a3CT2IjsrPxL_afm{N;Kj;fYJcO%*^yNu9*bOB4*hlDQc-HDa-F;QYkHs1uZFE08uA02DiN5iDIe0IrNDiz84>(^$SpNo=R$&o1exi6D5panV<Z@}`*PZzn*_T#J~#tV8aMxYT~{gE-AgEA#^Kb+2#d*xNK#{Jlo=8dX=9W%#UVczs$aj^$sEx=7O*lZN-Y_JRnbvntP>_!VBmqWqVerhg(^ky7)GC;e<i5H8_5Pbsf+s?gG8)>9WAF8DU>a1(Y1ht=zK9(SDeIUh5JH92Bpl#%A6s8EUove<_uxix;Bk8e3{X&6cwAQ_sF8J%u8p!mdg@bK2=;XEl4cL1C1C)>TZA%fQjGh)E{EbQtHo1*sS8=2|40IDJBZSh~J4WU9b{0M2WV&?s<l*+}}d1g^ri65&w?T-tsh$TCzg1CZX7QfKM>^2r(k0_PKuabCUD*loCNb>lLD0eJ{@T$*2&mYYl15T0V1#5ER_*y&JguQ!&6U+g26aRmzUY#MA%`*GcyW^Sj%`nX_7zG$`>GI>DKCm7r1O-$}Hz=hJ5q5>;;uPP-<kl9OUm@4?L^up}GPmm-nBv?!1&c|n`)an{?vWpId*z*Eqjglm+sCG5PC9>qpYp`U+}rn)ev&Z_dLenXTMXhs_K7~-FGP9hgCWiF1y>a7r}5!OJ*B&8~J77A1Ll6bX*sY?CD4YtPm^!Y-hD`MX(da*<96XxHuSY%ANLioV!zxfD&7Us<h*y2SIb#Fu<eX~||PF$IkifU(PYXH&8Z&vFX_X?fR+<`2mV`PGZ@?pYnRmv=DjjTn*Zv)@`vi02;U(a{vSqo^V4)n|SOA~3gg{VSTO;g}!wP8e<yqd+DdwuI-{y;gzs?1Qg-o&OjVjg>exnt$=Q7V|}WkXV=Mh-sT)U*((bG4;eAEZ9MdLG)BZ!!~OQkl8akIhyeVtvPlg)aCm@#$GclEx_*sIo%BzS+F>scMLv`ofTlt~XWSuXt-<(BUnhaCTXT)tWGB4oT?rm~|oW0>d7iRFx-Bsv{P(QQUP1s>VXe3I(88xSV=kYq*oii|y#&g%R*K=6u{3P~3q~(L=|(XroOH)#+sL>>M`-MDchFYA`i!^<XaWMIgTaT|_J$H|V4ROSCHzw`ow?_7P&4Qkk>dY*$Id<U=;t!ewcce-U`aAn;V@X~X-hl2zYHF>Y7RVFAErnG9q6C)T>g`Aw?<B0-o}Mml9LAACCR*a*m@LKTlv@=3s=WC1kHz7t)%)Reh)IF|VdCHX#;((NKffAeJUq-mgyI)tfp>uZ+@+aqzcw6Y9h#duk&>{XxApl1ncz04bZpr!VLzf{QDUR*Zx3&jgiQ+m``+-$|e=2-c)g=ItHzzIQ8OJq$%3`F5X!ShoTCbK`{GoKtegIlh#ypzL+@&f8Ym5Y+|t)+D&Lc$${Vbqfgsl=5n(MU|2ROWC@KiVrm+?o<r#d!TRuv+bo7UySlSOU3_vwxU2?Xq8JLN21Dq}uR|m-<4ytfxObm%ZHo%L3w*4!?as#F02^$GYk~E^jE0ekuV7nt1!I#^P(V`7u%Xx|1*_9-sNqdcgcRL3+KcK^H63kI$#A7>xTU^V^C|4U%;1jO7FOKMlPYna*02UJrSr8=GFUg#bK@Y*%wrl*08=BwiJ4M77A|sE|T51}`{VIFhMx9N{@roRBFEbi<y4Y_js7l?B8qLlUPdDYoHACn+!h)r2JOPbI)FnXz_Eq@bLup<>YDpe*Q4Dyo)Du85scShyMr)}rK^rou2C1IEaf<oY#&e7eX$JNP851=-Lzx;|o@h)k&qyyc3Gg=wUet07u$$K+l|{@&{AId_2A{8cFifIKU649G<^f>J=^aJu|<Cpn_x9l~2n|B?sg3LH+^Va)z6IM^8V@6W>?FL9UIso(&X1Nmy?F3z^TeJc2_srei^Bw5GclAK$x3Km%MhH0o>WYkOEShn!$pu6H`AGS~To_G@J;2G1{@iaQARto9~i91{t5=P=Kp(X-XZnBpTE*7ak|AErG$3!&=OrVMZ1k4o%atw)U8fP>+&O~a68ks_m>!~bw-Ec@21{H?pVFYj(B@eV)aq^$@4qkW7SrXNiimhY^@R(V<s>a+URY9bftvIaKR7oLgjohK7YJ{th?yV6ANIhQ7{RD<(VphR(F_no+e3d$MS!bK4Wjq&Fk6@#8cC8*OWEk^4u6n0Q;)9UxMQn?_=~vd6ONlgA7ka2^9s7vL2>=y?R<5D_2GA$sTR`mF@nEmzDz0Km_Ukv4gR}g0B>G8h8c}mi!1RVB+*sg@5x}J-AB$NxvYNuV{@?r6=1-yRzftQH3|3OGQgI5Y_p-7a?N?_hfJ}#h`dcYLo76rXSRw#@iqNalPL>2Arzi4lsgwZoGVsV6lOW!<Rt}BGDiJGh4yEQRRS9rbR$?9J6EXd4`F5q+1-y=elpaLurK_;kwUI+3E{Fr=x~65qj<A=JT07lN&q6&$W)Q(t3+Y)9EI9A3w!n8bPFYdsFD6<Y3mZ{^L!n-!DSFV+uT^~-De6IUe`vl5v@L5H84CE*y5?GGScZBJR^ab(%G;BlroePmKN#LYhbKe3(j-%yc&74>(3ql7&@+Sed#Zs{`!uv>$+xhTSltU+zmoSA!NSktZ}g#+GrxUBGOacecJPLkTv6jIrv2=%m~W$62C|7bF<NC>T?_}qGRm5a6hQY=Ml1phK*<g_JYd6dmT5gD;>*%lR+g%1oqd*dI1Di7=hv;VFe}9}<+(yey0JvjM7~0N0K-~f0Gl8<!YYj?pquMm2%D3vVpfA*l&91nNVAh)_!`TlFpKOoEfjX;)H4li%KI8m-m=CNkl2wb_k-J4awo6))*&T*sV1P4t0(q?EI3*>Mcq#H88S$wb8XSdlrrWu_s~~aQVwY;<1IR_Bk+d~d-W9SNpRdK<V>}uiSOJ9=Pb{~BDyrRsxB>7TiC9^g`qhhTB2fJ7O4+Bw9@#BnU7>**gZFds+?pFuWjzo@us2!j#miT(!vwg={Vq)98YYeB~&qqjAV<<)Q%}oktVKDqtK~PEtvsIM|Ga1Rz*syg_Cx>y!0*x@xv}&MNr(56|4E)E7J^C#lc3OUalrJ_y%yqGJGJ#nhc-N&}L@v7o|}QDd*Z<O*dCf_o~&V?KE69of9=a#}ZiMhhBr3;FgjYxt*@@v9utVU5M7v5$~?if>fCaPbPBZG|ov)6b5j^I5?D~b!2T-)L|G_#1PFWpGjk<`he!8aZyP=iMm6n3$1%NR~6*k$pxg%OO##x))R1uCcwg0(8M`L&{18qS2c);sl`f525-v})V=KY#3<^{At0ViRtQgAJQbMDToWSN4ivRS$5<g93Rw5*0Z5q?!QmS2Yt^~Bv>>lc>s(X<W+a+o{?J@fHP2E@GE&i}=sqw6rcR9_5$uc2!j}E=97|g{QyPaQit@&DH-FYx9T-dxZ>a6uuz+q-wrFR*s1D{xifAqaO%Z_T$@hCD_C*v@V>HN+quVlBL#V4@RP^z)xKi`9P8ejN{J^G^a$!`v6~b1l<7s;xU`!+fM8t*0)df?MC}l-2qwYmdeK3>}->u{26gTTAiLK}&!NuaItt#-Do;s@KnlW|U);C!vvca+<Od$%nFcKBvy`#dKiQcZf?h4swECndqw?J}f&5JC9(Sg8);;P6hHY}-8u~g4xf`VQmxI$uElsIhgs7UHI%eAyw#JnR=z6>Y##>kr7c%o!kA!nk+Rhi98VKzxtB^O;|^b&o(D+h};n^q}2xezDVwvMjR5J$C@47)JOpz+C7bFDKd<5Z+!21GDPG`u0%>C7tJ6{pb<8J{LXViBpsWvCF4lK4-bh+iU0bzLeNC6oZkE5_IPs?lET(-<?!R#L5kAp(ro&SvvUJS!i<l}@@8t-7ImF@)+o3AA&s{#)AL8>7D$PW3}Yjcl7@D{oAD^Idwn`P#VCNQff-SD^ZiP#0@qynmdUY2#^P2l5d)Q7p``JULG+RY-SWv(r+>DmB@@ZC=<B<m$f$M=Y&Pj&2~TUni5mBvJ%rfvF0?3Cr6C5^5>8`pTzt6e_tiCWCkYajb$=6=`lJfo!des8CGS^7vMR$Yb=YbVyy=(&Z@1Sb&aTDq+Gobg<i1A8RaOxuo(_QlWT1oWZzbu40T|fX`P<zv^d>W$NuzUrHz17%87sK{v7DJ!zd)VPtR?s3vnpNoHaF7o`qeDRKR#rmMiA(U}O{oVDc8e}uw!$5k>?m`yvEo-~$42c#RUXG&GF8o+Y6pdht-+n;X-3K(&19r!+mn#O0M%t}qmj;_#9o$vGE_xRAOp0Cfe((&X<YZo~c{VS9bE_U%{C}ln#5GMo2Yn#j3^3tZcp#dc^&c0+iY*n!GaxClZQenL<z9)7Y=;cLM`}<jMoJw}&3YH0R$>qBpschxZC~wEBWBIihZ)3|?YC`LZ=gSF8DPX8qY`2wBZcBc!1erMuMW*U&Bp~Hf9kBvjvux$E51bCcM`w(~B09@(O$ONqI#uw%9&D_FWvL2J&aPucFGY5pN&@LoA&PhpOF-1g=a~>d!+F-JxK3e<F?1ed7b}^B)WNhrje{5FQ@t{fp@cGNn=VH6l<s1j3js1BJiAo663tqWqd2Ck*MLr0Bs9~x1hYyLzr%yK5Aj=;6!9}^YYh7*kC>^p7YT&vifnt7(2YcyuaI^?5c#3kj83nk8QEgRQU>jf>)=Y}-7PD;JGIUTRh6aQS#M$18e5V}(YMG~yuK&6o~?amt=cl6o0IbrUKfEm)oNNN7?C|Hm>P|IMQSj;!I!Id`?9_elwPYUH)5d)@RV*V;{cvKdNI;lVBLMQaOcVEj`{*58v$a&Q+@pvROWP?qqqFR&6Ae`%<7F+mF5x+E0bua)F~Bf11Kp{2KZK?K$1G7*=k86`dqZDv)ZU^xk_T$(&!OPruA)2m3vmug~p8yrxa<wYd59FuCx{&^DR>9ECcq$`~p2KkZ~UcounfyJF5Oj)yY*!hjg8p<v25twL-JYM^37%$thP{Jw5b%Q)}>|oH7PtnIdmNt@@%Cu4(KQv~8y?*Cj>yRAgl!Tq$)+Rt;^n6q^^Xt#NU^s39;gM95EQN)*?*pv1=pU1}k_O%)mS=1D~{xDnb}nu?%W0Vu>nEKp7mMQ7C$(wq~CZbntLd>wnE{fr{GR*J=L!M2=hSY{$Gy^|qVchw;B8!_%Wu3t7FqLstE4ulB4o2ry8rR_v@Dt*~A1w?LZm7b6fCLk)zXzDFHxhd3~R7<@T*j|UBjAIeL#Jssq`SYkvDtjxTk@Wg^Eh&rPA1ql=EnWaOU#i4n5wN^<08SWHUA+R%U-eP1KqJB5;K?Yb39DVXAd!?lvQ^ep1Hp_1U8BiV9EvVlRbG-SO+6z=vdD8R&l_2s@={B5krX-fQt8x^>YOJ@Moey{u&SsQsLtL^Wm$$<L~1Haaa)PnW7Sw~yG)tZbx`+7$WF2)TdZ@m6*YLC2()0^DFP=>`y-TjI5G2k^~jzdby+9bkaR*OyHC=wq)l7b<XLrXSqk5@dsV9|Lg+Z%b*i5ycp*=4CqBoHD>fJa-$97Ovok2e3QKb{*C|LCeM`jqC*#G^DSJzup2t~Y!-;j23mETkmWruRw5J`rj>s=dZ|7S%nTygGDX}m1Hy-&m7Rjrls2ei<OkdZ>j+d-P?Eb+J<aF0<msGSazq1t7mz&0HdPjZ;OV^yHF2FC7It+{av5G=mfo{-#Nb@@ZfsGYR(PPc*LsigCrmz**B}L9yi7eMgrmN8xbpBYTw5}F7$U$VFr2^)dhcR`*?O5oaVVR4bV<xTmQ=9^g+@^*GYj6t6lNI#-EFfPKd`S}qZw-!2nj@B`lPP&FtRL55<s|(OGng-`_HAYx4ph@uOC4xPza8UWl`?4<S8_sMAmVqzK-9t#Rcl;5=@G$f9joOjKzEpur#a9(d4=-vpihxD^ulDVGw4}Khg2a?>AZ1tpfZ6y(=lx|+$QLSUNpD7=;1VJl^vA(s#o#p!pZIG7ICvv8@-vOq+BO-A{B-p>Bx!Z2&b1)qFr}Zo1WgdvV`sV98mHmRm_O@?_hXQU&Z27aX5*LOo{5*V(Ew3d&9RmSpPuKjW6{`hmx*??(9b8467wKUPkaPxImT&ZoBvnv9*JBc7d1VX%ye2j2oTs2OFdyQmFtM&2&le6X>dn-VsA8E#)3d`HcwJx}{l}oV{5$vahTI-xSfo!VoDe-<BXXB?e8eK;4jPer<ZE8<^!8Q|z9|LoN#gSJ0CK9au5Z({?$NEkov}KjAAO1dH~O$PhN_@hwWwDK+e9*2}czGn#=nC(EZw!eCw=K*r`g;qQDOEuG?}T8fd({}ZFlrfsOzhM~z|(!u2cS=WZ;1he1?ZkP;eD`06gl(6H0-~vGcsW9EV5{uPDt=NFBc<1cV+{n02iGIO#n&^sAahXJ?UBSfNQk)8~L_{L}JZ=uNjW|nG5Q!2r8JHL!q=n`SWGk>H2xqdX&Ir$x_~f^C1zA3su!ILpBJM}X7p$e6jngM%x*K^hEVWw7rh5B21wmUf-=?OM<SnzKB1*Ab))L$E87MQPjzBvJN6jGZXKXF|GD#!*S`_N9AssTW39M;mkWxfJ0F^Eb71M52uOe$|NL2w9h||@{m?K=vALW(#M5P!`g3&gVCbN(tg&F>lgr1H1bep(@a$c=hEZL@K#HDME9ZwrVw#)~qU0u}GrrKRCV}qv!6cf^QmGMmFsZwcJrH6~kR#0)oYEbT<>jgRK2J}?kc)b@ZXu$je3xB63Fn8+R3b=xssIf(AMRr(;6C-&mYAKj+&B#s?C*w_HHIH3K8)L7C1ysk3Um}nu6#$O0c)yL9yM&3xh_Ep$z6J}k&FZ{$PV(O2ZeDaiG-~My?SGj6tvAlc-qrJ=e@e%;XUtqupZl7Y%A2~$sQyVyyXaFTN|>1Z_Cs!0o$f(V4Ivt@q_!l*EYsU6EVrk;JQ-_B7)^BMvsbe#C5b;}?ABb7huSTfA|j`;rv_(kl!$Vfy6!_d^zc|0Q%;k*p!&PP1s4!om3pKCnTy;}?2aAWTRi0CwUr}<JdTg7(b<i269R3=z?ks>3FS@Xl@$lJeUnsWt+%H{o01f+>FOy6M<r6FeqB<~Q+oI*MS4!#SDljA-`BX6<h5@eAKo9n_2rw%2i{lkv*)i^y12oi7xa_bUDtME_hI+r**9r?5VY+uWY`$NTLb#(?@#{+fyYZt')).decode('utf-8'))
_ACTIONS_6C12S_4Q_FIRST_YARN = json.loads(zlib.decompress(base64.b85decode('c-rk<%Wfn|a{L#bd0;(QBz5C-*J>Ke88%3^3ade3Fo0GNAgm4}-Gu#j^^*0-%CImu^N3`#N4yn^#msnzyScgfFaLY?@4x;2x4-^=_D{c@{qW_}-N#=)-#$Kld03xq&(HqjxBvRL|Ni=yuOI*R+wcGR*Z=wY`IoaFKRy3d`|!h;zx;ap^QWI~@6OK8KHP84&gaF~k3X*0p9g<<T(3WV{d)7``u6GU{A%>|PwTt;pU=)`ho66bxc~U&!_)CUR@?30&xalR{OQA=zkEKvX*THFFK3(e<I{6nf4+Zs`tkYG;j7Vy(}8$g-`ySGx){H8|G2@cKtqPFJ$@Qb1!}<Pb=BE}Jv_AJc}`|0eck<vyzBGb?T2-3JW+r4{{Y@LYBzc7?q7!ES+wK%yPuDX;iRv-nX3FO9O3ot`2EM_ar?A>7%!sncc-fdF5UTf5k202884!8asKHaJLBY=QSaDPmV<LTz@t$*_V2^(ZfWj+^s+MtUAN})I9%mR_oFcURXAN>|DnkNJE2&?<So0g2V*uEj$+2j-{>>88+ST%C(j-4yyFm-(^OfPGvROpo1uEN^0Vcn3);w{LnofReM|MRl)s7R5e(t(gaLCD&6_@mhj$!4d_8*~(Fbqfj^p0);N36jr1yP3o$xLl*#Ga~O<kWGe)tBD9o;I6iZvM=rp5)*=c(hf)!DwU-h#0`LVjA95q(<l;r{M!{o(1?Kdm30KHYu#*V8kh)8M6FVl0vLJ0_Zg{jEJ{PjwF+9FftFD_8mD*02EI^!hjEcihKi-n$L$zebw`n0JNwI55J&!p-;@z!-sh0{3dSv@J84_hH!EsE^?Q0>|DkNSUhwKSd8@V}U+}4`d#JXg@aiqxB{y9jN-CO17`Efv9gD&p+{W+FV}+cnTi}y=B9B0LK0Ck)<&hZ~hWEA+}}QKI?IzsY-COS2nEQpVt3r^1Tmis3iulXH7-{0+K~jgI#QGR~$ogDz|fJ9VD*7$Pj3R>ZFUIi-CY}#_FY!yc-#~emt(*Mg_dgc{DW^z*}nbAKnO>4UsZW$nbEhEq*iwr~#a20e}SOq9fAffQGBI>&ZXH(*8Ke+52PPA8TS#b?e2B)q`MqB`P0ST9=tKGvkY!;7HQtGr*9x=wW1cWegM#QgYf)LgKAnD7(`uWAo$f!@txz)(RL6x}&@LVh9=y)uAuRAsUWF3qPP7oHBrTU;;FuAbijd9ea7J>C6Co<S;11k&3Yl0FIn2yW<+&56UrIDG&PbiRe-pzHe+_S<&G=!Ghjg;0>AZaQWbp<MeJIyg#-T;kk5dq|4_$e?sHC)<K`D5w$aw9-kg=H$SW&9{vJ=bSZAcF0pFEmA6|^NE~B2ZAq8l(ndd$eIrVbpM~RQ7=~l`svS}?q8Kdbw3*6i8rmB}h|0r^crdGJeH=a<F6sDj8VtL?V+Y$1b5T1+9-I7)@dzYWL9O4`*DuY?+IZ;GOG7ge&+^_P{4;?%?L01n^G(K%dyg}HtEkn=wrLtHmBlu3d{WHd<W*lc;=}!uXOf`vRq>Ch`yJscnR|r+5QAHAbANyLoTdVesNElTGxYU<{3t{MkG{ASu1nL0&f%mMnKz7_(1|TF9@N?eARDp!$&rUV2b}>!2W0*9zU6zzz)0dt=CYMgp{4+;?s&8@jmo%h2wX{EYVj!zKduvDMbJcmVje$bz&Zr_4fsdEVr<?D#t4*ij!v}k*^t=_Y^>2Ib7a8zQzE<L*mI6Y1zd}fl{%F%w94e5+Cej5MJ;jIY#AF@Fh|t3xTc{LMK;rMxfGP0LvOsp0A+Z(k+B@FvYZ(Z0t(H^%GZ&(#$f{W1OeW8oc4R3&WM)NbxAH_L{Ayzyn2=*$^)kBou~E6n8GZcm_sxQwx={ERM^qF%a3t9i#=spr{#OgV?&&awotoeZsXRmdtNsdtJiI%A;zr?Heq=Lkb57rX!N&ahAXoP!Vf725%jm(sbq)A9A~=e8+By5hlifj7;afA!y%cN^x=tyS)+3}cInQG7p*r4N96=10*c3{7Cra2h8%&#>C2g5iS<s<icmkGA<mr4Z&5QS>n=(=Pw$2}BQr;uX2|<1Zz%XP%L7RyPf+9N@W&R4UXDd~*vCWMx8?}!e=CGtEi;?bM6ubhe>i3mrGn-jq6iMf!#wWq>z_W|{du>*YF<+L%Q%&;1q|P9-<S8z=JBpvkX?C&A%Y_Q5=}5zSvH2iJsy2t2|pLCL$I#}?HF%&cu^%GvvW$dCvYwwxtl|)r@%x?il^tV<;L<blf#1~riGpdIle+P5$v?k%`C|o1C6l23Z<>Y$7ma_4(1&gq-=Kqg|qSj$uMe3ZUrud2&2?pf|w}lfzGAP%)C9vIn2QwV9dZgCO%}7yBnOcE{!AGpiTu(;ucDK;4q+VQ2LP*jG#BG<uP1ok~E$%V$hhdFSR0aioru%h(KYkN6j!4zbsx5a@#C_UHM={=6ZYD-;6W0Qh4CG5TWmRFKhQX`JJW*HHAwKERe_}C+u4<s;N8Zah$F&XsG?{LJ6t^026<(p((qyR<2)5)+BT4%T>(17d^(S6MA%A;};It60aq26#`F(NDj3{j|pjQS;Zj)qSf%mJRO8IyHJT;VJ+Sgx1ilN+~|^xiM6;zr&;+2kDpc^S>oGxh6pf?8h{Fo1x1k?$*s*~JDa{V!$*<q3E0PEB_-Wz0K6CWSw#wF3~Uesy8&G(7cO&QB`cNLt1RM;K-8H*-(|w%MtrEzex-0#&ZJK^Od3y?dY)-OFE>DmH@-%*@+8l0j$F$y0#j~k-!8XF-a@P1=wLO5`@i7^eaq-U+J}y*Io~eiPKYry_sVkAMB1JVL0Hjuxs}Wa%*3Uxwr%pnN!JTlW0O!u!8&OZjP$(8HUcQ%yRwB4ME=l2I!agLS24J%nuF9_N2kPVGzu$CnJdAqevUKNMH1t-QzV5+p<LYR+QJMm;G3<!or6qPw#HB-n5?!6Ag|B27H@_f0u2P)ENt!U!of$#!NQgW$UZrK1;hBbt=DC&qh2iHYHLt>DMrFqFzc=w;y^uH8Mp<R7dCldUN~BjZ8}LBLE?04A(nd}&<$%U+RN+Yzq7p~*(kh~G)LBtK$XGlxKD9O%9+q#c8&qBKpPa4LQA@snaay;CUcHrtclb^I39qyEq8U*n6y=biO5!iU~;wOV$1_svt3lBgP~PoC&t0SuG}h+`6@{7089+E7%m2d{s&7=uH&PjH~|9qv=?<kL(i)-6OF&isn`$0#qe-ElCx>m-xr~iPU+Y4MK<MugEBf6b2=jPspuDR$zaR%o}7qrWcgEy`V{y_OXf1DdTYU9ED|c`f)7V3qfR8VESeKQyyuqo=&+}HeQ0IbsY2uovIx782vO4o#wiGtMH~wf2K>m%6@I<VphO|E=O&+q<nks82Jo*KKU<}{tQ({zOUh9xjYA3l64sDhD=}7pspiF=f87NkS!|5lR#!d>)=6Dd-aAiNj&UgdZmV-roF^i{H|sYIocnSM_zFq1JUj7~IxtY=qygqW(}c%z8;P#K%z$Tt(O(OIS$zg3x~()Av!$gP6EwV?v}32K4UtBYbW>54gD6?UTrKRzOAEzmWi)AP^d(`OP5rK`k%U6L$rufe-(l6utRdGb3x3ojBq~HO>3|6a-%KLv^g$4dw(*>2?B=qHkWPT<^n`6(fQKdfPX*urBqs<}7Fg79POh7!T@S~$o;;H$;4rW|ZamDEsY%5NNDFn_qE7m!M4fbX%%D0<Mpwk8^huiNGZeBgWLcv5=~Me#Pfyc$D<~|WS)m%8ie#pNQd|j=S4BqNNLMI#81=?ELnMLNl&FY^1~3W0lCh9OYDgqrVw=?hiQyE^T_qU}B=YjMy7<mgN)LnD6q1KXO>$ggUhEJ36`^5@nom-Nk2z4>|Dj^I3HlzGP|eR{@*a|8d=kBp_-9gFSrhimx_#iVRp+=IP?fEj_ECvFs6_24Ju9A-4z)Hpslr{X+A>%=^h0;clR>VdA^s^UEd~ah41T2mMPznto&>AYMInBwGN$s`qUJ7|X&o<V*4Gsn;Ibfl%)Xg+Mh`6D)zmCYt69YW1`8Y62JtF!X&a@b-%JJo)?)!=h<X5-A~G<0D3o+#>;W^^!^4Ey%Q`7DkwFm%Xtr!xVP;_hX>$lVIq|*3R+A(RNkemu<}+HEK_o-WTMC&kjnte7m(jHPz~!GTa#m(_kOEERI+k)91QxrW)+4PB>d$i{cJHH(QedKZkBCtyB2Fylf`Uu+TosD_8}uz8gGC3ORQB@H^jM=nReC<fY6U$nHI7!aS_=pbn@4iU<!Y|k)28A%#)uI;Wj=w}B^`cCae+)#11))txRaW{$D~)aBZg>S@mw}ZBep)SwqHrn9I;jnt-U57Dj7IlId7vCDAeJw$CH5cd_N0&rJji*N*U7~Rjo8_3;#4jj7juhRm&**9w33x)47=n5eWQH!)LI3FCoy6Zy3`F_FQ!t>@brl5=EuTDHAj2I%-4s^ViSQZ}XDH5t1Y8H;px9!l?P-4_(wchv(lilRPE5aV-kn<)q2}d8$yIG-F@^4T^~jr^qQtD7l=fx@LNRYyKNiUeUNIhD%1rox43LUy!CiXp*LhlN@y<a&;*UIJ4kt7pscgHB!noF$HcJrxBm@N{|Q&-aufL5;sa0znax+@S@seHTYn+MuH!nM#D4Lo{ub<y0Swg@e7?d)7jBkmdY8+KZNhInw%P~#z)byBuk2?Q`#l-Og1DWy%U!ct;Ro<&w&bFDj=O;M(Y|sBCA;Au``Do;~VpBf=G=j<M|Q;VISm02D@fSTLNRUM9BvyXlU27>zV6SMd!3mK4m*zUv@02oi4_~=-Sl1Vd89IEQm!SQXyBu^)3nhl9#T@V=4ffxZfEWuT1m+3tW$fOHOJ+&X8rH5*{qq*bwt8W%)m))nMg|#UZr1;QnCWY;ztey1u2Ncf@zIge0#86G@l*;6?>Sxd@XbUNo0h%uS_FNb0C+K@L%dPl+B1us(0H1`nV<S_-9|G8mYWrGY8%IBr%Y5%{$n<ibr?KQ$atc(t8Rl8`{y+)A>)DsI>^lR~9o%1#%LFfn3YeO1qCT_l+a8W&3}w?yk|wf1msZBJI3g{ljb5)4ILzGZ2)D>&BQ@a#0rhA381%>Fw>x2SgG3;XYCa#$;bT1fIgq&80wI_{qOpCP~5<NzbYYn4RL5(4_B@xKb^Lv}+AErB#$U<3v+IpUXo^&`>8Fb=r(Xtmi!zPwtERt(o?Xcpj*CcJ@K+(;l%vY`r++JX89@}0TQpXJ36J#JJcF;+vVSV`ex2Qvi_0g8n<c_PL7&W8F}`frImu~cj)Ko5f`c(rgIgrY6$GcZRZ5s)`xZo%nxWDtxO(q>e83ZR@e$gRz=5PegyC*o17G>tnfDy}nEtY9Y%KF~3u`2v3YM}#!2;Z*7L$bVU=z8;}Hw0r_Xoj@d|9FPdt3Nk+okJ>>30&sAxD{l6|-1@o0L*I8<xXFO)as8chJ-T$m@`_<CG8U)&7F3Un^qERuitQB7L*A@yyaA=J!N5#LKaRP~9pDJqv-X7fZtiwry@qb%DNSNm@(CsA5-5Z)BC4g3uAKx}>JprW?S*K)4xOZmHL|J&glM4iwWwBln%tpOLu5x(1PO4_nwDCafF5%jiFN6uxu!~4G|U_1VZpOTt4G<$gVU>>ia~Uqev@Mnm&c$~UAKbvaZa)xXkKg$R<=r2P>G&ieKAT<W7v+K5eAofjo{7QU405xj+7RtIKY4fn=~Sh|BW;Lt#Zgw(4PVjwtH7}4J#~51gP?FHPly%dB^VAQiOe&@e;3hz6YcM$wL8U(;b}$S}2P0+Y-bHfkxXZ_K14Me#ItdF!5&X*XJNH2!GEkbS&N*C0qLC)eD6$R28^TXqD%Z<|Ioi1F8jDm6f9-N~%A+d=>YkUCLmH`pjy2h$q!At9a1tyJbhbGWx?bP2L9dQv)3$BY-OgB%@Sns!twQiMqw$x<+S5B*!$D3he_2DTzJ+@d~5PYUxV<*1mQ!dO$%1pnHxsMuz3mS$5&7tri1L&BswxNmXAhJ3lYQc1hLwi&PN@Bh$=Dos;*eI2PC2L|q7Ut<Y#aPk+z&yk3S-*@aO1;v^ljWKBdsfFHJ=&9@m`Rg|El5Gs#p^m7{7#$mOlrN7yR0Pc$tkEh;{CM_sdZcR?el~E=MA@q<=pchpk36Oml*#sN~VK7lYPs}&4xd<z9cR)*2L->il?7(-@w116dc8Pto+BJIKO3b3^cP#CcK_WcQC(oO>c7So9O;q;h<EMXS5~(p{WA!E{t%-dcrkBeAEUFo6ck3#jZlxMEJgQ>Jw)#oa*ZKZwt+lc9hKeDb*X2gbSM<T^3V!->rw@>>>usJJrS>~1wo`rYY*s<%Zr*XX&Lv1F9`p(tI}vOU@wQRI9;!%kIZe$GOc!-J<-sX>x`(31kr3t)njX~7$dq_!tUW+VUAC$0<o~YTJ(t^F*;kqs4v7S|?{S@ybk!X}BL1Q#0Ew})kyu(wWfVhzhi@UmSL!O@$RvjtPfGhLH7N^YVNs|`%N%3>sUkbeOf|{~g#}(VHxg_3wx+sL20~BQ)OkY{9>V>>!6-!*L)YW-&oZS8l&ztt$nZ`j!sSevC{ZvyE-VWs!p~R{O1XM^ZfXe*Y~;zqzi{NNj#==OK^CV1Dl{?=X<IlhE;A=Y@g;0e_khLJSON0|<Q+p~_&N$L#o{(pE!r!>O84`0({>r3WBg#<u*5m9{#cv1%XzX?wR+5w=tvs4Z3+D_rY4E)(5^XE1Sb_3nuvUMRRlIx-)rXK>i}MIrPsQqz;qNdFU!r!H`FpdnqaP22c=cYI91T*6`-$RQR$Mv)pgj_X_Qx<nX^}cV>-;5f=jridl^V9gUIdaQy$P2x%m|!O!5)+PFyy@S{yN~QsW7J)CU=|fGvQhR5RH`ePLBUf@3R-#`?fw5db<duC&O^SWn?;!X<iQSgW3L>i2^nKUmjEUpF*B5}65IdqQ(`H7Hehgnt7v083Ful96-;Pw8=i1ICRv;Fi9*pUqjW5w2Sv54V<dCzY|)E;6M60nM0`70p|8%&*ee04ECvzzBf?SQRU`U<XZ6HP0bh;z27i=a(i}5Y~R6v>Zy&@v5+g)|U)C9t25HcP;yyAco3*rlhlS%HSp6Mc_=<&bLZi>&k_dgIHT!Z5Y%|0X5Z7sZ|9gOCvmBX?@SA)CO4|RQ-yU7!#VEaMuQCP7!Rzjl|!I;777lDr1U4TTReI6qpiC*<=ph*DhdXf`+*SM=g0y7v*kaTlKKD*}R3cBX;7m_1T5o1rqy+HgiHK-Qg<=JvwgyWpzD!BEJ^OQ?qj~6*N+Uc!Zc&A+QhdsB6hE>Nks^cEq)lBxs1|>#}Ba8>Xgm?&JwV|BrL7<jddpNm8C}MnaBa&h^aIHXehpp(=t`#RAmB0W4_PkVCkLS)`@C0YVcXE*DBy;LE8#Yra}jdCbqVxLss<;{S?4Cp$|YOyZ4`^sU11GNQzeo>X^MDPTJy$H6TLR&toVn<NV9mIoDcBCBg1A(Ua+^1fy1ZhF*lizZl$*+t2(MPAx!8)6i-BELB6^*mdpf=8G%opVjY42{E0;4c)v?O0JV6kNuRv{o0hK3)p#H=j|eL94WfCEQw*7Bt+3uIOD!6szh#&#vE-COZ{ytDD8IO(M%fLu&Dx&AKa_%uv|R=}&R^Wr|eDY-S*x038bJlKx2f`D<F_=X97l2bh@K6OnE3w*Uc*CD8j+nTtFdmkTuwjgZoag8a~OS=31iJ=EO@7OD#ZQaWLknBzBJT13aqs-GHo3Zi2Pp@)8_$U>q}7rRR}he=&VRv~h*g6n>uk@sH5TE=T2A@3N}PJ|~E(?G0Y=!{{&4%1p%by61_9z9}WALSPqVC99A<pLr8fHoy1EhqesD|hv9Y7yvA4T+-(J$p|ph2O7)9ln1-#Z(|ZZO!E?c~f8az{CAhx+WWjjC0;E!PdC2P%L3Cn^<k|-LB8OF*QY`SSW2MxK22q0k&D?Kqa->8YKEO%qgC1dhNCqnQQ?qOaHRm%WMc@K&yTnWi`S8RI|vB02gKq<5_f9L@6<>hO;*SrRec8KO{+|v1<c3Jz>V3fNtM;5y%oioD^S+NYoo4S^hOd$-??i2JjS?xnl$&F`la7ZeH#wC(K!*U{pq?5}Ht!(`GUboiKsn2v}5qJGRUhE%U8qFn~~<HPTn*JTDjYG6w`I$_#PBMw6<UcgJT?pxUy;ztD?ns)Q^r86uwRi#GgG%TH7ewKf>FYQ~D@P6E%2FymCoh86%})wanMowifb<0@PMMD(3jRL}4qS9}HR@`5fhT5kc-Cn%uJ(h$_iy|LzY-X@5~xdPEz4(m3xxu%_Z7NjE3Z1dW-HP7Z+=`u30mnqFSy4B9Z6lp=xWh%-Z^I6y-Q+ACCWU32t(cO$H?M4w1XRDFG@O>tV#cANnF}*BgIM8%oo02%QW=|-TVrGT&Av&yZED_&+OV)UM`fhZYuj(@0tQ*$rtnFr`t_?|$l>~gM%bu!UrloG`YW*qihv&c0pb-yEF><a?Mz}F=&}=5ZUXMJe!YZkEv`)E>;LfK;aBDkM$2P08IeSZ7NDv}?6B2to0KYcS=xPre@i7wu6yYVK62p9(t^FD~Lut%22z&}Fu*yZ>CQ8E^S%5OTQm%Td2{PChT)8NtzD4t@uaGvls}av-mmB4V3Ca9%;fKzbnl23xQMQ3|rPsOOt9^3VmL<k=J&Bk#LN(B=5^MGrC0+x;7Gs4>8^7>ynw67{$S-uE2rZhQ*5!CzK&Ll3V1U<iF9{<w-B&zzy*kf*yhc{8mQ!CSyQliqYkPxYO%Ixkr$;@F@)I7YllA@>dtIAA319C6>Fi=1soT<9$6~d|@az(})xDutk(Z3CG1Lp_R@36mD>94@_|((V5DFX)LpwDmE#cj&i;PLnQo^+oQ*nZPGB#`22!5qetqi)l{Z{6EnXblK&Jqisf}N<&Wd>_rY8y0Mr30^_OrG<~en_DPL7Ll{-dP6>HN%YI1*_6EZ5FRic0D=i6~Dd%RC@6Sq0(38yEYWzb)@gpkf<TbWysYW?krSv_i93hYg`S@p~^K^;Y}=<?y3EeShX!7-@;JsB>s3VDSEKhuX@F6sX-Soek_i$US+ov?R29R*(CKNnky76+aME90ykB{rZ%1Cs*G{J1Y5L4QzGQ{sJ*%BO*R7s5+ox%VuRCNo2bzur9LIj(qx>^sC!gpeoc*-D8x!y8_*$tr{tPqbh8BqV-y|vQt?@F^T|RfffuP13}CKln*`#j4G1!sqgtVssIFfMvVB>SSI%*i#!?u$bR)`=h9N_F6dFS=Y(WRf!(2&`^R`|~l9XC=1@c?~|FZ6RALLReWJ$`o`zRo-i!0i;KDOzxWHn%jun-v1#{&=q@bkH%^B#z<BHqcw@a6ND(b{^*JgD;uKr>e9Qfz*)r)L*f<Z>c5$zm$F^Q3<0r5xVceYIB@`F~K$rV{{iOd=RHaZ&veEKT^kYGf(J9bHzZi=3RL+XVxeFslL^b7}ODSzGY^5ydbnqak39GKJD${<E}KCCjrZEx%S)%d_^K>Obg;5>p_p9!PAxa_z)|r$CF-A`lI?XF3SKVTztI#u``mwOM?<k`Tdx8%_<geiCH8UGuM+OmPwuU@jvo=`Bk31r+s#tA&>+rDEmhv&gezf5y`#RLAzN4zM(VlPOhOmCeqs9utJe%LA?in)gLq<Z8%0!#ThM;zX42<e==HI?-_IfKC|$c1tpBTuHQ^T=S^bXz?MG<n!W?T^5^2pu!EWN=q`Q{P<6M@AT!I>7uJNZaZ9CY6<yT;d!O}?aMLKc?VtOF_euYNlx}vC-U(kk57{zDNi&$oyXd&Dry$F`83w3R)1w3repfO2vh!=N-ssBS#7e2hG$CgoO1tdYa@`&-w2|JXf<}3zFsNXvz1;z`j4cgSq9*$49xkPVIc-80_z&w7@BDWY2d81sJvW9E?z(<jP>|Jju($ni)STF6K7x)Y?i}i0%xWP_ep``Bn1+t81Up$;aFT|@<d5ACeC=x@OrEs5R^#^d74%q@tmq8naeh?qF73LF>Jlkoi7`ZA<U4hB3g?n%O2^H(qCRU*#gh;$s5k7)LR22mx`7u1SUm2t+my*#G+r-X`?}{f}h6rfiId!hBvswMV4oqdRZA^2a`Y+4Y8N3MMJdZ;42hOErBbfUD8$+ST})6L43s2a|Q{Q<O(ZaOzo|laXuHkZk2jB?88A%fhXG#L4vUV4LQjYWGv-BDjPs3R+cz0y()>B!XIV%qDVI)-I+ydKkgS9xYv|RxO~v*1A9ygjlu*4psSp`61UnoB8RGEmvUOL{JU!W4xjkrNk9uRJu%B($W;~DoY(RI0O&LC4Re+A@CGX{*Y2j}BsG~?YBuvn6=X$AnbqrywrjJ&fn7A~C1+bsC|S*<Fo0%B*1gvQmgdxyQAlg%vgn{LBWWGeh+q@QRDf1eP3YJ&4G>B_odS$0v?z4}7q-e+mDZq=q_v*-1xiHbH4?iwS5eYn5Vzv>h*GO(BUZu)REE&tO4y6yU&O4Yf84sakB?e?h;dV`=E;*fFh}<-qfI>g(Nu_)s0UODt7zWQLo5Dt_#p5aOQ7K8pV8E^(Mo)1Y!)nV`UcvC4~n<YvMz0SZ`FIN-e9Z7aWVGKm!-#A<7<@FudbW?*g)<)P%Cv(pA6RTMvmpzYmj*cO(>=m41{HF!ZCM67^@*-@?yZmW5y8`LZreCu@@Z6LPcyWW{?SW$%%Owfw<OW6U#J{fN#t;c{As$fwnMtUI!JAhL$dQ#jj+6hK~>TpX*jLg-U4@yC{NUC^d*CnWz?H4a@)*7p}mhpU(g=;2#u2QHf#|_i@-;gk6BQglhBNy~3(IF_e^&M-8C`PCotyeMS4aS7#+rqRIM7&(B<EcL!D=p|L;J2IPkQSG5n~IaZpY`;+Y=Ho`%>4*RV<i8qx)keSV>soTGA{||QnE?W')).decode('utf-8'))
_ACTIONS_6C12S_4Q_SECOND_YARN = json.loads(zlib.decompress(base64.b85decode('c-rk<U2j`ia{MoP)`Lk=5|uZN&D}9pGcsg*h0Q=143G^11e=FR-h%x1IFd+S-cwy&)#p(5IC{ILDc<vax~r?JfBEl|fBo(EfBgOTlYjc<<cH7iZ{Gd-;ripJ&v%=XhtrdP`|Use<v+jt&zHx4{Pz35|NXzdJpXd?<NL?|)gFHM{I_4Pe}4bd_07rY$=loelhbAM@y8!Gn-7!!__*1;`||PqkDKdHC#RRQkAK?S-2QxWy4ZdF!`<z>&u>5N|Kj4|;eSr29sBV9?O#5B*uQBp>Dw<S_nVKO9^3l!?cJvzAD?y~%^nU1;^XG#X8+c+`CGR?H+dCk$n>@Qr}<Q%2FzX;&K~UHt|gCivN-7L^S8*mKHOZt-9+Pw`m_B5@U~gI$y=ZQWICQrJ03s#dA}GA`uaRm!Pn9e-dxY$zh55LpEh^%MKu5HaP`2YyPPkgkGG%ai>O_kfBL_jaq!8kcWf%#!8sh@*(mM%_xAdEX>Pytv@<7Nx8`y`T<uG@qcHteI$dD@p~(R|p;^J?Eze^Q#%wYi&5X6*(P!*=-09FA{O)|`?T4_PreIwzgu@MNhVW?RXUjnsw2?)JPCj|tmg-|Ef0EB57{cch2Fy`5Z~7qa-m!c5a`t{i58lA-$Gzu=pT9{beeCbk2_Mpd?cYw`H1v1Vhp+Invs>jXuqKnk)VM&#{ObH{b++$|w_t9Mkgqmo#F!Smy}h~Fy#4g+pEh@&-rv0c=fg8$(BPF{Vl0vJJB~C5+gp3mo^TKC9Ff_VgRA`f!LR_o>Gf~S@4Szzx_6t}f1Nf7Fz*`kabkpng<J76fH4C11n$-I(zeWG-iK*#vp%K+2poIEAZ4x!e9C^1jRks2e~@_uqW#$6kH$?dI#BVTO17`Efv9hu&p+{W`dnWHcuIc`ddr6M0F3+nPqxNjzWH0=gxHpO`>dZ!O;v)My|7{Z`fKBVO}_Vm4Yg81?z&+R+Y0UBd<dg2X0Z5|Q}6B;AvMx*$gW!HkgV7bySGjbEdTBl+uqYTYX}jt-gPI?`?bs1pcidrShyV%LXnQsl(pY5o2cbMOooCzMi>1a^-Hl)f?g$qkwb>g!8?btz8~P~^=Dsy_7C{8I)F98)QKbSFod5%PUkj&5`^U2cQ+m^bLTXCrRX&pcuHRYGP8&(Ac%)bIqfG=^<GDoUGTx!{CIu$*QjITZhQkR5Tn>=sCIoR4$*WhdMF0%;IuKw9hsmDNa2IN>)6v<y+KDt)oxIxBbCD;0AD#+cKbED9h7~<Qy%pFFQThv`o4*Qu46EBjt0HYz#A$N=JtnMn$)Y=@cOg8AkledIX!=G{kYv*W9l3e9~X{k^=!m^{B(DH|HJ0)?r*@7DIrX0hr+i*8s>61+{79fG-B~^1T^XeK`86)G|b336ji-TV`QNUJRQr#np!7QtjR-|IH=OKK6VegD?R@?4QJcl$dgTr$*%)Lon79^d<2TCAnLdE@l!La79o0iYG@_I+TL=6@FsAzou8|~gh!*}y#}_vR+#L<!H&*5?V7WP!tp7@%Mu%b7%J#^Rh((+t7l+L<yv8A#pDvazrDSAOpAf0)$@NoPtce1@!d(;*4z8@xVOf~($T4zgN!0Eh_f;u>gZOG4c^09vDfl$B1BLQ#*!}u_7BKZ8f_?)ril3=T6|2suO%3&iyo%?E`98%Hu{+&WfFSZJeBdzO_U$uH4(t3^Kh)!M1(R<I8%p-1>L*A=zKff=;)iD7L{$lh8aESg91*S7C@e-&eRxRz$clRx5u)gF3fD%MJZwj%&!HG*{yP`3}&<1rkY5n(wty9^flvLcwh<2>;;*qK^wr;%&s~e$xwXlY=DA~+gm>PB8MB)vxH4H%;wEgw>|4Yy3=X4UQ7d1;06Ys?V?Tw5(wu1I?1+Xr1D*0iex({xu-pr1=~S1`Bcv}XZfx63WR^qX&lc6G9`e4G1G5g;$O6ZVK5bO8;f9M7%s*=W%f<Q*Z|f+6QXUh;jIyGJ0Ds)r{e#W$d>FK?L%qA+r>@BlDwQH3Io))JD(=ELEHbc&O0`&v}^27ijGnX@&ed5fZW;t*U~&dItsvz+ZOiamdNShUmo7Q|Fem~0{dD|9IwH?fFq*$Dg8{r#T)E)G+^-7hWP3I&0h{(D(G+_D*=9ug~NC6I<o6^mP1Lq>lImbx+Umx^a3Xgl8S&a7&#Zst*tOTIUZGqCv<4O;%Vx?o}SBW3xM?zyf0fUt+jgK)|1Q#Wh)5;jq3(K23kYN;gFqMMRQ7aQ7PeCT|AmsSpvW{Mn~(|?+top^I!sDA2Qjx62RalVJ@x$7CS{|TH7^=a{zCMIYF5AY1&D|RcHqiwVt@nFizG(4pq?S(<D~Y=ni;u3Yeu}Y64@H3@zFQU^8`F!6;_I_2)nnrz@|e8CUFN&{auls+H?&K575Fl2)+StBc<qGL^IQkhKiixr++xhrKr^TOa(Alsh9dayRQ<LnM!;kPZpvc!(1<K7(?|!)s&y@Qvw?86GmE&#Ag@S<HZG+3uwkum~Xeo+e{8P=cYg&vb8^aCp5CXHM}R;!%^}pG694e4#T57QnWKnps(tg&Lg12>|ikDnS7i<T+Qcne=buHwm!96V+^mS0J*mD<BAe;{1~XO5DoG=WTkJxMPVj292*3T5hEYIQSUNh-k?golZJ;#QEqF|B?%1s7KR%3|E2$5NGHH(e#Kh*GHuy5iu5vWD!`}vp(1+p=L~CHDcUc^SE?g7V%a2szbDn*w#a9xzIL{^t*inakeC_7N*)#$I+R?NBps|b~I^LZPbRe3YpEv85-WK`oVK-*GSSfxweJ*zV3?qimd_`>$lLX*M&7;cj{QdG5!4RAp0@g`AT$L3_|PCapK4y!0o;(uX*sYmAo#cumr&ai$`4Xbt?=qJuI%f=TVmgp++ykp9R7t=MRS!%Nhh!gE4!Tgh$1`cx~1}+%ucJR2hmUg?7#~9j@t1#ISp(fHZdzNrDHCYy(gNW!nMxcd;<;0Q}0f-SB%zjg!~!0?oZNZUl|mAaP8=7R*QX@<HdHveBe|Gf4rAQmS!l*C^7VcL2Q|?_$QeC9qYg2Ny9ra`9l$0MJqbP1W!&35v~orb94Pxh~l#J7(OpCS)xA=Jn;^N0a`6oZU%vJkmzcJN^gc+DGKb!@ew6fn?Ppt{1a7H?qys)~UH#G-Vif;mw1dLBz>K6jFtJEihqZ$)T0SyV4=@$tIvmy6w^YLc<&t<4kQzT@R6mi9#CCG|wWO<Y**SodL8g1SMOq)Eq0}(SuuLlp&YkfHp@$$X_<%B_r7R%d;vv!XcAy1u2PY3|mg|(J2sn^qyv$gB|NR{Q31%<XQtKPry$kKR?UCo{m&SUa0k_s~}2|%MpCs+Dg-&>Pf!JvQtx47}+-MhK$@@S!pd4USQb;)KoB(^}NuSyxgeIN$A58)5BBdY1RvKsc1u}lU<|hGJUR=;KNcTD9IgYX$)B+0Cz;PER=L|<OL#417nd<r-LmVPUz@dIH1LBrN<n8O??v%_U1T?s@=o;el!*BXRnfr?SySdd#k#v2sbN93{jew)<23|^C04MD)mXB!{qCo6XALnRCNbos7FgO3X4T`EHdMiO7{b6G0!xMv0{773D=L~p@L#v0$dEg=<L<X@~7+$I_n0uOHNl)YQ6e1;}->D)h6)3OL)r5t|Jc+>U^-)hz$bm0Ut>#ZvYT966<kMq2t3o0RMsF!9*8tIs@x&HP+qHtS7tFX(tTf%^MHXTiOG<%?wFlktCR_$s*ggV!J5zlQ9&h2}2JxA3JNMKJE+z<(NZ-U8RIasDamt3MLq+8oNDzs8Ho=X-<gfkABDz8esAaEKy5U6)@xqNzMkqS~$=ki*UAa@|uVrPvKEAwg^{6Nb=N~93muzM!Fq7N)V`oRHVe9JeOx2T@Vb?1ny8TOJ|&z<BPe1_*1?^=19j-OpXaqBo2F2s1J)7iTmT+KuJU)5H36eI<DR*YV4XV6TYE!<wH#alb3KymJve}x%Zl_`k1@sua~%J5?Y=bK?C5=vO}&=C&jW{!eJ$Mi5<g1qsxn(!uKXPQylQq-g3zrO-lc^zeon-3X8>*>i3wm4akj`Url0T1mN&uL=$FzbLatN3_CIhKF6f>8TwTyTA!`KPlz|yD@_j*k1|CLN_8-EMm#90zgm<s6BY2H6VqZe5=pX!?S*Q}PP<A}xeIEZ6bc*B{5=MV=p-A?z3C(er74E$xVD#Mu_T(sf^OF<8(?;U`}W7`VUUBZineT#jTzB8EA5I61><s2v^0}s&p5%u%1@_BvK+*qCZ|!`j5P{XcVK7_vW-*et_q|m0xRlfFAbdLFH887%AwkfsT(2Q9(2`>8Zt2uu6W^6)<UgVlh`EMHnDJZk!Zw<+#ydKwM&8&i~)6pa@EfQn5jjRDePV2Aozq75m(TQg1mrQrqP(1zkk)Z^$`NF`rbGL1-C3f=CkbmPEW}RD#G;8v89DuJKEI9=<ZJ;;wbwiy1IoP4KK`jF;ypyNA`QfZl&F<I0+1q^!deMeUImVW+@*-y&GLL*H+r7)dobBLaY>?+K!{<>*3VY>SHTX6529N<RZFcAymQF$`ph5?x|PV0QU*Yh;E7?jZ)KE1;l>QORsoIGT|zLkqv&JG~~eHk-YC>d29}LvP7I5T-2Nu7_MhNe&xk9X@sT};N7QUXo~-%RjW}#(F16cN=ixMif@kN-$dTbIre+Lb^iw0QQt&_5@C;G5U(Qxo<%3sq-3yvsKMs4q16zi@|*|`j*z}rIMF(&tc%PE40fIrUerjF)>7JG-Cq*NPA944iSSI998mAtxX|Q)q_&kLEvKjzwP&+_SJR_F=fSfObl=Qb6(6<gj&xSit>=q@T^O?bZ4!v3@xc@^Thl^cWr85#{%6~45bABH4v4LyxHxmjx^n7@T8M%cR!|X?rIS%lb7tL<XDLO6c9S)4<!gC$<cVHm-iLE%(NEim+)B~m=E)-^`N2Xym(E(_+1U~=xlg@w>D&*{{S64z8!xH5a6EzDtla9r34$S!XKB=O&@^2LbYLDX!W)cIpN44hqTZ~9MaM2)hK68u((vnyfZsP|YXMgg0Umz5X$z61&>4M#WOYTLPoq$Xn@IpANA^$2S{jzl-&9{hq@cb|jzPN)etRm|xQ=N3tH#$l{Ae->Wt<63%{N2eFDU&1zkt&LSTb)X%@!y$)g=PB&*(7&0kBXB-BMz{3&kO8P>t56Ev3+c1-OwsZ7qa5?`N@QT>(K2d8(a=WBZW6qKU~+QC4Uk_?;f*%+}J-(^biB`55N&DUY)Ko<g16>o|;^>Es_KpJ_C1rfPkW=36uKd-o#_^j8#q)gd)!leU&J0V#AL;loMJt}a`NMzdY{p%x{s3&LMp*8v`{JcLb)19b}|QpX1!8?;tI=;_(*VqT{_UP(@W8flIvPfN4jy*4<(`U<|R9x7Wi)09ZQNS1y~78Z!zQtcL&%|Q|kY-NL|z>^}}-@8JR6s>4_#`OU0e?`_5@>yi2kJaYosB#Gr1>`F5b7z&wUs)l96#~t17QFi!oDjwa6`W<5rG8eW^LaVy_c9{{+%D{%>?F^l(5PjuM*Ts^T7Rzls8n^}e#?HuGrG1Ek$rfgO@BiP%hM7FYOPhH{G*fW-IaIBY6@_OAahM<&B0DA0XU8AaLa;`eQ5)50j-TP3BZdK3bCbBgnEU#wPRc|?nqK`Akk{}2~SrJsiR%yVR^iZd9NgAyR2E2m|KgBl2#jI+^F(~sy=_Hdn8t()RgT@#geI?5ZmEnLiQ{Lfo>_`@;_XYne<zs_Mt)?A^9a-dW@aQjJv}sB-ZL8*6Kx2%!lGY3SnVLVaky#uM{13aSo6ROVAieVK1XyiDWAo^f(hCg9KoeN+j`m>{LR8<+B<azglZWCG7dRN`t$o@+D}<mcVNSaN8Yak6eT^S3s2sUzp{ITWN!U8V`0W4+dzOPiFDck!yK1tjeguC7FO^FkAXn^^u`xNs=h79CT#J%tLLeQgc8PqLG3uay=NTRuoqtS`>A(O<_OOilUB@h?G3|BV}Symrsu|ODFnRPf(-P7#fMbx+6=B9^)1&Nm%Wk3!<ae8rL$2>phb)vUHtWt<oT1ry0|wC#ST*n@s)Inwv1%B2JB{Ipn2l0n;`Tg^_{S(lpJD)RkbQl6?k_O4WX)>5-f;fjbvxq%N$KmUew&PhMp0jGeEgFkgfo0B$sx%0u(&1%C;w=sqVyxbuK7CD;98E|gpwal}<{)y()=xf%fB@k)g#+4T>}=(_{$_;VdgfHakYwHzO|ln;+;_RV+i|J-foT-7s9#FFLgxZ<Z;+jk=)>XJ>c2qwfwn=++}PRzcu+sR~Q-+ICTR~=+2jpilPAubn^c^sWmzt6;!v38U5l-~^xb13<Nxp;1u6}c39&a2W;FmTM%5za3q@7_%jrVCW~sJMK45zZ-^`4s;+fHRk2knOCo4ouakE(`fPLqBcq;Ovv*^98M(G*Pt3Q#~uP1u>~5v%N)*;dttxhi`)8_Zwsg77Ov-Z(K*Iq8CbYfnxF&3&rEG^)QL)DhH5tVk4R8v2hJtMpMj~U>@>9QtN{DPs+kz2cjg&jj)W2oIwr3*Fm-P)u`U{0l9a@a@(|eHnb~Eu(ja1XX%?PM>-WO(Q49Y>OYapio$C$0tixozM#8gi21N;UZ?>{*f`_R34`t|D0VWVA;pV`0b5-DMit%5aa$NiCLkUKbi~``ShGTpHx@Jyojd7CC~sbz6$(V)4Imie^{H9*;pFLEM{=#z!>TUJqwF1~37yrRODaVL8A4OlW;fK`R=SxNu<c}fo7QFw50Z$1G>`pIr^N-N`_e5d6~0I@R+r_lO-IE~z85EE<4#&i#QDx-m~S-}9lHqN<3C~{s6(l&<*|^v*3AP(+Pu+c;fIAk2}RlZATt-sW0K62+LhO8Ai-82laY&hSZd{!nmGZoNEreun^dhBRV%~7&%4Z_)@9<wj&<s7aS3?Jx!L5fObGx(D#_|{p7aZIo&eLv#%7rLap|0qt;r-M&?cU+UhKL9{z?;Z^~wo)5Q4in<KRnT;xkHNBpDJ_sM=UHe8Sjv%@HHn&3wS~GF!k%bhpu35xj<yLps4&cSU(bJQ9Es3@FOCkYJcxPL5;cC62p7<z)I+sG^gI-ZRml&@wQNzBg9(Sd#hX0x?*0Pv^Rw)$+hHJc$aB6COo)(eY!gB9xXu!f2P^Z^l&pY$A;I>-o9?huaJ_<)eOS)uGlXPTH}>r%)X93ri4#SHsLS?Xndnv60ObR=R0{^pr%FRsc7mjHl1eRaj>`N2n<IS0==Z*tiNWMhTz--_FLUfDqDlmHc7r_yPE>uP?{0@AqQasH!A&Vr7(pnwP8V7kweCSyC?4UP?ACa+m7A3?^2PgUZc5FA0^)Rp;5-84xz)wiuInn$2)<S|oW|Pi?D#5qf5zm6m!h7Ej6!83$epb2EJBk<|&Trs5|zL0}bz3wTyUt+FXKT1>JyS;oT52haO)fr;Qjgsy}o0-kJ|FHYyk)O2teHVfsz)yfsNYZ>tDcxTaB9eA<D%?U+NM1+f#Jfx-E>BVD3tp;UF7WS@Dk2ENAyw!-Ei_#?eO2y(~2k~%gmoJ@NUN9RHDqSYIaNju?mwmbGGS!{IBAV=2rQYYd)H|6gOHV2>jlJ{u!i#n_LO@K)Wt0TskO@{k$k#P1E2FWBvkF&lbCO*SkO)h6>FLNSAv7Z7)o-qp3$M`=`L@g1b~1ap;=5KCs)*>dhYGT<c=6KC;*L=&!w8}xZ?DKfVz<xW6URnB4?N>VTfy-%vR<OI;5*moBX?cFex0}QJp2$YME%eC7VBs4wb^o#UNb4B78l|h&gC--8SsOQ=GPV3ds&m5tX!SSN7%<TQXgZnONeGdcOR3VON{U=cam2m^@ZM;ZEghc5l-8#W}dl5H>FEFS{U#v6N}etjvx+#>Nk1?wp|(=(~2h*f@$79Bb6j|Z;ebON3u#=f?OP*Mxjd-tMeL_$CL*U8KsH>zAA$_z4pa@27{8!kYy(^7xpo8;*uh3SEX`#h^(wtiV!O}aHHNPZM3V9vqpBSZmW6~;qp1MZ61JWs$W$zpOLS&1MsEWcel})hy-;fP>y`G^O2oSq7hm9QwjmsFHIRGml0FvO+E<Eb0t?%&`Jy>>OTaD5fiahDXsHrGBT@@D-}@iYsrRa|51hT$U!Z!T*PA<9s1i-aR~HFq+CU1JXSVB;~8qYf5G$%R8x}rxQ@<%j-^4tNc6OwP>nUq%}co8`r;zV0^sMqm>9;_z9PRcNaA*>?th!6`8<5*4Mw?UM4#`3z4>&f9+keCh000LrI76sOCA>3ovP}eRo;Ns>|L8Vn1a8ogL4)Qv{<0TL0y&AHMW#U?$GoCgRMI~eqH8ZR%d+`1*&qCsI}@;a2b+^0^c#0SUES2z^v&$?935^TG<;VHcb|#O4Co)Y+iloIsDstgrZk**~flt&8Ze7r4>-Kxjl?;uY;u$S9%wR;YuM2u8mb51n4h>G(Sq*b>YcKFNvVd7sfgd1xw_@2m+Eh1pOx{7wZIu^YM)EGGl!qfU~~-#5!CnCz;5cqnJS+vq+4flv<vX5y<mdl{89Eg9PTD;67hYqN=;@Vb60o+ckLUu%Qz^r34rnhG!RuW~@1$cEXTwohChuOQ(SYjN2@71!Fp-$o2Q@3oI?eWnB&nXgqK2(#vv@_<T#zfOTKk4&W2GsYLy;ss1u#zSqSFa!~~qgt^eR-S)Mk>WP<`a8a)j0)(&%*yjZP#km}D?5|FRUXPD)b#XVtNjoM0x<as~`Qfqnn3hi17)~jpW?uN3(`|&Mo!5djmlVxN@*EjFVChY9h3tazVg^h&$%`d~=CYJLpyvL|3?iayP&`F?v>?P7L06`Kr`VR1Fl~uUw8Makb?P-?%W>&dX-THod0W3YkasF%Yz~~l(;h`k8W&>%IDxtntJs_x*UPIu1&YIVD5PxUCC(~hj;zT8wpY4Pnr#=4JkFkAuJOjc&?F6aR@<7()S1O;6%EUBZBioEN%Mon9KMktE0tLT{)b%)sofMtSoo}>szWMMQCvGOk1#}+lDWJf52EGkYn3#(Vw9Y7u&nQb!kr$~URA5Ej}fShFMOeBY7p)s)T_3KD(R)|%&PBF=g^r}ewLuaQV-42s=Q+GMwe2wD6XzN*jarWQC(B7P)J<mxsHbQW*x}>k6qhFF&7FeP+_Q2@g!j8GWz~@(h@b{-V=Q}NGNg%?!b%x2Z_%|6ohoWWYmQ*nvm79wy{LQu!6jKfZu6+2DX%(IFDso$9wQ{iuD#WZB$i;wr8d3G^*a3zPSwKsz&_-o{}gRkE#}=Dvm3I`Xy2Pcxg^>Wbt^p8ZEpW#NLD1<sMBm!SY*$hEhcng@*@H@ieqet9U}9Dyu%6o0Phy@;B+6=_h+u*0(Gp$Cz|{o>B>Y$7jFlqnG6;sg@@ru$9UiqFC3RWcG0`P)wa6J7pO%$@)r^WbB>L+i{dvY_6HASVzQts9Xsx>L@XiiaGyhW$G1!tf@AiR5+lPZ&!<JStU_L`4a|J7?rawZGO$dsXl6hT$HL>%#nQ4kt9o8r3UmN>7ZhggS6+;^?2HW`WqE&_0>zskx$bjGG6=0kp4o}5KFfjiLE<$K7tsxl9(_pD#l<nO1KV#)nk|ueYCYVl!L#e&@H>kZTe>X`c;Ley!V#@=)^o<w9JHLg!P!xEl&1s4%9`)HOkw%tmY>y`uJZKSXPmiQ>9*(%R#)bq5Y8AMQ*b1g%M>`mT-R|4MV7IqcTgeK~@6=b>T_P?dAhgWW2080YjZ)s+4Z7a^0>5A&DthL5mJE>V_136hJC3r<WD@NaB@R4cqj%)CGb<%ZJ7s6l7A>h5@RWG3#MaZR-|D$lwrKJe^ki?5t|Zn4U@UCMyoqz{NA8*eWHev^v?ZXnciA?mTt4k~n)W5I8||fXUR_g;q37Nu|i@dud>&lSbi`4cR@2KuDzg$lZmy9Ihk#m{;M}Fc7Ab+eLz`CUeruhld`y(`IV@9;r}nlny{t7jg;1A=<vwuqBRemWiqA7(W6$BW8q<&(dNu>`0aM0wWOJ>D)e7vTwc7Vt&*-A3#1oT8ZLBRu_~*Ily0It+hXr99|QA{AP<8b2kV!$tqltu%3$bMP)3=NvusGE|!v=7QR-%bw*38jG2-`YgVF=giMO1cWF$)s5VumWdW_N){UnQ7q+|y!GBk^LdarqjQk`CKN>}pQ_30x?~jyjiI)GdW<;sBP0MaGci}z{4R<adozW)b|49OVeQJuUvVTLUN#ws2ij!K2Q}>*cZAn>XQk6n!@l**&#LL$}tVG7Fcf8wOz}bW}J^(oo0jGgz8j8Bh!>d@pDrjJGq>{9Snibu8TyDu(tqQH8iZW76-q1ZED=!yhtZf)Eb(vFkC_gPToIEXx?(Lyf7dNU#*@e5!+)S1l-x7EjZAamBmEl)sT`^IFHqo+8evb>-4b6%bYeX>VYD5hiR7`nL&14%VdXDQylx-k*x;%^Oy8@K^vI}(qeBAFV%h6ELmLldg!7O_ERf#B><pjNkm2+H<$Og=AF(~}u!7>tKgqhn$2GIPMt-`BR>pZdVX|TOggf{_GGptps_$cMvf_sCBm(eRFtE2}_jRKC5+p87@+FC~H%!$s3e1n$iz)?_M3jTnGTFqlbev!nUMCv>TZ(-JwOaUcZ|GGHO5>J-qin3{L&cuOhFbmX+vQj46;!bpS@N?l9?l)WQ{BZs8W9W-K{ohQ`eET6Y<ab}1xWA7db+!#Qq<!ErTt{jfY0rMl_Q+Dy3h=ELXc(U1wzac|7id}G;k8vqYSkPvqS1^sW<bD*wpvoKk3*4Ed@a<I5MNAbXEf%Xad2~QfQMO9bCHTkm0V_q1ZmlJd8d)gnU)RCm~n#Z#c%zLTb&Gi?p`G;{GJ@~l37k(-JV!T{0-eVaIw$K4C}>cHi2!>S~BEp%zF#{2J(*ZcC}s$H!$lgF`=v%@BX%ZYi>6Tf2C*`_Pi7rYPD<Du)y1nwhz&Fim#Nq8Ll+zrTbXT-R+0$1<@x&hi8q7+*SM^RGNxxv3x8DMAx1eOrDPnM*2$HQC>{U=<4&_PE+ff+1`CZ9%f%w<1gEJf0Ng4Jd(|QI5rRe3!QmfDg')).decode('utf-8'))


_TRUE_MILK_SUPPORT_SHOPS: Set[str] = {
    "PIZZA_SHOP",
    "ICE_CREAM_SHOP",
    "SMOOTHIE_SHOP",
}

_CACHED_TAPES: Dict[str, List[Dict[str, Any]]] = {}
_COMMITTED_ROUTE: Dict[int, Optional[str]] = {0: None, 1: None}

def get_base_tape(route_name: str = "8c6s_3q") -> List[Dict[str, Any]]:
    """Lazily loads and returns the requested base tape."""
    if route_name not in _CACHED_TAPES:
        if route_name == "6c12s_4q_first_yarn":
            _CACHED_TAPES[route_name] = _ACTIONS_6C12S_4Q_FIRST_YARN
        elif route_name == "6c12s_4q_second_yarn":
            _CACHED_TAPES[route_name] = _ACTIONS_6C12S_4Q_SECOND_YARN
        elif route_name == "6c8s_3q":
            _CACHED_TAPES[route_name] = _ACTIONS_6C8S_3Q
        elif route_name == "10c4s_3q":
            _CACHED_TAPES[route_name] = _ACTIONS_10C4S_3Q
        else:
            _CACHED_TAPES[route_name] = _ACTIONS_8C6S_3Q
    return _CACHED_TAPES[route_name]

def select_active_tape(obs: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Selects and locks the optimal route based on Town Shop rolls at Day 3 / Day 6.
    Permanently locks the route by Day 6 (Step 144) to prevent late animal layout oscillation.
    Uses TRUE Milk Support Shops (Pizza Shop, Ice Cream Shop, Smoothie Shop) only.
    """
    step = int(obs.get("step", 0) or 0)
    player = int(obs.get("player", 0) or 0)

    if step == 0:
        _COMMITTED_ROUTE[player] = None

    if _COMMITTED_ROUTE[player] is not None and step >= 144:
        return get_base_tape(_COMMITTED_ROUTE[player])

    shops = (obs.get("town") or {}).get("unlocked_shops", []) or []

    # 1. First shop on Day 3
    if len(shops) >= 1:
        if shops[:1] == ["YARN_STORE"]:
            _COMMITTED_ROUTE[player] = "6c12s_4q_first_yarn"
            return get_base_tape("6c12s_4q_first_yarn")
        if _TRUE_MILK_SUPPORT_SHOPS.intersection(shops[:1]):
            _COMMITTED_ROUTE[player] = "10c4s_3q"
            return get_base_tape("10c4s_3q")

    # 2. Second shop on Day 6
    if len(shops) >= 2:
        if "YARN_STORE" in shops[:2]:
            _COMMITTED_ROUTE[player] = "6c12s_4q_second_yarn"
            return get_base_tape("6c12s_4q_second_yarn")
        if _TRUE_MILK_SUPPORT_SHOPS.intersection(shops[:2]):
            _COMMITTED_ROUTE[player] = "10c4s_3q"
            return get_base_tape("10c4s_3q")

    # 3. Third shop fallback before Step 144
    if len(shops) >= 3 and "YARN_STORE" in shops[:3] and step < 144:
        _COMMITTED_ROUTE[player] = "6c8s_3q"
        return get_base_tape("6c8s_3q")

    default_route = "10c4s_3q" if _TRUE_MILK_SUPPORT_SHOPS.intersection(shops[:3]) else "8c6s_3q"
    if step >= 144:
        _COMMITTED_ROUTE[player] = default_route
    return get_base_tape(default_route)

def get_lookahead_scheduled_sells(
    tape: List[Dict[str, Any]],
    current_step: int,
    lookahead_steps: int = 96
) -> Dict[str, Tuple[int, int]]:
    scheduled: Dict[str, Tuple[int, int]] = {}
    for i in range(1, lookahead_steps + 1):
        idx = current_step + i
        if idx >= len(tape):
            break
        for order in tape[idx].get("market", []) or []:
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                item = order[1]
                qty = max(0, int(order[2] or 0))
                if item not in scheduled and qty > 0:
                    scheduled[item] = (idx, qty)
    return scheduled


# ==================== MASTER AGENT SYNTHESIS ====================
"""Project Aegis: Master Competitive Agent for Kaggriculture

Architecture:
- Mathematically optimized base tapes with multi-route town shop selection.
- Dynamic Opponent Shed Forensics & Front-Running (The Predator).
- Scaled Continuous Trickle-Selling, Liquidity Guard & Hard Pressure Valve (The River).
- Zero In-Memory Tape Mutation via Pure Debt Accounting.
- Non-Spatial Signature Spoofing (The Ghost Protocol).
- Weed Repair and Feed Rescue Execution Guards.
- Unscripted Farmhand Coordination (Scavenger Overlay).
- Guaranteed Terminal Liquidation (Steps 716-720).
- Universal Exception Safety Wrapper.
"""

import copy
from typing import Dict, Any, List









class AegisAgentState:
    def __init__(self):
        self.debt_mgr = PureDebtManager()
        self.shed_estimator = OpponentShedEstimator()
        self.predator = PredatorEngine(self.shed_estimator)
        self.river = RiverEngine()
        self.last_step = -1

    def reset_if_new_game(self, step: int):
        if step == 0 or step < self.last_step:
            self.debt_mgr.reset_if_new_game(step)
            self.shed_estimator.reset_if_new_game(step)
            self.river = RiverEngine()
        self.last_step = step


_AEGIS_STATES: Dict[int, AegisAgentState] = {}

def _get_seat_state(obs: Dict[str, Any]) -> AegisAgentState:
    seat = obs.get("player", 0) if isinstance(obs, dict) else 0
    if seat not in _AEGIS_STATES:
        _AEGIS_STATES[seat] = AegisAgentState()
    return _AEGIS_STATES[seat]


def _aegis_core_step(obs: Dict[str, Any]) -> Dict[str, Any]:
    step = obs.get("step", 0)
    state = _get_seat_state(obs)
    state.reset_if_new_game(step)

    # 1. Update forensic model of opponent
    state.predator.update(obs)

    # 2. Select active base route (adapting to Town Shop rolls)
    active_tape = select_active_tape(obs)

    # 3. Retrieve base action for this step
    if step < len(active_tape):
        raw_tape_action = copy.deepcopy(active_tape[step])
    else:
        raw_tape_action = {"farmer": ["PASS"], "hands": [], "market": []}

    # 4. Weed Repair Guard (dynamically clear random weeds on action tiles)
    action = weed_repair_overlay(raw_tape_action, obs, step)

    # 5. Feed Rescue Guard (emergency wheat feed buy if animals unfed at hour 18+)
    action = feed_rescue_guard(action, obs, step)

    # 6. Apply Pure Debt Repayment (intercepts scheduled sales to repay prior front-runs)
    action = state.debt_mgr.apply_repayment(action, step)

    # 7. Process tape market orders through River
    processed_market = state.river.process_tape_orders(action.get("market", []), step)

    # 8. Evaluate Predator front-running opportunities
    lookahead_sells = get_lookahead_scheduled_sells(active_tape, step, lookahead_steps=96)
    frontrun_orders = state.predator.evaluate_frontrun_opportunities(
        obs, processed_market, state.debt_mgr, lookahead_sells
    )

    # 9. Generate scaled trickle sales & enforce Liquidity Guard
    future_slice = active_tape[step: min(len(active_tape), step + 10)]
    initial_market = processed_market + frontrun_orders
    action["market"] = state.river.generate_trickle_orders(obs, initial_market, future_slice)

    # 10. Apply Ghost Protocol signature spoofing on Step 0
    action = apply_ghost_signature_spoof(obs, action)

    # 11. Schedule auxiliary scavenger farmhand on morning Hour 0
    scarcity_active = OpportunisticCropManager.detect_scarcity_opportunity(obs) is not None
    action = schedule_auxiliary_farmhand_hire(action, obs, scarcity_active=scarcity_active)

    # 12. Scavenge unscripted farmhands for weeds, fertilizer, and scarcity/Wave-2 crops
    action = scavenger_farmhand_overlay(action, obs, active_tape=active_tape, step=step)

    # 12. Align hands count strictly to live hands
    player = obs.get("player", 0) if isinstance(obs, dict) else 0
    farms = obs.get("farms", []) if isinstance(obs, dict) else []
    my_farm = farms[player] if len(farms) > player and isinstance(farms[player], dict) else {}
    live_hands_count = len(my_farm.get("hands", []) or [])
    action["hands"] = (action.get("hands", []) or [])[:live_hands_count]

    # 13. Execute terminal liquidation in the final turns
    action = execute_terminal_liquidation(obs, action, step)

    # Truncate market orders at max 10
    action["market"] = action.get("market", [])[:MAX_MARKET_ORDERS]

    return action


def agent(obs: Dict[str, Any], config: Any = None) -> Dict[str, Any]:
    try:
        return _aegis_core_step(obs)
    except Exception:
        return safe_agent_fallback(obs)

