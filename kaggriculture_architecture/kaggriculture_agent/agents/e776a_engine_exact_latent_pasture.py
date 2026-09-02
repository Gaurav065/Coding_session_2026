"""E776A: engine-exact delivery repair for E775's unexecuted pasture bundle."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

import e775a_latent_pasture_activation as PARENT

ENGINE = PARENT.ENGINE
STEP_NETWORK = PARENT.STEP_NETWORK
ACTIVATION_STEP = PARENT.ACTIVATION_STEP
DELIVERY_STEPS = (314, 315, 316)
TARGET_TILE = PARENT.TARGET_TILE
FINAL_EXECUTABLE_STEP = 718


PROVENANCE = {
    **PARENT.PROVENANCE,
    "owned_delivery_repair": (
        "project hire spawn after source unit actions: (5,4) pickup, north, "
        "(5,3) place"
    ),
    "parent_sha256": "4abb721b60f8928683ce038903f616cc618ce9a547c7a1f520b1fb81a7398bc6",
    "delivery_steps": DELIVERY_STEPS,
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


def _tile(farm: Any, x: int, y: int) -> Any:
    tiles = list(ENGINE._get(farm, "tiles", []) or [])
    if y < 0 or y >= len(tiles):
        return None
    row = list(tiles[y] or [])
    return row[x] if 0 <= x < len(row) else None


def _cancel(state: dict[str, Any], reason: str) -> None:
    state["active"] = False
    state["cancelled"] = True
    state["cancel_reason"] = reason


def _correct_delivery(
    obs: Any, seat: int, step: int, action: dict[str, Any], state: dict[str, Any]
) -> dict[str, Any]:
    if not state.get("active") or step not in DELIVERY_STEPS:
        return action
    farm = _farm(obs, seat)
    private = ENGINE._get(obs, "private", {}) or {}
    hands = list(ENGINE._get(farm, "hands", []) or [])
    inventories = list(ENGINE._get(private, "inventories", []) or [])
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
        314: ((5, 4), {}, ["PICKUP", animal, 1]),
        315: ((5, 4), {animal: 1}, ["NORTH"]),
        316: ((5, 3), {animal: 1}, ["PLACE", animal]),
    }
    expected_position, expected_inventory, command = expected[step]
    if position != expected_position or inventory != expected_inventory:
        _cancel(state, f"visible corrected-delivery mismatch at step {step}")
        return action
    if step == 316 and not PARENT._is_empty_pasture(_tile(farm, *TARGET_TILE)):
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
    if step == ACTIVATION_STEP:
        parent_diagnostic = PARENT._LAST_DIAGNOSTIC.get(seat, {})
        if bool(parent_diagnostic.get("active")):
            state["active"] = True
            state["animal"] = parent_diagnostic.get("animal")
            state["intervention_steps"].append(ACTIVATION_STEP)
        action = parent_action
    else:
        action = _correct_delivery(obs, seat, step, parent_action, state)

    # Final-turn sweep: physical COLLECT_FERTILIZER actions resolve before market
    # orders, so one extra order can cash out fertilizer created on the last turn.
    # Overspecifying is safe: SELL stops when the shed is empty.
    if step == FINAL_EXECUTABLE_STEP and len(action.get("market") or []) < ENGINE.MAX_MARKET_ORDERS:
        action = ENGINE._copy_action(action)
        action["market"].append(["SELL", "FERTILIZER", 100])

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


e776a_agent = agent
