"""Project Reactive: rule-based Kaggriculture agent (not a fixed tape replay).

Design principles, all derived from the 456-player-game corpus analysis and
verified engine mechanics this session:
- Buy animals (cows first, then sheep) as early and densely as possible --
  animals are the dominant score predictor (r=0.278 for cows, r=0.345 for
  animals-per-quadrant); crop diversification (tomato/carrot/egg) is a
  measured dead lever (near-zero or negative correlation).
- Restrain land purchases -- more quadrants did not correlate with more
  animals in the corpus (r=-0.184); land is only bought if it will actually
  hold more animals than we already have room for.
- React to real AMM prices when selling, not a fixed schedule.
- No fixed hand-count/index assumptions: every decision is made from CURRENT
  observed position/inventory each step, since hands and the farmer's
  position both reset every night (engine: `_end_of_day`). This sidesteps
  the hand-index fragility that broke every bolt-on overlay this session.

Per-actor inventory indexing (verified against engine source): inventories[0]
is the farmer, inventories[i+1] is hands[i] -- same index as position lists.
"""

from typing import Dict, Any, List, Tuple, Optional

TARGET_COWS = 10
TARGET_SHEEP = 4
TARGET_QUADS = 3
TARGET_HANDS = 6
SELL_PRICE_RATIO = 0.85
FEED_BUFFER_DAYS = 2

# --- Value-density-aware sell thresholds (candidate_sell_threshold fix) ---
# BASE_PRICES splits into two clear tiers with a ~1.7x gap between them:
#   cheap/bulky:  WHEAT $25, CARROT $35
#   valuable/low-volume: TOMATO $60, EGG $50, FERTILIZER $100, STRAWBERRY $120,
#                         MILK $160, WOOL $200, MELON $250
# WHEAT/CARROT are the two cheapest goods AND (being basic crops) the ones
# most likely to accumulate in bulk from repeated harvests, so they eat the
# combined 100-unit shed cap fastest for the least value-per-unit. Holding
# them hoping for a better AMM price is a bad trade: the opportunity cost is
# shed space that MILK/WOOL/EGG/FERTILIZER (2-6x the value density) need to
# avoid being silently discarded at the once-daily flush. So they get almost
# no price floor -- just a sanity check against dumping at a fully crashed
# price -- gated mainly on a small operating buffer instead of price.
# Everything else keeps the original meaningful floor (SELL_PRICE_RATIO):
# these are valuable and low-volume enough that waiting for a decent price
# is worth the shed-space cost.
LOW_VALUE_ITEMS = {"WHEAT", "CARROT"}
LOW_VALUE_MIN_PRICE_RATIO = 0.3  # sanity floor only, not a "wait for a good price" floor
LOW_VALUE_BUFFER = {"CARROT": 5}  # WHEAT's buffer is already the feed reserve, netted out below

BASE_PRICES = {
    "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "STRAWBERRY": 120, "MELON": 250,
    "EGG": 50, "MILK": 160, "WOOL": 200, "FERTILIZER": 100,
}
ANIMAL_COST = {"COW": 400, "SHEEP": 500, "GOOSE": 300}
ANIMAL_STRUCTURE = {"COW": "PASTURE", "SHEEP": "PASTURE", "GOOSE": "COOP"}
SHED_ACCESS = {(4, 4), (5, 4), (4, 5), (5, 5)}
_FIB = [1, 1]
while len(_FIB) < 20:
    _FIB.append(_FIB[-1] + _FIB[-2])


def _quadrant_of(x: int, y: int) -> str:
    return "NW" if x < 5 and y < 5 else ("NE" if x >= 5 and y < 5 else ("SW" if x < 5 and y >= 5 else "SE"))


def _step_toward(pos: Tuple[int, int], target: Tuple[int, int]) -> List[str]:
    hx, hy = pos
    tx, ty = target
    if hx < tx:
        return ["EAST"]
    if hx > tx:
        return ["WEST"]
    if hy < ty:
        return ["SOUTH"]
    if hy > ty:
        return ["NORTH"]
    return []


def _nearest_shed_tile(pos: Tuple[int, int]) -> Tuple[int, int]:
    return min(SHED_ACCESS, key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))


def _count_animals(tiles) -> Dict[str, int]:
    counts = {"COW": 0, "SHEEP": 0, "GOOSE": 0}
    for row in tiles or []:
        for t in row or []:
            if isinstance(t, dict):
                a = t.get("animal")
                if a in counts:
                    counts[a] += 1
    return counts


def _find_tiles(tiles, unlocked_quads, predicate) -> List[Tuple[int, int]]:
    out = []
    for y, row in enumerate(tiles or []):
        for x, t in enumerate(row or []):
            if (x, y) in SHED_ACCESS:
                continue
            if _quadrant_of(x, y) not in unlocked_quads:
                continue
            if predicate(t):
                out.append((x, y))
    return out


def _nearest(pos, candidates):
    if not candidates:
        return None
    return min(candidates, key=lambda p: abs(p[0] - pos[0]) + abs(p[1] - pos[1]))


class ReactiveAgentState:
    def __init__(self):
        self.last_step = -1

    def reset_if_new_game(self, step: int):
        if step == 0 or step < self.last_step:
            self.last_step = step
        self.last_step = step


_STATES: Dict[int, ReactiveAgentState] = {}


def _get_state(player: int) -> ReactiveAgentState:
    if player not in _STATES:
        _STATES[player] = ReactiveAgentState()
    return _STATES[player]


def _actor_action(
    pos: Tuple[int, int],
    inv: Dict[str, int],
    tiles,
    unlocked_quads: List[str],
    context: Dict[str, Any],
) -> List[Any]:
    """Decides ONE actor's (farmer or a hand) action this step, given its own
    real position and real personal inventory. Shared `context` carries
    farm-wide state (animal-needing-X tile lists, pending shed items) that
    gets consumed as actors claim tasks, so two actors don't chase the same tile.
    """
    x, y = pos
    tile = tiles[y][x] if y < len(tiles) and x < len(tiles[y]) else None

    # 1. Carrying an animal? Deliver it to a matching empty structure.
    for animal in ("COW", "SHEEP", "GOOSE"):
        if inv.get(animal, 0) > 0:
            structure = ANIMAL_STRUCTURE[animal]
            if isinstance(tile, dict) and tile.get("kind") == structure and "animal" not in tile:
                return ["PLACE", animal, 1]
            targets = context["empty_structures"].get(structure, [])
            target = _nearest((x, y), targets)
            if target:
                if target == (x, y):
                    return ["PLACE", animal, 1]
                return _step_toward((x, y), target)
            return []  # no structure to deliver to; fall through

    # 2. Standing on a live animal tile: feed/care/collect fertilizer.
    if isinstance(tile, dict) and "animal" in tile:
        if not tile.get("fed_today") and inv.get("WHEAT", 0) > 0:
            return ["FEED"]
        if not tile.get("cared_today"):
            return ["CARE"]
        if tile.get("fertilizer_available"):
            return ["COLLECT_FERTILIZER"]
        if tile.get("yield_units", 0) > 0:
            return ["HARVEST"]

    # 3. Carrying wheat: go feed something that needs it.
    if inv.get("WHEAT", 0) > 0:
        target = _nearest((x, y), context["needs_feed"])
        if target:
            if target == (x, y):
                return ["FEED"]
            return _step_toward((x, y), target)

    # 4. Need to build a pasture for a waiting animal.
    if context["need_pasture"]:
        if tile is None and (x, y) not in SHED_ACCESS and _quadrant_of(x, y) in unlocked_quads:
            context["need_pasture"] -= 1
            return ["BUILD_PASTURE"]
        build_target = _nearest((x, y), context["buildable_tiles"])
        if build_target:
            return _step_toward((x, y), build_target)

    # 5. Need to fetch something from the shed (unplaced animal or feed wheat).
    if context["shed_animals_waiting"] and not any(inv.get(a, 0) for a in ("COW", "SHEEP", "GOOSE")):
        if (x, y) in SHED_ACCESS:
            animal = context["shed_animals_waiting"][0]
            context["shed_pickup_this_step"].append(animal)
            return ["PICKUP", animal, 1]
        return _step_toward((x, y), _nearest_shed_tile((x, y)))

    if context["needs_feed"] and context["wheat_in_shed"] > 0:
        if (x, y) in SHED_ACCESS:
            qty = min(context["wheat_in_shed"], len(context["needs_feed"]))
            if qty > 0:
                context["wheat_in_shed"] -= qty
                return ["PICKUP", "WHEAT", qty]
        return _step_toward((x, y), _nearest_shed_tile((x, y)))

    # 6. Nearest outstanding animal-care task.
    for key in ("needs_feed", "needs_care", "needs_fert_collect"):
        target = _nearest((x, y), context[key])
        if target and target != (x, y):
            return _step_toward((x, y), target)

    return ["PASS"]


def _agent_impl(obs: Dict[str, Any]) -> Dict[str, Any]:
    step = int(obs.get("step", 0) or 0)
    day = int(obs.get("day", 0) or 0)
    hour = int(obs.get("hour", 0) or 0)
    player = int(obs.get("player", 0) or 0)
    state = _get_state(player)
    state.reset_if_new_game(step)

    farms = obs.get("farms", [{}, {}])
    farm = farms[player] if len(farms) > player else {}
    tiles = farm.get("tiles", []) or []
    farmer_pos = tuple(farm.get("farmer", [4, 4]))
    hands_pos = [tuple(p) for p in (farm.get("hands", []) or [])]
    unlocked_quads = farm.get("unlocked_quadrants", ["NW"])
    money = float(farm.get("money", 0.0) or 0.0)
    hires_today = int(farm.get("hires_today", 0) or 0)

    private = obs.get("private") or {}
    shed = private.get("shed", {}) or {}
    inventories = private.get("inventories") or [{}]
    market_prices = (obs.get("market") or {}).get("prices", {}) or {}

    market: List[List[Any]] = []
    animal_counts = _count_animals(tiles)

    # --- 1. Morning: re-hire target crew ---
    if hour == 0:
        needed_hands = TARGET_HANDS - len(hands_pos)
        for _ in range(max(0, needed_hands)):
            cost = _FIB[min(hires_today, len(_FIB) - 1)]
            if money < cost + 50:
                break
            market.append(["HIRE"])
            hires_today += 1
            money -= cost

    # --- 2. Land purchase: only if we still need room for more animals ---
    total_animal_target = TARGET_COWS + TARGET_SHEEP
    total_animal_current = animal_counts["COW"] + animal_counts["SHEEP"]
    need_more_room = total_animal_current < total_animal_target
    if len(unlocked_quads) < TARGET_QUADS and need_more_room:
        land_costs = {1: 1000, 2: 2000, 3: 4000}
        cost = land_costs.get(len(unlocked_quads), 4000)
        if money >= cost:
            market.append(["BUY_LAND"])
            money -= cost

    # --- 3. Buy animals if under target and cash allows (cows first) ---
    shed_animal_pending = {"COW": int(shed.get("COW", 0) or 0), "SHEEP": int(shed.get("SHEEP", 0) or 0)}
    for animal, target in (("COW", TARGET_COWS), ("SHEEP", TARGET_SHEEP)):
        current = animal_counts[animal] + shed_animal_pending[animal]
        cost = ANIMAL_COST[animal]
        buy_n = 0
        spend_preview = money
        while current + buy_n < target and spend_preview >= cost + 200 and buy_n < 2:
            spend_preview -= cost
            buy_n += 1
        if buy_n > 0:
            market.append(["BUY_ANIMAL", animal, buy_n])
            money -= cost * buy_n
            shed_animal_pending[animal] += buy_n

    # --- 4. Feed reserve ---
    total_animals = animal_counts["COW"] + animal_counts["SHEEP"] + animal_counts["GOOSE"]
    wheat_reserve_target = total_animals * FEED_BUFFER_DAYS
    wheat_have = int(shed.get("WHEAT", 0) or 0)
    if total_animals > 0 and wheat_have < wheat_reserve_target and hour < 20:
        need = wheat_reserve_target - wheat_have
        if money >= need * 30:
            market.append(["BUY_PRODUCT", "WHEAT", need])
            money -= need * 25
            wheat_have += need

    # --- 5. Reactive selling ---
    for item, base in BASE_PRICES.items():
        avail = int(shed.get(item, 0) or 0)
        if item == "WHEAT":
            avail = max(0, avail - wheat_reserve_target)
        elif item in LOW_VALUE_BUFFER:
            avail = max(0, avail - LOW_VALUE_BUFFER[item])
        if avail <= 0:
            continue
        price = market_prices.get(item, base)
        if item in LOW_VALUE_ITEMS:
            sell_ok = price >= base * LOW_VALUE_MIN_PRICE_RATIO
        else:
            sell_ok = price >= base * SELL_PRICE_RATIO
        if sell_ok and len(market) < 10:
            market.append(["SELL", item, min(avail, 20)])

    # --- 6. Terminal liquidation ---
    if step >= 716:
        planned = {o[1]: o[2] for o in market if o[0] == "SELL"}
        for item in BASE_PRICES:
            avail = max(0, int(shed.get(item, 0) or 0) - planned.get(item, 0))
            if avail > 0 and len(market) < 10:
                market.append(["SELL", item, avail])

    market = market[:10]

    # --- 7. Build shared context for task assignment, then decide each actor ---
    empty_pasture_needed = max(0, (shed_animal_pending["COW"] + shed_animal_pending["SHEEP"]) - len(_find_tiles(tiles, unlocked_quads, lambda t: isinstance(t, dict) and t.get("kind") == "PASTURE" and "animal" not in t)))
    context = {
        "empty_structures": {
            "PASTURE": _find_tiles(tiles, unlocked_quads, lambda t: isinstance(t, dict) and t.get("kind") == "PASTURE" and "animal" not in t),
            "COOP": _find_tiles(tiles, unlocked_quads, lambda t: isinstance(t, dict) and t.get("kind") == "COOP" and "animal" not in t),
        },
        "needs_feed": _find_tiles(tiles, unlocked_quads, lambda t: isinstance(t, dict) and "animal" in t and not t.get("fed_today")),
        "needs_care": _find_tiles(tiles, unlocked_quads, lambda t: isinstance(t, dict) and "animal" in t and not t.get("cared_today")),
        "needs_fert_collect": _find_tiles(tiles, unlocked_quads, lambda t: isinstance(t, dict) and "animal" in t and t.get("fertilizer_available")),
        "shed_animals_waiting": ([("COW",)] * shed_animal_pending["COW"] + [("SHEEP",)] * shed_animal_pending["SHEEP"]),
        "wheat_in_shed": wheat_have,
        "need_pasture": empty_pasture_needed,
        "buildable_tiles": _find_tiles(tiles, unlocked_quads, lambda t: t is None),
        "shed_pickup_this_step": [],
    }
    context["shed_animals_waiting"] = [a[0] for a in context["shed_animals_waiting"]]

    farmer_inv = inventories[0] if inventories else {}
    farmer_act = _actor_action(farmer_pos, farmer_inv, tiles, unlocked_quads, context)
    if not farmer_act:
        farmer_act = ["PASS"]

    hands_act = []
    for i, hpos in enumerate(hands_pos):
        hand_inv = inventories[i + 1] if len(inventories) > i + 1 else {}
        act = _actor_action(hpos, hand_inv, tiles, unlocked_quads, context)
        hands_act.append(act if act else ["PASS"])

    return {"farmer": farmer_act, "hands": hands_act, "market": market}


def agent(obs: Dict[str, Any], config: Any = None) -> Dict[str, Any]:
    try:
        return _agent_impl(obs)
    except Exception:
        player = obs.get("player", 0) if isinstance(obs, dict) else 0
        farms = obs.get("farms", []) if isinstance(obs, dict) else []
        me = farms[player] if len(farms) > player and isinstance(farms[player], dict) else {}
        hands_count = len(me.get("hands", []) or [])
        return {"farmer": ["PASS"], "hands": [["PASS"] for _ in range(hands_count)], "market": []}
