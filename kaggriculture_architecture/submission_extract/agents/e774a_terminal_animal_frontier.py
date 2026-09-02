"""E774A: liquidate visible shed MILK/WOOL on the final executable turn."""

from __future__ import annotations

import copy
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

import e773a_demand_aligned_pasture_network as PARENT

ENGINE = PARENT.ENGINE
FINAL_EXECUTABLE_STEP = 718
PRODUCTS = ("MILK", "WOOL")
STEP_NETWORK = PARENT.STEP_NETWORK
PROVENANCE = {
    **PARENT.PROVENANCE,
    "owned_terminal_frontier": (
        "step-718 projected-shed MILK/WOOL liquidation after the complete parent action"
    ),
    "parent_sha256": "f7e31def12b377a74a777561ea0f65e571be1e0d735ae4eb1825e70c0c8bafae",
    "final_executable_step": FINAL_EXECUTABLE_STEP,
}

_LAST_DIAGNOSTIC: dict[int, dict[str, Any]] = {0: {}, 1: {}}


def _revenue(item: str, inventory: int, quantity: int) -> int:
    return sum(ENGINE._price(item, inventory + offset) for offset in range(quantity))


def _terminal_orders(
    obs: Any, seat: int, action: dict[str, Any]
) -> list[list[Any]]:
    available, _ = PARENT.BASE._project_shed(obs, seat, action)
    for order in action.get("market") or []:
        if len(order) >= 3 and order[0] == "SELL":
            item = str(order[1])
            available[item] = max(
                0, int(available.get(item, 0)) - max(0, int(order[2] or 0))
            )
    market = ENGINE._get(obs, "market", {}) or {}
    raw_inventory = ENGINE._get(market, "inventory", {}) or {}
    ranked = []
    for item in PRODUCTS:
        quantity = max(0, int(available.get(item, 0)))
        if not quantity:
            continue
        inventory = int(ENGINE._get(raw_inventory, item, ENGINE.I0) or ENGINE.I0)
        ranked.append((_revenue(item, inventory, quantity), item, quantity))
    ranked.sort(reverse=True)
    return [["SELL", item, quantity] for _, item, quantity in ranked]


def _append_terminal_frontier(
    obs: Any, seat: int, action: dict[str, Any]
) -> tuple[dict[str, Any], list[list[Any]]]:
    step = int(ENGINE._get(obs, "step", 0) or 0)
    if step != FINAL_EXECUTABLE_STEP:
        return action, []
    additions = _terminal_orders(obs, seat, action)
    if not additions:
        return action, []
    changed = ENGINE._copy_action(action)
    room = max(0, ENGINE.MAX_MARKET_ORDERS - len(changed["market"]))
    additions = additions[:room]
    changed["market"].extend(copy.deepcopy(additions))
    return changed, additions


def _order_units(orders: Iterable[list[Any]]) -> int:
    return sum(
        max(0, int(order[2] or 0))
        for order in orders
        if len(order) >= 3 and order[0] == "SELL"
    )


def agent(obs: Any, configuration: Any = None) -> dict[str, Any]:
    seat = ENGINE._seat(obs)
    step = max(0, min(ENGINE.MAX_STEPS - 1, int(ENGINE._get(obs, "step", 0) or 0)))
    parent_action = PARENT.agent(obs, configuration)
    action, additions = _append_terminal_frontier(obs, seat, parent_action)
    _LAST_DIAGNOSTIC[seat] = {
        "step": step,
        "intervened": bool(additions),
        "terminal_orders": copy.deepcopy(additions),
        "terminal_units": _order_units(additions),
        "parent_market_prefix": copy.deepcopy(parent_action.get("market") or []),
        "parent": dict(PARENT._LAST_DIAGNOSTIC.get(seat, {})),
    }
    return action


e774a_agent = agent
