"""Observation-only terminal overlays used by the v19 ablation search.

The implementation is intentionally independent of any replay trace.  It can
wrap v18, a current-meta medoid, or another public control without knowing the
opponent identity.
"""

from __future__ import annotations

import copy
import math


SELLABLE = (
    "STRAWBERRY", "MELON", "MILK", "WOOL", "EGG",
    "TOMATO", "CARROT", "WHEAT", "FERTILIZER",
)
PRODUCT_BY_ANIMAL = {"COW": "MILK", "SHEEP": "WOOL", "GOOSE": "EGG"}
GLUT_WEIGHT = {
    "STRAWBERRY": 2.0,
    "MELON": 3.6,
    "MILK": 2.0,
    "WOOL": 3.2,
    "EGG": 1.5,
    "TOMATO": 1.3,
    "CARROT": 1.0,
    "WHEAT": 1.0,
    "FERTILIZER": 1.0,
}
MAX_ORDERS = 10
SHED_CAPACITY = 100


def _number(value, default=0.0):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _shed_access(board_size):
    half = board_size // 2
    return {
        (half - 1, half - 1),
        (half, half - 1),
        (half - 1, half),
        (half, half),
    }


def align_hands(action, obs):
    """Match the live hand count without remapping the validated prefix."""
    copied = copy.deepcopy(action or {})
    player = 1 if int(obs.get("player", 0) or 0) == 1 else 0
    farms = obs.get("farms", []) or []
    farm = farms[player] if player < len(farms) else {}
    expected = len((farm or {}).get("hands", []) or [])
    hands = list(copied.get("hands") or [])
    if len(hands) < expected:
        hands.extend([["PASS"] for _ in range(expected - len(hands))])
    copied["farmer"] = list(copied.get("farmer") or ["PASS"])
    copied["hands"] = [list(order or ["PASS"]) for order in hands[:expected]]
    copied["market"] = [list(order) for order in (copied.get("market") or [])]
    return copied


def projected_shed(obs, action):
    """Project legal DROP/PLACE deposits, which execute before the market."""
    player = 1 if int(obs.get("player", 0) or 0) == 1 else 0
    farms = obs.get("farms", []) or []
    farm = farms[player] if player < len(farms) else {}
    private = obs.get("private", {}) or {}
    projected = {
        key: max(0, int(value or 0))
        for key, value in dict(private.get("shed", {}) or {}).items()
    }
    inventories = list(private.get("inventories", []) or [])
    positions = [farm.get("farmer", [0, 0]), *(farm.get("hands", []) or [])]
    actions = [action.get("farmer", ["PASS"]), *(action.get("hands") or [])]
    tiles = farm.get("tiles", []) or []
    board_size = len(tiles) or 10
    access = _shed_access(board_size)

    for index, unit_action in enumerate(actions):
        if index >= len(positions) or index >= len(inventories):
            continue
        position = positions[index]
        if not isinstance(position, (list, tuple)) or len(position) < 2:
            continue
        x, y = int(position[0]), int(position[1])
        if (x, y) not in access or not (0 <= y < len(tiles) and 0 <= x < len(tiles[y])):
            continue
        # Since engine 1.32.7, shed DROP/PLACE resolves before the LOCKED-tile
        # guard.  Three central shed-access tiles begin locked but are still
        # legal standing positions for these operations.
        if not isinstance(unit_action, list) or not unit_action:
            continue
        inventory = {
            key: max(0, int(value or 0))
            for key, value in dict(inventories[index] or {}).items()
        }
        if unit_action[0] == "DROP":
            deposits = inventory.items()
        elif unit_action[0] == "PLACE" and len(unit_action) >= 2:
            item = unit_action[1]
            tile = tiles[y][x]
            animal_structure = {"COW": "PASTURE", "SHEEP": "PASTURE", "GOOSE": "COOP"}.get(item)
            if (
                animal_structure is not None
                and isinstance(tile, dict)
                and tile.get("kind") == animal_structure
                and "animal" not in tile
            ):
                continue
            try:
                requested = int(unit_action[2]) if len(unit_action) >= 3 else 1
            except (TypeError, ValueError):
                continue
            deposits = ((item, min(max(0, requested), inventory.get(item, 0))),)
        else:
            continue
        for item, quantity in deposits:
            room = max(0, SHED_CAPACITY - sum(projected.values()))
            deposited = min(max(0, int(quantity or 0)), room)
            if deposited:
                projected[item] = projected.get(item, 0) + deposited
    return projected


def opponent_exposure(obs):
    """Estimate visible terminal supply without identity or private state."""
    player = 1 if int(obs.get("player", 0) or 0) == 1 else 0
    farms = obs.get("farms", []) or []
    opponent = farms[1 - player] if len(farms) >= 2 else {}
    exposure = {item: 0.0 for item in SELLABLE}
    for row in (opponent or {}).get("tiles", []) or []:
        for tile in row if isinstance(row, list) else [row]:
            if not isinstance(tile, dict):
                continue
            crop = str(tile.get("crop", "")).upper()
            if crop in exposure:
                exposure[crop] += max(1.0, _number(tile.get("yield_units", 0)))
            animal = str(tile.get("animal", "")).upper()
            product = PRODUCT_BY_ANIMAL.get(animal)
            if product:
                exposure[product] += 1.0 + max(0.0, _number(tile.get("yield_units", 0)))
            if tile.get("fertilizer_available", False):
                exposure["FERTILIZER"] += 1.0
    return exposure


def _public_signature(farm):
    counts = {
        key: 0
        for key in (
            "WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
            "COW", "SHEEP", "GOOSE", "PASTURE", "COOP", "WEED",
        )
    }
    for row in (farm or {}).get("tiles", []) or []:
        for tile in row if isinstance(row, list) else [row]:
            if not isinstance(tile, dict):
                continue
            for field in ("crop", "animal", "kind"):
                value = str(tile.get(field, "")).upper()
                if value in counts:
                    counts[value] += 1
                    break
    return (
        len((farm or {}).get("hands", []) or []),
        len((farm or {}).get("unlocked_quadrants", []) or []),
        tuple(counts[key] for key in sorted(counts)),
    )


def clone_distance(obs):
    farms = obs.get("farms", []) or []
    if len(farms) < 2:
        return float("inf")
    left = _public_signature(farms[0])
    right = _public_signature(farms[1])
    return (
        abs(left[0] - right[0])
        + 3 * abs(left[1] - right[1])
        + sum(abs(a - b) for a, b in zip(left[2], right[2]))
    )


def terminal_market(obs, action, rule="collision", *, replace=True):
    """Sell every projected product; choose ordering from observable state."""
    action = align_hands(action, obs)
    shed = projected_shed(obs, action)
    prices = ((obs.get("market", {}) or {}).get("prices", {}) or {})
    exposure = opponent_exposure(obs)
    existing_market = list(action.get("market") or [])
    existing_rank = {
        order[1]: index
        for index, order in enumerate(existing_market)
        if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL"
    }

    rows = []
    for item in SELLABLE:
        quantity = max(0, int(shed.get(item, 0) or 0))
        if quantity <= 0:
            continue
        price = max(1.0, _number(prices.get(item, 1), 1.0))
        if rule == "value":
            score = price * quantity
        elif rule == "existing":
            score = -existing_rank.get(item, len(SELLABLE) + SELLABLE.index(item))
        else:
            score = (
                (1.0 + exposure.get(item, 0.0))
                * GLUT_WEIGHT.get(item, 1.0)
                * price
                * math.log1p(quantity)
            )
        rows.append((score, -SELLABLE.index(item), item, quantity))
    rows.sort(reverse=True)
    sells = [["SELL", item, quantity] for _, _, item, quantity in rows]
    if replace:
        action["market"] = sells[:MAX_ORDERS]
        return action

    already = {
        order[1]
        for order in existing_market
        if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL"
    }
    for order in sells:
        if len(existing_market) >= MAX_ORDERS:
            break
        if order[1] not in already:
            existing_market.append(order)
            already.add(order[1])
    action["market"] = existing_market[:MAX_ORDERS]
    return action


def _move_toward(position, targets, tiles):
    x, y = position
    if not targets:
        return ["PASS"]
    target = min(targets, key=lambda point: (abs(point[0] - x) + abs(point[1] - y), point[1], point[0]))
    tx, ty = target
    candidates = []
    if tx < x:
        candidates.append(("WEST", x - 1, y))
    if tx > x:
        candidates.append(("EAST", x + 1, y))
    if ty < y:
        candidates.append(("NORTH", x, y - 1))
    if ty > y:
        candidates.append(("SOUTH", x, y + 1))
    size = len(tiles)
    for operation, nx, ny in candidates:
        if 0 <= nx < size and 0 <= ny < size and tiles[ny][nx] != "LOCKED":
            return [operation]
    return ["PASS"]


def monetizable_terminal_units(obs, action, step):
    """Override only unit actions that can still reach the shed by step 718."""
    action = align_hands(action, obs)
    if step not in (717, 718):
        return action
    player = 1 if int(obs.get("player", 0) or 0) == 1 else 0
    farms = obs.get("farms", []) or []
    farm = farms[player] if player < len(farms) else {}
    private = obs.get("private", {}) or {}
    tiles = farm.get("tiles", []) or []
    if not tiles:
        return action
    access = _shed_access(len(tiles))
    positions = [farm.get("farmer", [0, 0]), *(farm.get("hands", []) or [])]
    inventories = list(private.get("inventories", []) or [])
    inventories.extend({} for _ in range(max(0, len(positions) - len(inventories))))
    unit_actions = [action.get("farmer", ["PASS"]), *(action.get("hands") or [])]

    for index, (raw_position, inventory) in enumerate(zip(positions, inventories)):
        if not isinstance(raw_position, (list, tuple)) or len(raw_position) < 2:
            continue
        position = (int(raw_position[0]), int(raw_position[1]))
        load = sum(max(0, int(value or 0)) for value in (inventory or {}).values())
        x, y = position
        tile = tiles[y][x] if 0 <= y < len(tiles) and 0 <= x < len(tiles[y]) else None
        distance = min(abs(x - sx) + abs(y - sy) for sx, sy in access)
        replacement = None
        if load > 0 and position in access:
            replacement = ["DROP"]
        elif step == 717 and load > 0 and distance == 1:
            replacement = _move_toward(position, access, tiles)
        elif (
            step == 717
            and load == 0
            and position in access
            and isinstance(tile, dict)
            and int(tile.get("yield_units", 0) or 0) > 0
        ):
            replacement = ["HARVEST"]
        if replacement is not None:
            unit_actions[index] = replacement

    action["farmer"] = unit_actions[0]
    action["hands"] = unit_actions[1:]
    return action


def apply_overlay(obs, base_action, mode):
    """Apply one named ablation without changing the wrapped base policy."""
    step = max(0, int(obs.get("step", 0) or 0))
    action = align_hands(base_action, obs)
    if mode in {"terminal_existing", "terminal_value", "terminal_collision"}:
        action = monetizable_terminal_units(obs, action, step)
    if step == 718:
        if mode in {"c20_append", "terminal_existing"}:
            action = terminal_market(obs, action, "existing", replace=False)
        elif mode == "terminal_value":
            action = terminal_market(obs, action, "value", replace=True)
        elif mode == "terminal_collision":
            action = terminal_market(obs, action, "collision", replace=True)
        elif mode in {"late_collision", "late_clone_collision"}:
            # Final-turn purchases and hires cannot improve bank reward.  At
            # the last executable market step, replace them with every
            # projected sellable unit, including same-turn DROP/PLACE stock.
            action = terminal_market(obs, action, "collision", replace=True)
    elif mode == "late_collision" and step >= 680:
        action = terminal_market(obs, action, "collision", replace=False)
    elif mode == "late_clone_collision" and step >= 680 and clone_distance(obs) <= 2:
        action = terminal_market(obs, action, "collision", replace=False)
    return action


def wrap_policy(policy, mode):
    def wrapped(obs):
        return apply_overlay(obs, policy(obs), mode)

    return wrapped
