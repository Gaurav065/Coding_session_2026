"""E749A: six-trace top-programme consensus with visible-state execution guards.

The 719-node physical and non-SELL programme is exactly identical across six
attributed NIklitaCheporev public episodes spanning two submissions.  Runtime
edges use only the visible observation: live hand count, weeds, shed/cargo,
cash, market inventory/prices and unlocked shops.  No replay observation,
identity, seed, reward or future state is read.

This is a research candidate, not a submission artifact.
"""

from __future__ import annotations

import importlib.util
import math
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "artifacts/e706_top10_tapes/episode_101408728_seat1.py"
SPEC = importlib.util.spec_from_file_location("e749a_attributed_niklita_trace", SOURCE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import E749 consensus source: {SOURCE_PATH}")
SOURCE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SOURCE
SPEC.loader.exec_module(SOURCE)

MAX_STEPS = 720
MAX_MARKET_ORDERS = 10
SHED_CAPACITY = 100
WEED_REPLAY_STEPS = 8
I0 = 10000
SEED_COST = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COST = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
LAND_COST = (1000, 2000, 4000)
PRODUCTS = (
    "WHEAT",
    "CARROT",
    "TOMATO",
    "STRAWBERRY",
    "MELON",
    "EGG",
    "MILK",
    "WOOL",
    "FERTILIZER",
)
SHOP_PRODUCTS = {
    "BAKERY": ("EGG", "WHEAT"),
    "PIZZA_SHOP": ("MILK", "TOMATO", "WHEAT"),
    "BRUNCH_SPOT": ("EGG", "WHEAT", "STRAWBERRY"),
    "YARN_STORE": ("WOOL",),
    "ICE_CREAM_SHOP": ("STRAWBERRY", "MILK", "WHEAT"),
    "PET_CAFE": ("CARROT",),
    "SMOOTHIE_SHOP": ("STRAWBERRY", "MILK"),
    "FARMERS_MARKET": ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY"),
}

# base, scale, below function/target, above function/target; engine 1.32.7.
PARAMS = {
    "WHEAT": (25, 400, "sqrt", 0.80, "log", 0.20),
    "CARROT": (35, 450, "hinge", 1.00, "sqrt", 0.70),
    "TOMATO": (60, 200, "hinge", 0.40, "sqrt", 0.60),
    "STRAWBERRY": (120, 100, "sqrt", 0.70, "linear", 1.60),
    "MELON": (250, 300, "log", 0.20, "sq", 3.60),
    "EGG": (50, 332, "hinge", 0.40, "log", 0.20),
    "MILK": (160, 122, "sqrt", 0.60, "linear", 1.60),
    "WOOL": (200, 105, "log", 0.20, "sq", 3.20),
    "FERTILIZER": (100, 200, "linear", 0.40, "linear", 0.40),
}

PROVENANCE = {
    "team": "NIklitaCheporev",
    "episodes": (101384251, 101377363, 101373123, 101422155, 101408728, 101399763),
    "submissions": (55817147, 55826943),
    "consensus": "719/719 physical and 719/719 non-SELL nodes exact",
    "source_episode": 101408728,
    "source_action_sha256": "7c9c30df14a8dd4b4420e913d52d2d86a3624263cace5c71fa2a0c1088a46134",
}


@dataclass(frozen=True)
class StepNode:
    step: int
    day: int
    hour: int
    phase: str
    expected_hands: int
    non_sell_orders: tuple[tuple[Any, ...], ...]
    preserve_occupancy_programme: bool
    shop_conditioned_liquidation: bool


def _phase(day: int) -> str:
    if day <= 2:
        return "opening"
    if day <= 8:
        return "formation"
    if day <= 18:
        return "productive_scale"
    if day <= 25:
        return "demand_conversion"
    if day <= 28:
        return "harvest"
    return "liquidation"


def _compile_node(step: int) -> StepNode:
    source = SOURCE.TRACE_ACTIONS[min(step, len(SOURCE.TRACE_ACTIONS) - 1)] or {}
    non_sell = tuple(
        tuple(order)
        for order in source.get("market") or []
        if not (isinstance(order, list) and order and order[0] == "SELL")
    )
    day, hour = divmod(step, 24)
    return StepNode(
        step=step,
        day=day,
        hour=hour,
        phase=_phase(day),
        expected_hands=len(source.get("hands") or []),
        non_sell_orders=non_sell,
        preserve_occupancy_programme=True,
        shop_conditioned_liquidation=True,
    )


STEP_NETWORK: tuple[StepNode, ...] = tuple(_compile_node(step) for step in range(MAX_STEPS))
_STATE: dict[int, dict[str, Any]] = {0: {}, 1: {}}
_LAST_DIAGNOSTIC: dict[int, dict[str, Any]] = {0: {}, 1: {}}


def _get(value: Any, key: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(key, default)
    getter = getattr(value, "get", None)
    if callable(getter):
        return getter(key, default)
    return getattr(value, key, default)


def _seat(obs: Any) -> int:
    return 1 if int(_get(obs, "player", 0) or 0) == 1 else 0


def _farm(obs: Any, seat: int) -> Any:
    farms = list(_get(obs, "farms", []) or [])
    return farms[seat] if seat < len(farms) else {}


def _private(obs: Any) -> Any:
    return _get(obs, "private", {}) or {}


def _copy_action(action: Any) -> dict[str, Any]:
    action = action if isinstance(action, dict) else {}
    return {
        "farmer": list(action.get("farmer") or ["PASS"]),
        "hands": [list(command or ["PASS"]) for command in action.get("hands") or []],
        "market": [list(order) for order in action.get("market") or []],
    }


def _source_action(step: int) -> dict[str, Any]:
    index = min(max(0, int(step)), len(SOURCE.TRACE_ACTIONS) - 1)
    return _copy_action(SOURCE.TRACE_ACTIONS[index])


def _align_hands(action: dict[str, Any], obs: Any, seat: int) -> dict[str, Any]:
    action = _copy_action(action)
    expected = len(_get(_farm(obs, seat), "hands", []) or [])
    hands = list(action.get("hands") or [])
    if len(hands) < expected:
        hands.extend([["PASS"] for _ in range(expected - len(hands))])
    action["hands"] = [list(command or ["PASS"]) for command in hands[:expected]]
    return action


def _tile_at(farm: Any, position: Any) -> Any:
    try:
        x, y = int(position[0]), int(position[1])
        return (_get(farm, "tiles", []) or [])[y][x]
    except (IndexError, TypeError, ValueError):
        return "LOCKED"


def _weed_repair(
    obs: Any, action: dict[str, Any], step: int, seat: int, state: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, int]]:
    action = _align_hands(action, obs, seat)
    farm = _farm(obs, seat)
    positions = [_get(farm, "farmer"), *list(_get(farm, "hands", []) or [])]
    commands = [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]
    active = state.setdefault("weed_transactions", {})
    telemetry = {"started": 0, "replayed": 0, "completed": 0}

    for actor, transaction in list(active.items()):
        index = int(actor)
        if index >= len(commands):
            active.pop(actor, None)
            continue
        age = step - int(transaction["start"])
        if age == 1:
            commands[index] = list(transaction["intended"])
            telemetry["replayed"] += 1
        elif 2 <= age <= 1 + WEED_REPLAY_STEPS:
            prior = _source_action(step - 1)
            commands[index] = (
                list(prior.get("farmer") or ["PASS"])
                if index == 0
                else list((prior.get("hands") or [])[index - 1])
                if index - 1 < len(prior.get("hands") or [])
                else ["PASS"]
            )
            telemetry["replayed"] += 1
        else:
            active.pop(actor, None)
            telemetry["completed"] += 1

    for index, (position, intended) in enumerate(zip(positions, commands)):
        if index in active or not isinstance(intended, list) or not intended:
            continue
        if intended[0] not in {"BUILD_PASTURE", "BUILD_COOP", "PLANT"}:
            continue
        tile = _tile_at(farm, position)
        if not isinstance(tile, dict) or tile.get("kind") != "WEED":
            continue
        active[index] = {"start": step, "intended": list(intended)}
        commands[index] = ["DIG"]
        telemetry["started"] += 1

    action["farmer"] = commands[0] if commands else ["PASS"]
    action["hands"] = commands[1:]
    return _align_hands(action, obs, seat), telemetry


def _shape(function: str, value: float, scale: float) -> float:
    value = max(0.0, value)
    if function == "linear":
        return value
    if function == "sq":
        return value * value
    if function == "sqrt":
        return math.sqrt(value)
    if function == "log":
        return math.log1p(value)
    if function == "hinge":
        ratio = value / scale
        return ratio + 8.0 * max(0.0, ratio - 1.0) ** 2
    return value


def _price(item: str, inventory: int) -> int:
    base, scale, below_function, below_target, above_function, above_target = PARAMS[item]
    if inventory < I0:
        amplitude = below_target * base / _shape(below_function, scale, scale)
        value = base + amplitude * _shape(below_function, I0 - inventory, scale)
    else:
        amplitude = above_target * base / _shape(above_function, scale, scale)
        value = base - amplitude * _shape(above_function, inventory - I0, scale)
    return max(1, round(value))


def _contested_value(item: str, inventory: int, quantity: int) -> float:
    quantity = max(1, min(int(quantity), 60))
    first = sum(_price(item, inventory + offset) for offset in range(quantity))
    second = sum(_price(item, inventory + quantity + offset) for offset in range(quantity))
    return float(first - second)


def _project_shed(
    obs: Any, seat: int, action: dict[str, Any]
) -> tuple[dict[str, int], dict[str, int]]:
    farm = _farm(obs, seat)
    private = _private(obs)
    shed = Counter(
        {
            str(item): max(0, int(quantity or 0))
            for item, quantity in dict(_get(private, "shed", {}) or {}).items()
        }
    )
    inventories = list(_get(private, "inventories", []) or [])
    positions = [_get(farm, "farmer"), *list(_get(farm, "hands", []) or [])]
    commands = [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]
    pickup_reserve: Counter[str] = Counter()
    board_size = len(_get(farm, "tiles", []) or []) or 10
    half = board_size // 2
    cross = {(half - 1, half - 1), (half, half - 1), (half - 1, half), (half, half)}
    for index, (position, command) in enumerate(zip(positions, commands)):
        if not isinstance(command, list) or not command:
            continue
        try:
            point = (int(position[0]), int(position[1]))
        except (TypeError, ValueError):
            continue
        if point not in cross:
            continue
        if command[0] == "PICKUP" and len(command) >= 2:
            item = str(command[1])
            quantity = max(1, int(command[2])) if len(command) >= 3 else 1
            taken = min(quantity, shed[item])
            shed[item] -= taken
            pickup_reserve[item] += taken
        elif command[0] == "DROP" and index < len(inventories):
            for item, quantity in dict(inventories[index] or {}).items():
                shed[str(item)] += max(0, int(quantity or 0))
    return dict(shed), dict(pickup_reserve)


def _cap_sales(
    obs: Any, seat: int, action: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    action = _copy_action(action)
    available, pickup_reserve = _project_shed(obs, seat, action)
    capped = []
    reductions: Counter[str] = Counter()
    for raw in action.get("market") or []:
        order = list(raw)
        if len(order) >= 3 and order[0] == "SELL" and str(order[1]) in PRODUCTS:
            item = str(order[1])
            requested = max(0, int(order[2] or 0))
            quantity = min(requested, max(0, int(available.get(item, 0))))
            available[item] = max(0, int(available.get(item, 0)) - quantity)
            reductions[item] += requested - quantity
            if quantity:
                order[2] = quantity
                capped.append(order)
            continue
        capped.append(order)
    action["market"] = capped[:MAX_MARKET_ORDERS]
    return action, {"reductions": dict(reductions), "pickup_reserve": pickup_reserve}


def _assign_sell_slots(obs: Any, action: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    orders = [list(order) for order in action.get("market") or []]
    positions = [
        index
        for index, order in enumerate(orders)
        if len(order) >= 3 and order[0] == "SELL" and str(order[1]) in PRODUCTS
    ]
    if len(positions) < 2:
        return action, False
    market = _get(obs, "market", {}) or {}
    inventory = _get(market, "inventory", {}) or {}

    def score(order: list[Any]) -> tuple[float, int, str]:
        item = str(order[1])
        quantity = max(1, int(order[2] or 1))
        current = int(_get(inventory, item, I0) or I0)
        return _contested_value(item, current, quantity), _price(item, current), item

    original = [orders[index] for index in positions]
    ranked = sorted(original, key=score, reverse=True)
    if original == ranked:
        return action, False
    for position, order in zip(positions, ranked):
        orders[position] = order
    changed = _copy_action(action)
    changed["market"] = orders
    return changed, True


def _fib(index: int) -> int:
    a, b = 1, 1
    for _ in range(max(0, int(index))):
        a, b = b, a + b
    return a


def _fund_market(
    obs: Any, seat: int, action: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, int]]:
    """Suppress only units the visible own-side sequential ledger cannot fund."""

    farm = _farm(obs, seat)
    cash = float(_get(farm, "money", 0) or 0)
    hires = max(0, int(_get(farm, "hires_today", 0) or 0))
    unlocked = len(list(_get(farm, "unlocked_quadrants", []) or []))
    shed, _ = _project_shed(obs, seat, action)
    shed_units = sum(shed.values())
    market = _get(obs, "market", {}) or {}
    inventory = {
        item: int(_get(_get(market, "inventory", {}) or {}, item, I0) or I0)
        for item in PRODUCTS
    }
    output = []
    stopped: Counter[str] = Counter()
    for raw in (action.get("market") or [])[:MAX_MARKET_ORDERS]:
        order = list(raw)
        if not order:
            continue
        op = str(order[0])
        item = str(order[1]) if len(order) >= 2 else ""
        if op == "SELL" and item in PRODUCTS and len(order) >= 3:
            requested = max(0, int(order[2] or 0))
            quantity = min(requested, max(0, int(shed.get(item, 0))))
            proceeds = 0
            for _ in range(quantity):
                proceeds += _price(item, inventory[item])
                inventory[item] += 1
            shed[item] = max(0, int(shed.get(item, 0)) - quantity)
            shed_units -= quantity
            cash += proceeds
            if quantity:
                order[2] = quantity
                output.append(order)
            stopped[op] += requested - quantity
            continue
        if op == "HIRE":
            cost = _fib(hires)
            if cash >= cost:
                cash -= cost
                hires += 1
                output.append(order)
            else:
                stopped[op] += 1
            continue
        if op == "BUY_LAND":
            index = max(0, unlocked - 1)
            cost = LAND_COST[index] if index < len(LAND_COST) else 10**9
            if cash >= cost and index < len(LAND_COST):
                cash -= cost
                unlocked += 1
                output.append(order)
            else:
                stopped[op] += 1
            continue
        if op not in {"BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL"} or len(order) < 3:
            output.append(order)
            continue
        requested = max(0, int(order[2] or 0))
        quantity = 0
        for _ in range(requested):
            if op == "BUY_SEED":
                cost = SEED_COST.get(item, 10**9)
                needs_shed = False
            elif op == "BUY_ANIMAL":
                cost = ANIMAL_COST.get(item, 10**9)
                needs_shed = True
            else:
                cost = _price(item, inventory.get(item, I0) - 1)
                needs_shed = True
            if cash < cost or (needs_shed and shed_units >= SHED_CAPACITY):
                break
            cash -= cost
            quantity += 1
            if needs_shed:
                shed_units += 1
            if op == "BUY_PRODUCT":
                inventory[item] -= 1
        if quantity:
            order[2] = quantity
            output.append(order)
        stopped[op] += requested - quantity
    changed = _copy_action(action)
    changed["market"] = output[:MAX_MARKET_ORDERS]
    return changed, dict(stopped)


def _shop_signal(obs: Any, step: int) -> dict[str, Any]:
    town = _get(obs, "town", {}) or {}
    shops = tuple(str(value) for value in (_get(town, "unlocked_shops", []) or []))
    demand: Counter[str] = Counter()
    if step % 4 == 0:
        for shop in shops:
            demand.update(SHOP_PRODUCTS.get(shop, ()))
    return {"shops": shops, "immediate_demand": dict(demand)}


def agent(obs: Any, configuration: Any = None) -> dict[str, Any]:
    del configuration
    seat = _seat(obs)
    step = max(0, min(MAX_STEPS - 1, int(_get(obs, "step", 0) or 0)))
    state = _STATE[seat]
    if step == 0 or step <= int(state.get("last_step", -1)):
        state = {"last_step": -1, "weed_transactions": {}}
        _STATE[seat] = state
    state["last_step"] = step
    node = STEP_NETWORK[step]

    action = _source_action(step)
    action, weed = _weed_repair(obs, action, step, seat, state)
    action, cap = _cap_sales(obs, seat, action)
    action, sell_reordered = _assign_sell_slots(obs, action)
    action, funding_stops = _fund_market(obs, seat, action)
    action = _align_hands(action, obs, seat)
    shop = _shop_signal(obs, step)
    _LAST_DIAGNOSTIC[seat] = {
        "step": step,
        "node": node,
        "weed": weed,
        "sale_cap": cap,
        "sell_reordered": sell_reordered,
        "funding_stops": funding_stops,
        "shop_signal": shop,
        "active_weed_transactions": len(state.get("weed_transactions", {})),
    }
    return action


e749a_agent = agent
