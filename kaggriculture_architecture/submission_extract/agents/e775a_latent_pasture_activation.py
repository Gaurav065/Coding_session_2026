"""E775A: activate a fully serviced latent pasture with one guarded bundle."""

from __future__ import annotations

import copy
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

import e774a_terminal_animal_frontier as PARENT

ENGINE = PARENT.ENGINE
STEP_NETWORK = PARENT.STEP_NETWORK
ACTIVATION_STEP = 313
DELIVERY_STEPS = (314, 315, 316, 317)
TARGET_TILE = (5, 3)
ANIMALS = ("COW", "SHEEP")
ANIMAL_COST = {"COW": 400, "SHEEP": 500}
EXTRA_HIRE_COST = 89  # The registered fourth hire when hires_today == 7.

PROVENANCE = {
    **PARENT.PROVENANCE,
    "owned_structural_bundle": (
        "one extra shop-selected animal and hand delivered into the already serviced "
        "empty pasture at (5,3)"
    ),
    "parent_sha256": "bc446060cb4ca57e31cc7583f0da16e92c31cb0818d84435483f7523282f4b3c",
    "activation_step": ACTIVATION_STEP,
    "delivery_steps": DELIVERY_STEPS,
    "target_tile": TARGET_TILE,
    "runtime_prohibitions": (
        "seed, opponent identity, replay identity, outcome, future shops"
    ),
}

_STATE: dict[int, dict[str, Any]] = {0: {}, 1: {}}
_LAST_DIAGNOSTIC: dict[int, dict[str, Any]] = {0: {}, 1: {}}


def _reset(seat: int) -> dict[str, Any]:
    state: dict[str, Any] = {
        "last_step": -1,
        "active": False,
        "animal": None,
        "cancelled": False,
        "cancel_reason": None,
        "intervention_steps": [],
    }
    _STATE[seat] = state
    return state


def _farm(obs: Any, seat: int) -> Any:
    farms = list(ENGINE._get(obs, "farms", []) or [])
    return farms[seat] if seat < len(farms) else {}


def _private(obs: Any) -> Any:
    return ENGINE._get(obs, "private", {}) or {}


def _tile(farm: Any, x: int, y: int) -> Any:
    tiles = list(ENGINE._get(farm, "tiles", []) or [])
    if y < 0 or y >= len(tiles):
        return None
    row = list(tiles[y] or [])
    return row[x] if 0 <= x < len(row) else None


def _is_empty_pasture(tile: Any) -> bool:
    return isinstance(tile, dict) and tile.get("kind") == "PASTURE" and "animal" not in tile


def _spawn_geometry_matches(farm: Any) -> bool:
    positions = [
        tuple(ENGINE._get(farm, "farmer", ()) or ()),
        *[tuple(value or ()) for value in (ENGINE._get(farm, "hands", []) or [])],
    ]
    cross = Counter(position for position in positions if position in {(4, 4), (5, 4), (4, 5), (5, 5)})
    return (
        len(positions) == 8
        and int(ENGINE._get(farm, "hires_today", 0) or 0) == 7
        and cross == Counter({(4, 4): 2, (5, 4): 2, (4, 5): 2, (5, 5): 2})
    )


def _activation_candidate(
    obs: Any, seat: int, action: dict[str, Any]
) -> tuple[int, str] | None:
    farm = _farm(obs, seat)
    private = _private(obs)
    if not _is_empty_pasture(_tile(farm, *TARGET_TILE)):
        return None
    if not _spawn_geometry_matches(farm):
        return None
    if len(action.get("market") or []) >= ENGINE.MAX_MARKET_ORDERS:
        return None
    purchases = [
        (index, str(order[1]))
        for index, order in enumerate(action.get("market") or [])
        if len(order) >= 3
        and order[0] == "BUY_ANIMAL"
        and str(order[1]) in ANIMALS
        and int(order[2] or 0) == 1
    ]
    if len(purchases) != 1:
        return None
    if sum(order == ["HIRE"] for order in action.get("market") or []) != 3:
        return None
    purchase_index, animal = purchases[0]
    money = float(ENGINE._get(farm, "money", 0) or 0)
    if money < ANIMAL_COST[animal] + EXTRA_HIRE_COST + 1_000:
        return None
    shed = dict(ENGINE._get(private, "shed", {}) or {})
    if sum(max(0, int(value or 0)) for value in shed.values()) > 90:
        return None
    return purchase_index, animal


def _activate(
    obs: Any, seat: int, action: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    selected = _activation_candidate(obs, seat, action)
    if selected is None:
        return action
    purchase_index, animal = selected
    changed = ENGINE._copy_action(action)
    changed["market"][purchase_index][2] = 2
    changed["market"].append(["HIRE"])
    state["active"] = True
    state["animal"] = animal
    state["intervention_steps"].append(ACTIVATION_STEP)
    return changed


def _cancel(state: dict[str, Any], reason: str) -> None:
    state["active"] = False
    state["cancelled"] = True
    state["cancel_reason"] = reason


def _delivery_command(
    obs: Any, seat: int, step: int, action: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    if not state.get("active") or step not in DELIVERY_STEPS:
        return action
    farm = _farm(obs, seat)
    hands = list(ENGINE._get(farm, "hands", []) or [])
    inventories = list(ENGINE._get(_private(obs), "inventories", []) or [])
    commands = list(action.get("hands") or [])
    if len(hands) != 11 or len(commands) != 11 or len(inventories) < 12:
        _cancel(state, "missing appended hand")
        return action
    if commands[-1] != ["PASS"]:
        _cancel(state, "parent claimed appended hand")
        return action
    animal = str(state["animal"])
    position = tuple(hands[-1] or ())
    inventory = dict(inventories[11] or {})
    expected = {
        314: ((5, 5), {}, ["PICKUP", animal, 1]),
        315: ((5, 5), {animal: 1}, ["NORTH"]),
        316: ((5, 4), {animal: 1}, ["NORTH"]),
        317: ((5, 3), {animal: 1}, ["PLACE", animal]),
    }
    expected_position, expected_inventory, command = expected[step]
    if position != expected_position or inventory != expected_inventory:
        _cancel(state, f"visible delivery mismatch at step {step}")
        return action
    if step == 317 and not _is_empty_pasture(_tile(farm, *TARGET_TILE)):
        _cancel(state, "target pasture no longer empty")
        return action
    changed = ENGINE._copy_action(action)
    changed["hands"][-1] = command
    state["intervention_steps"].append(step)
    return changed


def agent(obs: Any, configuration: Any = None) -> dict[str, Any]:
    seat = ENGINE._seat(obs)
    step = max(0, min(ENGINE.MAX_STEPS - 1, int(ENGINE._get(obs, "step", 0) or 0)))
    state = _STATE[seat]
    if not state or step == 0 or step <= int(state.get("last_step", -1)):
        state = _reset(seat)
    parent_action = PARENT.agent(obs, configuration)
    action = parent_action
    if step == ACTIVATION_STEP:
        action = _activate(obs, seat, action, state)
    else:
        action = _delivery_command(obs, seat, step, action, state)
    state["last_step"] = step
    _LAST_DIAGNOSTIC[seat] = {
        "step": step,
        "active": bool(state["active"]),
        "animal": state["animal"],
        "cancelled": bool(state["cancelled"]),
        "cancel_reason": state["cancel_reason"],
        "intervention_steps": list(state["intervention_steps"]),
        "parent": copy.deepcopy(PARENT._LAST_DIAGNOSTIC.get(seat, {})),
    }
    return action


e775a_agent = agent
