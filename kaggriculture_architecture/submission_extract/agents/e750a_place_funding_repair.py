"""E750A: account for same-turn shed-adjacent PLACE in E749's visible ledger."""

from __future__ import annotations

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

import e749a_niklita_consensus_network as PARENT

PROVENANCE = {
    **PARENT.PROVENANCE,
    "owned_repair": "engine-exact visible same-turn shed-adjacent PLACE projection",
    "parent": "E749-A frozen SHA-256 2188debac2af3308f4ea1bd427a38cd3a2332394073c7cca6240c011fb0c5374",
}
STEP_NETWORK = PARENT.STEP_NETWORK
_LAST_DIAGNOSTIC = PARENT._LAST_DIAGNOSTIC


def _project_shed(
    obs: Any, seat: int, action: dict[str, Any]
) -> tuple[dict[str, int], dict[str, int]]:
    """Project engine shed operations in actor order, including PLACE."""

    farm = PARENT._farm(obs, seat)
    private = PARENT._private(obs)
    shed = Counter(
        {
            str(item): max(0, int(quantity or 0))
            for item, quantity in dict(PARENT._get(private, "shed", {}) or {}).items()
        }
    )
    inventories = list(PARENT._get(private, "inventories", []) or [])
    positions = [
        PARENT._get(farm, "farmer"),
        *list(PARENT._get(farm, "hands", []) or []),
    ]
    commands = [action.get("farmer", ["PASS"]), *list(action.get("hands") or [])]
    pickup_reserve: Counter[str] = Counter()
    board_size = len(PARENT._get(farm, "tiles", []) or []) or 10
    half = board_size // 2
    cross = {
        (half - 1, half - 1),
        (half, half - 1),
        (half - 1, half),
        (half, half),
    }
    for index, (position, command) in enumerate(zip(positions, commands)):
        if not isinstance(command, list) or not command:
            continue
        try:
            point = (int(position[0]), int(position[1]))
        except (TypeError, ValueError):
            continue
        if point not in cross:
            continue
        inventory = (
            Counter(
                {
                    str(item): max(0, int(quantity or 0))
                    for item, quantity in dict(inventories[index] or {}).items()
                }
            )
            if index < len(inventories)
            else Counter()
        )
        operation = str(command[0])
        if operation == "PICKUP" and len(command) >= 2:
            item = str(command[1])
            quantity = max(1, int(command[2])) if len(command) >= 3 else 1
            taken = min(quantity, shed[item])
            shed[item] -= taken
            pickup_reserve[item] += taken
        elif operation == "DROP":
            for item, quantity in inventory.items():
                room = max(0, PARENT.SHED_CAPACITY - sum(shed.values()))
                shed[item] += min(quantity, room)
        elif operation == "PLACE" and len(command) >= 2:
            item = str(command[1])
            quantity = max(1, int(command[2])) if len(command) >= 3 else 1
            room = max(0, PARENT.SHED_CAPACITY - sum(shed.values()))
            shed[item] += min(quantity, inventory[item], room)
    return dict(shed), dict(pickup_reserve)


@contextmanager
def _installed_projection() -> Iterator[None]:
    original = PARENT._project_shed
    PARENT._project_shed = _project_shed
    try:
        yield
    finally:
        PARENT._project_shed = original


def _cap_sales(
    obs: Any, seat: int, action: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    with _installed_projection():
        return PARENT._cap_sales(obs, seat, action)


def _fund_market(
    obs: Any, seat: int, action: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, int]]:
    with _installed_projection():
        return PARENT._fund_market(obs, seat, action)


def agent(obs: Any, configuration: Any = None) -> dict[str, Any]:
    with _installed_projection():
        return PARENT.agent(obs, configuration)


e750a_agent = agent
