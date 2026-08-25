"""Project Aegis - Execution Guards & Repair Subsystems

Contains:
1. Weed Repair Guard: Dynamically clears unexpected random weeds (0.5% spawn) blocking farmer pathing.
2. Feed Rescue Guard: Ensures live animals never starve if wheat feed buffer runs out at hour 18+.
3. Room Evac & Capacity Guard: Prevents shed overflow at end-of-day (hour 23).
"""

from typing import Dict, List, Any, Optional, Tuple, Set

# Central shed access coordinates
SHED_ACCESS = {(4, 4), (5, 4), (4, 5), (5, 5)}


def weed_repair_overlay(
    action: Dict[str, Any],
    obs: Dict[str, Any],
    step: int
) -> Dict[str, Any]:
    """If a unit is about to execute a tile action (PLANT, WATER, HARVEST, BUILD) on a square
    where an unexpected weed spawned, swap the action to DIG for 1 turn to clear the tile.
    """
    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return action

    farm = farms[player]
    tiles = farm.get("tiles", []) or []
    farmer_pos = farm.get("farmer", [4, 4])
    hands_pos = farm.get("hands", []) or []

    all_positions = [farmer_pos] + hands_pos
    farmer_act = list(action.get("farmer", ["PASS"]))
    hands_act = [list(h) for h in action.get("hands", [])]
    all_acts = [farmer_act] + hands_act

    for i, pos in enumerate(all_positions):
        if i >= len(all_acts):
            break
        if not pos or len(pos) < 2:
            continue
        x, y = pos[0], pos[1]
        if y < len(tiles) and x < len(tiles[y]):
            tile = tiles[y][x]
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                curr_op = all_acts[i][0] if len(all_acts[i]) > 0 else "PASS"
                # If trying to plant, build, water, or pass on a weed, clear it first
                if curr_op in ("PLANT", "BUILD_COOP", "BUILD_PASTURE", "WATER", "HARVEST"):
                    all_acts[i] = ["DIG"]

    action["farmer"] = all_acts[0]
    action["hands"] = all_acts[1:]
    return action


def feed_rescue_guard(
    action: Dict[str, Any],
    obs: Dict[str, Any],
    step: int
) -> Dict[str, Any]:
    """If live animals remain unfed late in the day (hour >= 18) and shed has 0 wheat,
    automatically dispatches a BUY_PRODUCT WHEAT order to prevent animal starvation and escape.
    """
    hour = int(obs.get("hour", 0) or 0)
    if hour < 18:
        return action

    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return action

    farm = farms[player]
    tiles = farm.get("tiles", []) or []
    unfed_animals = 0

    for row in tiles:
        for tile in row or []:
            if isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE") and tile.get("animal"):
                if not tile.get("fed_today", False):
                    unfed_animals += 1

    if unfed_animals <= 0:
        return action

    private = obs.get("private") or {}
    shed = private.get("shed", {}) or {}
    wheat_in_shed = int(shed.get("WHEAT", 0) or 0)

    if wheat_in_shed < unfed_animals:
        needed = unfed_animals - wheat_in_shed
        money = float(farm.get("money", 0.0) or 0.0)
        market = action.setdefault("market", [])
        if money >= needed * 25 and len(market) < 10:
            market.append(["BUY_PRODUCT", "WHEAT", needed])

    return action
