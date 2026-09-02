#!/usr/bin/env python3
"""Order-safe market-impact controls for the v22 Kaggriculture study.

The public v21.1 agent ranks a predicted collision with a hand-written
exposure score and then moves those SELL orders to the front of the complete
market queue.  This module provides deliberately smaller counterfactuals:

* ``impact_slots`` changes only the contents of existing SELL slots;
* ``impact_front`` uses the same score but moves all SELLs before non-SELLs;
* neither mode creates, removes, or changes the quantity of an order.

The default price curve below is an exact, stdlib-only transcription of the
official Kaggriculture 1.32.7 market parameters.  Keeping it local also makes
the eventual submission artifact independent of ``kaggle_environments``.
"""

from __future__ import annotations

import copy
import math


PRICE_FLOOR = 1
MARKET_PARAMS = {
    "WHEAT": (25, 10000, 400, "sqrt", 0.8, "log", 0.2),
    "CARROT": (35, 10000, 450, "hinge", 1.0, "sqrt", 0.7),
    "TOMATO": (60, 10000, 200, "hinge", 0.4, "sqrt", 0.6),
    "STRAWBERRY": (120, 10000, 100, "sqrt", 0.7, "linear", 1.6),
    "MELON": (250, 10000, 300, "log", 0.2, "sq", 3.6),
    "EGG": (50, 10000, 332, "hinge", 0.4, "log", 0.2),
    "MILK": (160, 10000, 122, "sqrt", 0.6, "linear", 1.6),
    "WOOL": (200, 10000, 105, "log", 0.2, "sq", 3.2),
    "FERTILIZER": (100, 10000, 200, "linear", 0.4, "linear", 0.4),
}


def _get(value, key, default=None):
    if isinstance(value, dict):
        return value.get(key, default)
    return getattr(value, key, default)


def _shape(name: str, value: float, scale: float | None = None) -> float:
    value = max(0.0, float(value))
    if name == "linear":
        return value
    if name == "sq":
        return value * value
    if name == "sqrt":
        return math.sqrt(value)
    if name == "log":
        return math.log1p(value)
    if name == "log10":
        return math.log10(1.0 + value)
    if name == "hinge":
        if scale is None or scale <= 0:
            return value
        normalized = value / scale
        return normalized + 8.0 * max(0.0, normalized - 1.0) ** 2
    raise ValueError(f"unknown market shape {name!r}")


def market_price(item: str, inventory: int) -> int:
    """Return the Kaggriculture 1.32.7 default quote for one inventory level."""
    base, equilibrium, scale, below_func, below_target, above_func, above_target = (
        MARKET_PARAMS[item]
    )
    if inventory < equilibrium:
        amplitude = below_target * base / _shape(below_func, scale, scale)
        price = base + amplitude * _shape(
            below_func, equilibrium - inventory, scale
        )
    else:
        amplitude = above_target * base / _shape(above_func, scale, scale)
        price = base - amplitude * _shape(
            above_func, inventory - equilibrium, scale
        )
    return max(PRICE_FLOOR, int(round(price)))


def is_sell(order) -> bool:
    return (
        isinstance(order, (list, tuple))
        and len(order) >= 3
        and order[0] == "SELL"
        and order[1] in MARKET_PARAMS
    )


def impact_score(obs, order) -> float:
    """Proxy for the price damage caused by executing this SELL now.

    This intentionally follows the public impact-ranking experiment:
    quantity * (current quote - quote after this order).  It estimates the
    value of being earlier without pretending to observe the opponent's
    private inventory or simultaneous action.
    """
    if not is_sell(order):
        return float("-inf")
    item = str(order[1])
    try:
        quantity = max(0, int(order[2]))
    except (TypeError, ValueError):
        return 0.0
    market = _get(obs, "market", {}) or {}
    inventory = _get(market, "inventory", {}) or {}
    prices = _get(market, "prices", {}) or {}
    current_inventory = int(_get(inventory, item, 10000) or 0)
    current_quote = float(
        _get(prices, item, market_price(item, current_inventory)) or 0
    )
    later_quote = float(market_price(item, current_inventory + quantity))
    return float(quantity) * max(0.0, current_quote - later_quote)


def _safe_action(action):
    result = copy.deepcopy(action) if isinstance(action, dict) else {}
    result.setdefault("farmer", ["PASS"])
    result.setdefault("hands", [])
    market = result.get("market")
    result["market"] = list(market) if isinstance(market, (list, tuple)) else []
    return result


def reorder_market(obs, action, mode: str = "impact_slots"):
    """Reorder existing SELLs while preserving the order multiset exactly."""
    result = _safe_action(action)
    market = list(result["market"])
    sell_rows = [
        (impact_score(obs, order), -index, copy.deepcopy(order))
        for index, order in enumerate(market)
        if is_sell(order)
    ]
    if len(sell_rows) < 2:
        return result
    sell_rows.sort(reverse=True)
    ranked = [row[2] for row in sell_rows]
    if mode == "impact_slots":
        iterator = iter(ranked)
        result["market"] = [next(iterator) if is_sell(order) else order for order in market]
    elif mode == "impact_front":
        others = [order for order in market if not is_sell(order)]
        result["market"] = ranked + others
    else:
        raise ValueError(f"unknown reorder mode {mode!r}")
    return result


def wrap_market_impact(base_policy, mode: str = "impact_slots"):
    telemetry = {"games": 0, "sell_turns": 0, "reordered_turns": 0}

    def policy(obs):
        step = max(0, int(_get(obs, "step", 0) or 0))
        if step == 0:
            telemetry["games"] += 1
        original = _safe_action(base_policy(obs))
        if sum(is_sell(order) for order in original["market"]) >= 2:
            telemetry["sell_turns"] += 1
        result = reorder_market(obs, original, mode)
        telemetry["reordered_turns"] += result["market"] != original["market"]
        return result

    policy.telemetry = telemetry
    return policy
