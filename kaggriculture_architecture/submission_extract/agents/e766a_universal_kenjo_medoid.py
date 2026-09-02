"""E766A: current Kenjo medoid as the complete guarded programme basis."""

from __future__ import annotations

import importlib.util
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / "agents"
if str(AGENTS) not in sys.path:
    sys.path.insert(0, str(AGENTS))

import e750a_place_funding_repair as BASE

SOURCE_PATH = ROOT / "artifacts/e751_current_top10_tapes/episode_102192548_seat1.py"
SPEC = importlib.util.spec_from_file_location("e766a_kenjo_medoid_source", SOURCE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot import E766 medoid source: {SOURCE_PATH}")
SOURCE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = SOURCE
SPEC.loader.exec_module(SOURCE)

ENGINE = BASE.PARENT
SOURCE_STEPS = len(SOURCE.TRACE_ACTIONS)
MAX_STEPS = ENGINE.MAX_STEPS
STEP_NETWORK = ENGINE.STEP_NETWORK


def _source_action(step: int) -> dict[str, Any]:
    index = min(max(0, int(step)), SOURCE_STEPS - 1)
    return ENGINE._copy_action(SOURCE.TRACE_ACTIONS[index])


def _physical(action: dict[str, Any]) -> dict[str, Any]:
    return {
        "farmer": list(action.get("farmer") or ["PASS"]),
        "hands": [list(command or ["PASS"]) for command in action.get("hands") or []],
    }


def _non_sell(action: dict[str, Any]) -> list[list[Any]]:
    return [
        list(order)
        for order in action.get("market") or []
        if not (isinstance(order, list) and order and order[0] == "SELL")
    ]


FULL_DIFFERENCE_STEPS = tuple(
    step
    for step in range(SOURCE_STEPS)
    if ENGINE._source_action(step) != _source_action(step)
)
PHYSICAL_DIFFERENCE_STEPS = tuple(
    step
    for step in range(SOURCE_STEPS)
    if _physical(ENGINE._source_action(step)) != _physical(_source_action(step))
)
NON_SELL_DIFFERENCE_STEPS = tuple(
    step
    for step in range(SOURCE_STEPS)
    if _non_sell(ENGINE._source_action(step)) != _non_sell(_source_action(step))
)
if (
    FULL_DIFFERENCE_STEPS[0] != 72
    or NON_SELL_DIFFERENCE_STEPS[0] != 72
    or PHYSICAL_DIFFERENCE_STEPS[0] != 86
):
    raise RuntimeError("E766 source does not match the frozen 72/86 boundary")


@contextmanager
def _installed_source() -> Iterator[None]:
    original = ENGINE._source_action
    ENGINE._source_action = _source_action
    try:
        yield
    finally:
        ENGINE._source_action = original


PROVENANCE = {
    "team": "Kenjo1209",
    "source_episode": 102192548,
    "source_seat": 1,
    "source_submission": 55854303,
    "source_actions_sha256": (
        "36718cecbc5424f0c5ed12cc01988033986504851a767318b8107c39fd165872"
    ),
    "source_file_sha256": (
        "4d686ff547797f776081254ee602eda151ec0fe5de7ddcdf646fedf1bf5f0f89"
    ),
    "selection": "reward-free six-route full-action Hamming medoid from E754",
    "guards": "complete E749/E750 visible-state execution network",
    "compatibility": "full/non-SELL through 71; physical through 85",
}

_LAST_DIAGNOSTIC: dict[int, dict[str, Any]] = {0: {}, 1: {}}


def agent(obs: Any, configuration: Any = None) -> dict[str, Any]:
    seat = ENGINE._seat(obs)
    step = max(0, min(MAX_STEPS - 1, int(ENGINE._get(obs, "step", 0) or 0)))
    source_step = min(step, SOURCE_STEPS - 1)
    with _installed_source():
        action = BASE.agent(obs, configuration)
    _LAST_DIAGNOSTIC[seat] = {
        "step": step,
        "programme_diverged": source_step in FULL_DIFFERENCE_STEPS,
        "physical_diverged": source_step in PHYSICAL_DIFFERENCE_STEPS,
        "base": dict(ENGINE._LAST_DIAGNOSTIC.get(seat, {})),
    }
    return action


e766a_agent = agent
