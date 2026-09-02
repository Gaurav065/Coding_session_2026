"""E773A: conserved pasture bundles aligned to visible shop demand.

E766 remains the complete guarded programme.  This wrapper may relabel only
pre-registered route-compatible COW/SHEEP transactions and conserves the
source animal-product sale budget at existing sale nodes.
"""

from __future__ import annotations

import copy
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

import e766a_universal_kenjo_medoid as PARENT

BASE = PARENT.BASE
ENGINE = PARENT.ENGINE
MAX_STEPS = ENGINE.MAX_STEPS
STEP_NETWORK = ENGINE.STEP_NETWORK
ANIMAL_PRODUCTS = ("MILK", "WOOL")
BASE_PRICE = {"MILK": 160, "WOOL": 200}
MAX_COW_TO_SHEEP = 3
MAX_SHEEP_TO_COW = 1

# Every bundle uses a source PASTURE and identical route/service geometry.
# Replacing the animal token at all listed nodes preserves the transaction.
BUNDLES: dict[str, dict[str, Any]] = {
    "cow88": {
        "purchase_step": 88,
        "steps": (88, 92, 95),
        "source": "COW",
        "quantity": 1,
    },
    "cow150": {
        "purchase_step": 150,
        "steps": (150, 152, 153, 156),
        "source": "COW",
        "quantity": 2,
    },
    "cow169": {
        "purchase_step": 169,
        "steps": (169, 175, 177),
        "source": "COW",
        "quantity": 1,
    },
    "cow176": {
        "purchase_step": 176,
        "steps": (176, 180, 183),
        "source": "COW",
        "quantity": 1,
    },
    "sheep313": {
        "purchase_step": 313,
        "steps": (313, 329, 333),
        "source": "SHEEP",
        "quantity": 1,
    },
}
PURCHASE_BUNDLES = {
    int(bundle["purchase_step"]): name for name, bundle in BUNDLES.items()
}
STEP_BUNDLES = {
    step: name
    for name, bundle in BUNDLES.items()
    for step in bundle["steps"]
}

PROVENANCE = {
    **PARENT.PROVENANCE,
    "owned_network": "visible-demand conserved COW/SHEEP pasture transactions",
    "parent_sha256": "b66a4acb25695ce7e04b4a9a57c60543926fdc3bd2e85fc827c82bc80d86dc45",
    "pressure": {
        "wool": "2*YARN_STORE + visible_WOOL_price/200",
        "dairy": "PIZZA+ICE_CREAM+SMOOTHIE + visible_MILK_price/160",
        "minimum_gap": 1.0,
    },
    "substitution_caps": {
        "cow_to_sheep": MAX_COW_TO_SHEEP,
        "sheep_to_cow": MAX_SHEEP_TO_COW,
    },
    "immutable": "animal count, pasture/land/hands, routes, feed, crops, sale nodes/units/slots",
}

_STATE: dict[int, dict[str, Any]] = {0: {}, 1: {}}
_LAST_DIAGNOSTIC: dict[int, dict[str, Any]] = {0: {}, 1: {}}


def _reset(seat: int) -> dict[str, Any]:
    state: dict[str, Any] = {
        "last_step": -1,
        "assignments": {},
        "cow_to_sheep": 0,
        "sheep_to_cow": 0,
        "decision_rows": [],
    }
    _STATE[seat] = state
    return state


def _pressure(obs: Any) -> dict[str, float]:
    town = ENGINE._get(obs, "town", {}) or {}
    shops = Counter(
        str(value)
        for value in (ENGINE._get(town, "unlocked_shops", []) or [])
    )
    market = ENGINE._get(obs, "market", {}) or {}
    prices = ENGINE._get(market, "prices", {}) or {}
    milk_price = float(ENGINE._get(prices, "MILK", BASE_PRICE["MILK"]) or 0)
    wool_price = float(ENGINE._get(prices, "WOOL", BASE_PRICE["WOOL"]) or 0)
    wool = 2.0 * shops["YARN_STORE"] + wool_price / BASE_PRICE["WOOL"]
    dairy = (
        shops["PIZZA_SHOP"]
        + shops["ICE_CREAM_SHOP"]
        + shops["SMOOTHIE_SHOP"]
        + milk_price / BASE_PRICE["MILK"]
    )
    return {
        "wool": wool,
        "dairy": dairy,
        "gap": wool - dairy,
        "milk_price": milk_price,
        "wool_price": wool_price,
    }


def _assign_bundle(obs: Any, seat: int, name: str) -> str:
    state = _STATE[seat]
    assignments = state["assignments"]
    if name in assignments:
        return str(assignments[name])
    bundle = BUNDLES[name]
    source = str(bundle["source"])
    quantity = int(bundle["quantity"])
    pressure = _pressure(obs)
    target = source
    if (
        source == "COW"
        and pressure["gap"] >= 1.0
        and int(state["cow_to_sheep"]) + quantity <= MAX_COW_TO_SHEEP
    ):
        target = "SHEEP"
        state["cow_to_sheep"] = int(state["cow_to_sheep"]) + quantity
    elif (
        source == "SHEEP"
        and pressure["gap"] <= -1.0
        and int(state["sheep_to_cow"]) + quantity <= MAX_SHEEP_TO_COW
    ):
        target = "COW"
        state["sheep_to_cow"] = int(state["sheep_to_cow"]) + quantity
    assignments[name] = target
    state["decision_rows"].append(
        {
            "bundle": name,
            "source": source,
            "target": target,
            "quantity": quantity,
            "pressure": pressure,
        }
    )
    return target


def _replace_bundle(action: dict[str, Any], step: int, seat: int) -> dict[str, Any]:
    name = STEP_BUNDLES.get(int(step))
    if name is None:
        return action
    bundle = BUNDLES[name]
    source = str(bundle["source"])
    target = str(_STATE[seat]["assignments"].get(name, source))
    if target == source:
        return action
    changed = ENGINE._copy_action(action)
    for command in [changed["farmer"], *changed["hands"]]:
        if (
            command
            and command[0] in {"PICKUP", "PLACE"}
            and len(command) >= 2
            and str(command[1]) == source
        ):
            command[1] = target
    for order in changed["market"]:
        if (
            order
            and order[0] == "BUY_ANIMAL"
            and len(order) >= 2
            and str(order[1]) == source
        ):
            order[1] = target
    return changed


def _sale_revenue(item: str, inventory: int, quantity: int) -> int:
    return sum(ENGINE._price(item, inventory + offset) for offset in range(quantity))


def _reallocate_animal_sales(
    obs: Any, seat: int, action: dict[str, Any]
) -> dict[str, Any]:
    state = _STATE[seat]
    if int(state["cow_to_sheep"]) + int(state["sheep_to_cow"]) == 0:
        return action
    positions = [
        index
        for index, order in enumerate(action.get("market") or [])
        if len(order) >= 3 and order[0] == "SELL" and str(order[1]) in ANIMAL_PRODUCTS
    ]
    if not positions:
        return action
    changed = ENGINE._copy_action(action)
    available, _ = ENGINE._project_shed(obs, seat, changed)
    market = ENGINE._get(obs, "market", {}) or {}
    raw_inventory = ENGINE._get(market, "inventory", {}) or {}
    inventory = {
        item: int(ENGINE._get(raw_inventory, item, ENGINE.I0) or ENGINE.I0)
        for item in ANIMAL_PRODUCTS
    }
    pressure = _pressure(obs)
    for position in positions:
        order = changed["market"][position]
        original = str(order[1])
        requested = max(0, int(order[2] or 0))
        candidates = []
        for item in ANIMAL_PRODUCTS:
            quantity = min(requested, max(0, int(available.get(item, 0))))
            revenue = _sale_revenue(item, inventory[item], quantity)
            demand_score = pressure["dairy"] if item == "MILK" else pressure["wool"]
            candidates.append(
                (revenue, quantity, demand_score, item == original, item)
            )
        _, quantity, _, _, selected = max(candidates)
        order[1] = selected
        available[selected] = max(0, int(available.get(selected, 0)) - quantity)
        inventory[selected] += quantity
    return changed


def _source_action(step: int, obs: Any, seat: int) -> dict[str, Any]:
    action = PARENT._source_action(step)
    action = _replace_bundle(action, step, seat)
    return _reallocate_animal_sales(obs, seat, action)


@contextmanager
def _installed_source(obs: Any, seat: int) -> Iterator[None]:
    original = ENGINE._source_action
    ENGINE._source_action = lambda step: _source_action(step, obs, seat)
    try:
        yield
    finally:
        ENGINE._source_action = original


def agent(obs: Any, configuration: Any = None) -> dict[str, Any]:
    seat = ENGINE._seat(obs)
    step = max(0, min(MAX_STEPS - 1, int(ENGINE._get(obs, "step", 0) or 0)))
    state = _STATE[seat]
    if not state or step == 0 or step < int(state.get("last_step", -1)):
        state = _reset(seat)
    bundle_name = PURCHASE_BUNDLES.get(step)
    if bundle_name is not None:
        _assign_bundle(obs, seat, bundle_name)
    with _installed_source(obs, seat):
        action = BASE.agent(obs, configuration)
    state["last_step"] = step
    state["last_action"] = copy.deepcopy(action)
    _LAST_DIAGNOSTIC[seat] = {
        "step": step,
        "assignments": dict(state["assignments"]),
        "cow_to_sheep": int(state["cow_to_sheep"]),
        "sheep_to_cow": int(state["sheep_to_cow"]),
        "pressure": _pressure(obs),
        "decisions": list(state["decision_rows"]),
        "base": dict(ENGINE._LAST_DIAGNOSTIC.get(seat, {})),
    }
    return action


e773a_agent = agent
