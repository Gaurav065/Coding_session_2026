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



