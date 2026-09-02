"""Safe continuation and market experts for v23 research."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable

from scripts.v22_market_impact import impact_score, is_sell
from v23.simulator import best_sale_quantity, market_price
from v23.state_encoder import BASE_PRICE, encode_state, get, regime_from_configuration


PASS = {"farmer": ["PASS"], "hands": [], "market": []}


def safe_action(action: Any) -> dict:
    result = copy.deepcopy(action) if isinstance(action, dict) else {}
    result.setdefault("farmer", ["PASS"])
    result.setdefault("hands", [])
    market = result.get("market")
    result["market"] = list(market) if isinstance(market, (list, tuple)) else []
    return result


def shared_prefix_length(routes: dict[str, list[dict]]) -> int:
    if not routes:
        return 0
    rows = list(routes.values())
    prefix = 0
    for actions in zip(*rows):
        if any(action != actions[0] for action in actions[1:]):
            break
        prefix += 1
    return prefix


def _demand_adjusted_score(obs, configuration, order, alpha: float) -> float:
    score = impact_score(obs, order)
    if score <= 0 or not is_sell(order):
        return score
    state = encode_state(obs, configuration)
    item = str(order[1])
    quantity = max(0, int(order[2]))
    inventory = int(state.market_inventory.get(item, 10000))
    demand = max(0.0, state.demand_per_day.get(item, 0.0))
    post_inventory = inventory + quantity
    excess = max(0.0, post_inventory - 10000)
    recovery_days = excess / max(0.25, demand)
    urgency = min(1.0, recovery_days / 10.0)
    return score * (1.0 + max(0.0, float(alpha)) * urgency)


def reorder_sell_slots(
    obs,
    action,
    configuration=None,
    *,
    demand_alpha: float = 0.0,
) -> dict:
    """Sort only existing SELL slots; preserve every non-SELL position."""
    result = safe_action(action)
    market = list(result["market"])
    sells = []
    for index, order in enumerate(market):
        if not is_sell(order):
            continue
        score = (
            _demand_adjusted_score(obs, configuration, order, demand_alpha)
            if demand_alpha > 0
            else impact_score(obs, order)
        )
        sells.append((score, -index, copy.deepcopy(order)))
    if len(sells) < 2:
        return result
    sells.sort(reverse=True)
    ranked = iter(row[2] for row in sells)
    result["market"] = [next(ranked) if is_sell(order) else order for order in market]
    return result


def plan_sell_quantities(
    obs,
    action,
    configuration=None,
    *,
    horizon_turns: int = 24,
    switch_cost: float = 250.0,
    minimum_step: int = 240,
    cash_reserve: float = 2500.0,
) -> dict:
    """Bounded MPC-like SELL quantity adjustment for rebalance experiments.

    Quantity changes are prohibited on capital-order turns and while cash is
    tight.  This prevents a delayed sale from silently invalidating BUY/HIRE.
    """
    result = safe_action(action)
    if regime_from_configuration(configuration) != "rebalance":
        return result
    step = int(get(obs, "step", 0) or 0)
    if step < minimum_step:
        return result
    market_orders = result["market"]
    if any(order and order[0] != "SELL" for order in market_orders):
        return result
    state = encode_state(obs, configuration)
    if state.own.get("money", 0.0) < cash_reserve:
        return result
    changed = []
    for order in market_orders:
        if not is_sell(order):
            changed.append(order)
            continue
        item = str(order[1])
        base_quantity = max(0, int(order[2]))
        owned = max(base_quantity, int(state.shed.get(item, 0)))
        selected, _rows = best_sale_quantity(
            item=item,
            market_inventory=int(state.market_inventory.get(item, 10000)),
            owned_quantity=owned,
            base_quantity=base_quantity,
            step=step,
            horizon_turns=horizon_turns,
            unlocked_shops=state.shops,
            regime=state.regime,
            switch_cost=switch_cost,
        )
        if selected > 0:
            changed.append(["SELL", item, selected])
    result["market"] = changed
    return result


def terminal_liquidation(obs, action) -> dict:
    result = safe_action(action)
    step = int(get(obs, "step", 0) or 0)
    if step != 718:
        return result
    private = get(obs, "private", {}) or {}
    shed = get(private, "shed", {}) or {}
    market = get(obs, "market", {}) or {}
    inventory = get(market, "inventory", {}) or {}
    rows = []
    for item, quantity in shed.items():
        if item not in BASE_PRICE or int(quantity or 0) <= 0:
            continue
        quote = market_price(item, int(get(inventory, item, 10000) or 10000))
        rows.append((quote * int(quantity), ["SELL", item, int(quantity)]))
    rows.sort(reverse=True)
    result["market"] = [row[1] for row in rows[:10]]
    return result


@dataclass
class RouteLibrary:
    routes: dict[str, list[dict]]
    default: str
    trigger_step: int

    def __post_init__(self):
        if self.default not in self.routes:
            raise ValueError(f"missing default route {self.default!r}")
        if shared_prefix_length(self.routes) < self.trigger_step:
            raise ValueError("routes do not share the required decision prefix")

    def policy(self, selector: Callable[[Any, Any], str]):
        selections = {0: self.default, 1: self.default}
        last_step = {0: -1, 1: -1}

        def agent(obs, configuration=None):
            seat = int(get(obs, "player", 0) or 0)
            step = int(get(obs, "step", 0) or 0)
            if step == 0 or step < last_step[seat]:
                selections[seat] = self.default
            last_step[seat] = step
            if step == self.trigger_step:
                selected = selector(obs, configuration)
                if selected in self.routes:
                    selections[seat] = selected
            route = self.routes[selections[seat]]
            return safe_action(route[min(step, len(route) - 1)])

        agent.selections = selections
        return agent
