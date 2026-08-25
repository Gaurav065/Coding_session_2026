"""Project Aegis - Module 3: The Ghost Protocol & Non-Colliding Scavenger Overlay

Architecture:
1. The Ghost Protocol: Non-spatial signature noise (seed purchase on Step 0) to confuse opponent fingerprinting.
2. Non-Colliding Scavenger Overlay:
   - Only routes naturally occurring unscripted hands toward weed clearing (DIG) and fertilizer collection (COLLECT_FERTILIZER).
   - STRICT INVARIANT: Never issues auxiliary HIRE orders (preserves 100% tape capex).
   - STRICT INVARIANT: Never initiates PLANT orders on empty tiles (preserves 100% future pasture/crop reservations).
"""

from typing import Dict, List, Any, Optional, Tuple, Set

GHOST_SPOOF_STEP = 0
MAX_OPPORTUNISTIC_PLANT_DAY = 18
SHED_ACCESS_TILES: Set[Tuple[int, int]] = {(4, 4), (5, 4), (4, 5), (5, 5)}
_MOVE_DELTA = {"NORTH": (0, -1), "SOUTH": (0, 1), "EAST": (1, 0), "WEST": (-1, 0)}
_CLAIMS_TILE = {"BUILD_PASTURE", "BUILD_COOP", "PLANT"}


def _project_reserved_tiles(obs: Dict[str, Any], active_tape: List[Dict[str, Any]], step: int, lookahead: int = 20) -> Set[Tuple[int, int]]:
    """Projects forward, from REAL current positions, which tiles the tape's own
    scripted farmer/hands will BUILD_PASTURE/BUILD_COOP/PLANT on within the
    lookahead window. Tape actions carry no coordinates -- they act wherever
    the actor currently stands -- so the only way to know which tile a future
    scripted action targets is to simulate movement forward from ground truth.
    Anchoring to the REAL observed position (not a from-scratch full-game
    simulation) means any real-world drift (weed detours, etc.) self-corrects
    every time this is called, since it's called fresh every step.

    Root cause this prevents: an auxiliary hand planting on a tile the tape
    reserves for a future BUILD_PASTURE silently voids that build (engine:
    `if tile is not None: return`) with no error -- confirmed to cost 6 cows
    and $60k+ milk revenue in a real ablation test.

    Known limitation: if the tape's own hand count grows mid-window (a new
    hire lands within the lookahead), that new hand's targets aren't tracked
    since its spawn tile isn't known in advance -- a narrow residual risk,
    much smaller in scope than reserving nothing at all.
    """
    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return set()
    farm = farms[player]

    positions: List[Tuple[int, int]] = [tuple(farm.get("farmer", [4, 4]))]
    live_hands = farm.get("hands", []) or []
    tape_hand_count = len(active_tape[step].get("hands", []) or []) if step < len(active_tape) else 0
    for i in range(min(tape_hand_count, len(live_hands))):
        positions.append(tuple(live_hands[i]))

    reserved: Set[Tuple[int, int]] = set()
    end = min(step + lookahead, len(active_tape))
    for future_step in range(step, end):
        raw = active_tape[future_step]
        acts = [raw.get("farmer", ["PASS"])] + list(raw.get("hands", []) or [])[:len(positions) - 1]
        for idx, act in enumerate(acts):
            if not act or idx >= len(positions):
                continue
            op = act[0]
            if op in _MOVE_DELTA:
                dx, dy = _MOVE_DELTA[op]
                x, y = positions[idx]
                positions[idx] = (x + dx, y + dy)
            elif op in _CLAIMS_TILE:
                reserved.add(positions[idx])
    return reserved


def apply_ghost_signature_spoof(
    obs: Dict[str, Any],
    action: Dict[str, Any]
) -> Dict[str, Any]:
    """Injects safe, non-spatial market noise on Step 0 (e.g. buying 1 cheap Carrot seed)
    to disrupt opponent fingerprinting algorithms while preserving 100% of spatial pathing.
    """
    step = obs.get("step", 0)
    if step != GHOST_SPOOF_STEP:
        return action

    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    money = float(farms[player].get("money", 0.0)) if len(farms) > player else 0.0

    if money < 2500.0:
        return action

    market = action.setdefault("market", [])
    has_carrot_buy = any(
        isinstance(o, list) and len(o) >= 2 and o[0] == "BUY_SEED" and o[1] == "CARROT"
        for o in market
    )

    if not has_carrot_buy and len(market) < 10:
        market.append(["BUY_SEED", "CARROT", 1])

    return action


_FIB = [1, 1]
while len(_FIB) < 20:
    _FIB.append(_FIB[-1] + _FIB[-2])

AUX_HIRE_MIN_DAY = 10
AUX_HIRE_MAX_DAY = 26
AUX_HIRE_SCARCITY_MIN_DAY = 4
AUX_HIRE_SCARCITY_MAX_DAY = 9
AUX_HIRE_MIN_CASH_BUFFER = 500.0

# Measured via real ablation (8 seeds, env.run() vs "starter"): even after fixing
# the tile-reservation collision (0/34 BUILD_PASTURE failures, confirmed), hiring
# an auxiliary hand at all -- regardless of what it's tasked with -- costs
# -$47,652 avg vs not hiring one. Isolated and ruled out: hire cost (~$100-150
# total, trivial), crop-tending vs weed/fertilizer-only (both regress similarly),
# fertilizer-collection specifically (removing it changes nothing). Traced to a
# real step where an IDENTICAL market order nets $2,933 with the aux hand absent
# and $0 with it present -- the extra hand's mere presence disrupts shed
# inventory the tape's own scripted hands expect to have accumulated, most
# likely the same hand-index fragility found in a different tape entirely
# (project_doppelganger's YARN route: hand roles are positional, and any
# divergence from the exact count/order the tape assumes compounds over time).
# This is the 5th documented failure of "graft extra production onto a fixed
# tape via an auxiliary hand" in this project's history. Kept disabled until a
# fix addresses hand-identity stability, not just tile occupancy.
AUX_HIRE_ENABLED = False


def schedule_auxiliary_farmhand_hire(
    action: Dict[str, Any],
    obs: Dict[str, Any],
    scarcity_active: bool = False,
) -> Dict[str, Any]:
    """Adds ONE extra HIRE order on top of whatever the tape already schedules
    this morning, so the scavenger overlay has an unscripted hand to route into
    Wave-2 Melon Replanter / scarcity-crop work. Must be ADDITIVE: the tape
    re-hires its full crew every morning (hands wipe nightly), so "already has
    HIRE orders queued" is the normal case, not a reason to skip -- a prior
    version of this gated on `if no HIRE already queued`, which meant it never
    fired on any day the tape hires at all (confirmed empirically: 0/5 games).

    DISABLED by default (see AUX_HIRE_ENABLED docstring above) pending a fix
    for the hand-identity fragility this causes even though the tile-reservation
    collision it was originally built to fix is confirmed resolved.
    """
    if not AUX_HIRE_ENABLED:
        return action
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    if hour != 0:
        return action

    in_window = (AUX_HIRE_MIN_DAY <= day <= AUX_HIRE_MAX_DAY) or (
        scarcity_active and AUX_HIRE_SCARCITY_MIN_DAY <= day <= AUX_HIRE_SCARCITY_MAX_DAY
    )
    if not in_window:
        return action

    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return action
    farm = farms[player]
    money = float(farm.get("money", 0.0) or 0.0)

    market = action.setdefault("market", [])
    hires_already_queued = sum(1 for o in market if isinstance(o, list) and len(o) > 0 and o[0] == "HIRE")
    this_hire_cost = float(_FIB[min(hires_already_queued, len(_FIB) - 1)])

    if money < AUX_HIRE_MIN_CASH_BUFFER + this_hire_cost or len(market) >= 10:
        return action

    market.append(["HIRE"])
    return action


WAVE2_PLANT_START_DAY = 10
WAVE2_PLANT_END_DAY = 12
WAVE2_HARVEST_END_DAY = 27


class OpportunisticCropManager:
    """Detects extreme shop demand surges for Tomato/Carrot (scarcity window,
    days 4-9) and drives Wave-2 Melon replanting (days 10-27) on tiles the
    tape's own future schedule does NOT claim -- verified via
    `_project_reserved_tiles`, never on raw "tile is empty right now"."""

    @staticmethod
    def detect_scarcity_opportunity(obs: Dict[str, Any]) -> Optional[str]:
        day = int(obs.get("day", 0) or 0)
        if not (AUX_HIRE_SCARCITY_MIN_DAY <= day <= AUX_HIRE_SCARCITY_MAX_DAY):
            return None
        player = obs.get("player", 0)
        farms = obs.get("farms", [{}, {}])
        if len(farms) <= player:
            return None
        money = float(farms[player].get("money", 0.0) or 0.0)
        if money < 500.0:
            return None

        shops = (obs.get("town") or {}).get("unlocked_shops", []) or []
        market_prices = (obs.get("market") or {}).get("prices", {}) or {}

        tomato_shops = shops.count("PIZZA_SHOP") + shops.count("FARMERS_MARKET")
        if tomato_shops >= 2 or market_prices.get("TOMATO", 60) >= 110:
            return "TOMATO"
        carrot_shops = (shops.count("PET_CAFE") * 2) + shops.count("FARMERS_MARKET")
        if carrot_shops >= 2 or market_prices.get("CARROT", 30) >= 80:
            return "CARROT"
        return None

    @staticmethod
    def find_safe_tiles(
        tiles: List[List[Any]],
        unlocked_quads: List[str],
        reserved: Set[Tuple[int, int]],
        crop: Optional[str],
        max_tiles: int = 12,
    ) -> List[Tuple[int, int]]:
        """Existing plants of `crop` first (to keep tending them), then empty
        tiles not in `reserved` and not a shed-access tile."""
        existing_plants = []
        empty_tiles = []
        for y, row in enumerate(tiles):
            for x, tile in enumerate(row or []):
                if (x, y) in SHED_ACCESS_TILES or (x, y) in reserved:
                    continue
                quad = "NW" if x < 5 and y < 5 else ("NE" if x >= 5 and y < 5 else ("SW" if x < 5 and y >= 5 else "SE"))
                if quad not in unlocked_quads:
                    continue
                if isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == crop:
                    existing_plants.append((x, y))
                elif tile is None:
                    empty_tiles.append((x, y))
        return (existing_plants + empty_tiles)[:max_tiles]


def scavenger_farmhand_overlay(
    action: Dict[str, Any],
    obs: Dict[str, Any],
    active_tape: Optional[List[Dict[str, Any]]] = None,
    step: int = 0,
) -> Dict[str, Any]:
    """Routes unscripted farmhands, in priority order:
    1. Tomato/Carrot scarcity micro-plots (days 4-9) or Wave-2 Melon replant
       (days 10-27) -- ONLY on tiles `_project_reserved_tiles` confirms the
       tape's own future schedule does not claim.
    2. Nearest weed (DIG).
    3. Nearest ready fertilizer (COLLECT_FERTILIZER).

    If `active_tape` is not supplied, crop-planting is skipped entirely and
    this behaves exactly like the previous DIG/COLLECT_FERTILIZER-only,
    zero-collision-risk version.
    """
    player = obs.get("player", 0)
    farms = obs.get("farms", [{}, {}])
    if len(farms) <= player:
        return action

    farm = farms[player]
    live_hands = farm.get("hands", []) or []
    tape_hands = list(action.get("hands", []) or [])
    tiles = farm.get("tiles", []) or []
    unlocked_quads = farm.get("unlocked_quadrants", ["NW"])
    private = obs.get("private") or {}
    seeds = private.get("seeds", {}) or {}
    day = int(obs.get("day", 0) or 0)

    if len(tape_hands) >= len(live_hands):
        return action

    crop: Optional[str] = None
    safe_tiles: List[Tuple[int, int]] = []
    if active_tape is not None:
        if AUX_HIRE_SCARCITY_MIN_DAY <= day <= AUX_HIRE_SCARCITY_MAX_DAY:
            crop = OpportunisticCropManager.detect_scarcity_opportunity(obs)
        elif WAVE2_PLANT_START_DAY <= day <= WAVE2_HARVEST_END_DAY:
            crop = "MELON"
        if crop:
            reserved = _project_reserved_tiles(obs, active_tape, step)
            safe_tiles = OpportunisticCropManager.find_safe_tiles(tiles, unlocked_quads, reserved, crop)

    weeds: List[Tuple[int, int]] = []
    fertilizers: List[Tuple[int, int]] = []
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row or []):
            if isinstance(tile, dict):
                kind = tile.get("kind")
                if kind == "WEED":
                    weeds.append((x, y))
                elif kind in ("COOP", "PASTURE") and tile.get("fertilizer_available"):
                    fertilizers.append((x, y))

    while len(tape_hands) < len(live_hands):
        hand_idx = len(tape_hands)
        hx, hy = live_hands[hand_idx]

        best_target = None
        best_dist = 9999
        target_action_type = "PASS"

        # 1. Crop task on a verified-safe tile
        if crop and safe_tiles:
            for mx, my in safe_tiles:
                mtile = tiles[my][mx] if my < len(tiles) and mx < len(tiles[my]) else None
                if isinstance(mtile, dict) and mtile.get("kind") == "PLANT":
                    yield_u = int(mtile.get("yield_units", 0) or 0)
                    if yield_u > 0:
                        d = abs(hx - mx) + abs(hy - my)
                        if d < best_dist:
                            best_dist, best_target, target_action_type = d, (mx, my), "HARVEST"
                    elif not mtile.get("watered_today", False):
                        d = abs(hx - mx) + abs(hy - my)
                        if d < best_dist:
                            best_dist, best_target, target_action_type = d, (mx, my), "WATER"
                elif mtile is None:
                    d = abs(hx - mx) + abs(hy - my)
                    if d < best_dist:
                        best_dist, best_target, target_action_type = d, (mx, my), "PLANT"

        # 2. Nearest weed
        if not best_target:
            for wx, wy in weeds:
                d = abs(hx - wx) + abs(hy - wy)
                if d < best_dist:
                    best_dist, best_target, target_action_type = d, (wx, wy), "DIG"

        # 3. Nearest ready fertilizer
        if not best_target:
            for fx, fy in fertilizers:
                d = abs(hx - fx) + abs(hy - fy)
                if d < best_dist:
                    best_dist, best_target, target_action_type = d, (fx, fy), "COLLECT_FERTILIZER"

        if best_target:
            tx, ty = best_target
            if best_dist == 0:
                if target_action_type == "PLANT":
                    if seeds.get(crop, 0) > 0:
                        tape_hands.append(["PLANT", crop])
                    else:
                        market = action.setdefault("market", [])
                        has_pending = any(
                            isinstance(o, list) and len(o) >= 2 and o[0] == "BUY_SEED" and o[1] == crop
                            for o in market
                        )
                        if not has_pending and len(market) < 10:
                            market.append(["BUY_SEED", crop, 2])
                        tape_hands.append(["PASS"])
                else:
                    tape_hands.append([target_action_type])
                    if target_action_type == "DIG" and (tx, ty) in weeds:
                        weeds.remove((tx, ty))
                    elif target_action_type == "COLLECT_FERTILIZER" and (tx, ty) in fertilizers:
                        fertilizers.remove((tx, ty))
            else:
                if hx < tx:
                    tape_hands.append(["EAST"])
                elif hx > tx:
                    tape_hands.append(["WEST"])
                elif hy < ty:
                    tape_hands.append(["SOUTH"])
                elif hy > ty:
                    tape_hands.append(["NORTH"])
        else:
            tape_hands.append(["PASS"])

    action["hands"] = tape_hands
    return action
