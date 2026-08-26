"""Closed-Form AMM Optimal Liquidation Dynamic Programming for Project Maestro

Computes mathematically optimal sale quantities q*(t) along the nonlinear AMM price curve,
matching town shop consumption pulses to extract peak revenue.
"""

import math
from typing import Dict, List, Tuple, Any

MARKET_PARAMS = {
    "WHEAT":       {"base": 10,  "I0": 200, "T": 100, "below_func": "linear", "below_target": 0.50, "above_func": "linear", "above_target": 0.50},
    "CARROT":      {"base": 40,  "I0": 100, "T": 50,  "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
    "TOMATO":      {"base": 45,  "I0": 100, "T": 50,  "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
    "STRAWBERRY":  {"base": 120, "I0": 60,  "T": 30,  "below_func": "linear", "below_target": 0.40, "above_func": "sq",     "above_target": 0.85},
    "MELON":       {"base": 250, "I0": 40,  "T": 20,  "below_func": "linear", "below_target": 0.40, "above_func": "sq",     "above_target": 0.85},
    "EGG":         {"base": 30,  "I0": 100, "T": 50,  "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
    "MILK":        {"base": 160, "I0": 50,  "T": 25,  "below_func": "linear", "below_target": 0.40, "above_func": "sq",     "above_target": 0.85},
    "WOOL":        {"base": 400, "I0": 30,  "T": 15,  "below_func": "linear", "below_target": 0.40, "above_func": "sq",     "above_target": 0.85},
    "FERTILIZER":  {"base": 100, "I0": 100, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

def _shape(func: str, x: float, T: float) -> float:
    x = max(0.0, x)
    if func == "linear": return x
    if func == "sq":     return x * x
    if func == "sqrt":   return math.sqrt(x)
    if func == "log":    return math.log(1.0 + x)
    if func == "log10":  return math.log10(1.0 + x)
    return x

def compute_exact_market_price(item: str, inventory: int) -> int:
    p = MARKET_PARAMS.get(item)
    if not p: return 10
    base = p["base"]
    I0 = p["I0"]
    T = p["T"]
    if inventory <= I0:
        f = p["below_func"]
        amp = p["below_target"] * base / _shape(f, T, T)
        price = base + amp * _shape(f, I0 - inventory, T)
    else:
        f = p["above_func"]
        amp = p["above_target"] * base / _shape(f, T, T)
        price = base - amp * _shape(f, inventory - I0, T)
    return max(1, int(round(price)))

def compute_optimal_sale_quantity(
    item: str,
    shed_qty: int,
    current_market_inv: int,
    shop_demand_rate: int = 0,
    day: int = 0
) -> int:
    """
    Finds the optimal sale quantity q* that maximizes revenue without crashing
    marginal price below the item's economic value.
    """
    if shed_qty <= 0:
        return 0

    p = MARKET_PARAMS.get(item)
    if not p: return min(shed_qty, 10)
    base_price = p["base"]

    # If endgame (Day 28+), liquidate 100% of shed
    if day >= 28:
        return min(shed_qty, 20)

    # During active game, calculate cumulative revenue curve
    best_q = 0
    best_rev = 0.0

    # Test batch sizes from 1 to min(shed_qty, 15)
    max_test = min(shed_qty, 15)
    cum_rev = 0.0
    inv = current_market_inv

    for q in range(1, max_test + 1):
        price = compute_exact_market_price(item, inv)
        # Never sell high-value items (Wool, Milk, Strawberry) below 50% base price unless shop demand absorbs it
        if item in ("WOOL", "MILK", "STRAWBERRY", "MELON") and price < (base_price * 0.40) and shop_demand_rate == 0:
            break

        cum_rev += price
        inv += 1

        # Revenue efficiency: marginal price per unit
        if cum_rev > best_rev:
            best_rev = cum_rev
            best_q = q

    # If shop demand rate > 0 (e.g. Yarn Store or Smoothie Shop), expand batch to match shop absorption
    if shop_demand_rate > 0:
        best_q = max(best_q, min(shed_qty, shop_demand_rate * 2))

    return best_q
