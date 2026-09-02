"""Small exact market rollout used by the v23 event-triggered planner.

This is intentionally not a full farm simulator.  The actor schedule remains a
validated open-loop backbone; only the market subsystem is rolled forward when
an observed demand or inventory event can change a SELL continuation.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from v23.state_encoder import PRODUCTS, SHOP_PRODUCTS


PRICE_FLOOR = 1
MARKET_PARAMS = {
    "WHEAT": (25, 10000, 400, "sqrt", 0.80, "log", 0.20),
    "CARROT": (35, 10000, 450, "hinge", 1.00, "sqrt", 0.70),
    "TOMATO": (60, 10000, 200, "hinge", 0.40, "sqrt", 0.60),
    "STRAWBERRY": (120, 10000, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": (250, 10000, 300, "log", 0.20, "sq", 3.60),
    "EGG": (50, 10000, 332, "hinge", 0.40, "log", 0.20),
    "MILK": (160, 10000, 122, "sqrt", 0.60, "linear", 1.60),
    "WOOL": (200, 10000, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 10000, 200, "linear", 0.40, "linear", 0.40),
}


def _shape(name: str, value: float, scale: float | None = None) -> float:
    value = max(0.0, value)
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
    raise ValueError(name)


def market_price(item: str, inventory: int) -> int:
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


def execute_sell(item: str, inventory: int, quantity: int) -> tuple[int, int]:
    """Exact unit-lockstep revenue for one unilateral SELL order."""
    revenue = 0
    inventory = int(inventory)
    for _ in range(max(0, int(quantity))):
        quote = market_price(item, inventory)
        revenue += quote
        # Official engine does not add $1 sales to market inventory.
        if quote > 1:
            inventory += 1
    return revenue, inventory


def demand_on_tick(unlocked_shops: tuple[str, ...]) -> dict[str, int]:
    demand = {product: 0 for product in PRODUCTS}
    for shop in unlocked_shops:
        products = SHOP_PRODUCTS.get(shop, ())
        multiplier = 2 if len(products) == 1 else 1
        for product in products:
            demand[product] += multiplier
    return demand


@dataclass(frozen=True)
class MarketRollout:
    immediate_revenue: float
    terminal_value: float
    objective: float
    ending_inventory: int
    ending_quantity: int


def rollout_sale_choice(
    *,
    item: str,
    market_inventory: int,
    owned_quantity: int,
    sell_now: int,
    step: int,
    horizon_turns: int,
    unlocked_shops: tuple[str, ...],
    regime: str,
    projected_supply_per_turn: float = 0.0,
    terminal_discount: float = 0.95,
    shop_interval: int = 4,
    center_interval: int | None = None,
) -> MarketRollout:
    """Evaluate immediate sale plus marked-to-market remaining stock.

    Supply is a deliberately coarse public-state projection.  Demand timing and
    the official nonlinear price curve are exact for the fixed shop set.
    """
    center_interval = center_interval or (24 if regime == "rebalance" else 12)
    sell_now = min(max(0, int(sell_now)), max(0, int(owned_quantity)))
    immediate, inventory = execute_sell(item, market_inventory, sell_now)
    remaining = max(0, int(owned_quantity) - sell_now)
    shop_tick = demand_on_tick(unlocked_shops)
    for offset in range(max(0, int(horizon_turns))):
        future_step = int(step) + offset
        inventory += int(round(max(0.0, projected_supply_per_turn)))
        if future_step % max(1, shop_interval) == 0:
            inventory -= shop_tick.get(item, 0)
        if future_step % max(1, center_interval) == 0 and item != "FERTILIZER":
            if regime == "rebalance":
                multiplier = 1
            else:
                day = future_step // 24
                multiplier = 4 if day >= 20 else 2 if day >= 10 else 1
            inventory -= multiplier
    terminal_quote = market_price(item, inventory)
    terminal_value = terminal_discount * remaining * terminal_quote
    return MarketRollout(
        immediate_revenue=float(immediate),
        terminal_value=float(terminal_value),
        objective=float(immediate) + terminal_value,
        ending_inventory=inventory,
        ending_quantity=remaining,
    )


def best_sale_quantity(
    *,
    base_quantity: int,
    switch_cost: float = 0.0,
    **kwargs,
) -> tuple[int, dict[int, MarketRollout]]:
    """Search a bounded quantity set and charge deviation from the backbone."""
    base_quantity = max(0, int(base_quantity))
    candidates = sorted(
        {
            0,
            base_quantity,
            base_quantity // 4,
            base_quantity // 2,
            (3 * base_quantity) // 4,
        }
    )
    rows = {
        quantity: rollout_sale_choice(sell_now=quantity, **kwargs)
        for quantity in candidates
    }
    selected = max(
        candidates,
        key=lambda quantity: (
            rows[quantity].objective
            - (0.0 if quantity == base_quantity else float(switch_cost)),
            -abs(quantity - base_quantity),
        ),
    )
    return selected, rows


def projected_supply_from_exposure(
    own_exposure: Mapping[str, float],
    opponent_exposure: Mapping[str, float],
    item: str,
    horizon_turns: int,
) -> float:
    """Conservative per-turn public supply proxy for the market rollout."""
    total = max(0.0, float(own_exposure.get(item, 0))) + max(
        0.0, float(opponent_exposure.get(item, 0))
    )
    return total / max(24.0, float(horizon_turns))
