
import json
import base64
import zlib
import copy
import math
import os

_TAPE = None
TAPE_FILE = "blind_hybrid_tape.json"


def _tape_path():
    """Resolve TAPE_FILE relative to this script's own directory, not the process's
    current working directory. A bare relative open(TAPE_FILE) only works if Kaggle's
    submission runner happens to cd into the extraction directory before executing
    the agent -- __file__-relative resolution works regardless, with the same
    /kaggle_simulations/agent/ sandbox fallback the original, previously-working
    main.py used for exactly this reason."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = "/kaggle_simulations/agent/"
        if not os.path.exists(base_dir):
            base_dir = os.getcwd()
    return os.path.join(base_dir, TAPE_FILE)

MARKET_I0 = 10000
PRICE_FLOOR = 1.0
MAX_ORDERS = 10

LAND_ORDER = ["NE", "SW", "SE"]
LAND_PRICES = [1000, 2000, 4000]

CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2,  "max_yield_day": 4,  "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2,  "max_yield_day": 3,  "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8,  "max_yield_day": 8,  "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

# AMM constants
PRODUCTS = {
    "WHEAT":      {"base":  25, "I0": MARKET_I0, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "I0": MARKET_I0, "T": 450, "below_func": "log",    "below_target": 0.20, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "I0": MARKET_I0, "T": 332, "below_func": "linear", "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

SHOPS = {
    "BAKERY": ["EGG", "WHEAT"], "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"], "YARN_STORE": ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"], "PET_CAFE": ["CARROT"],
    "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}
ARCHETYPES = sorted(SHOPS)

def _shape(func, x):
    x = max(0.0, x)
    if func == "linear": return x
    if func == "sq":     return x * x
    if func == "sqrt":   return math.sqrt(x)
    if func == "log":    return math.log1p(x)
    if func == "log10":  return math.log10(1.0 + x)
    return x

def sell_proceeds(inv0, q, item):
    if q <= 0: return 0.0
    p = PRODUCTS[item]
    base, I0, T = p["base"], p["I0"], p["T"]
    above_target, f_above = p["above_target"], p["above_func"]
    below_target, f_below = p["below_target"], p["below_func"]

    amp_above = above_target * base / _shape(f_above, T)
    amp_below = below_target * base / _shape(f_below, T)
    revenue = 0.0
    inv = inv0

    for _ in range(q):
        if inv >= I0:
            price = max(PRICE_FLOOR, base - amp_above * _shape(f_above, inv - I0))
        else:
            # Real below-I0 (scarcity) pricing -- flattening this to `base` used to
            # discard real premium both for the *current* inventory (if it's already
            # below I0) and for any projected future scarcity from town-shop drain.
            price = max(PRICE_FLOOR, base + amp_below * _shape(f_below, I0 - inv))
        revenue += price
        if price > PRICE_FLOOR:
            inv += 1
    return revenue

def forecast_shop_drain(item, unlocked_shops, steps_remaining):
    current_rate = 0
    for s in unlocked_shops:
        prods = SHOPS[s]
        multiplier = 2 if len(prods) == 1 else 1
        if item in prods: current_rate += multiplier
        
    R = 8 - len(unlocked_shops)
    p_hit = sum(1 for a in ARCHETYPES if item in SHOPS[a]) / 8.0
    
    hit_drain = 0
    hits = [ (2 if len(SHOPS[a])==1 else 1) for a in ARCHETYPES if item in SHOPS[a] ]
    if hits: hit_drain = sum(hits)/len(hits)
    
    ticks_left = steps_remaining // 4 # townShopSellInterval=4
    exp_rate = current_rate + R * p_hit * hit_drain
    return int(exp_rate * ticks_left)

class OpponentModel:
    def __init__(self):
        self.forecast_queue = []
        
    def update(self, obs):
        player = obs.get("player", 0)
        opp = 1 - player
        opp_farm = obs.get("farms", [{}, {}])[opp]
        opp_tiles = opp_farm.get("tiles", [])
        
        # Super simple harvest forecast
        harvests = {}
        for row in opp_tiles:
            for t in row:
                if isinstance(t, dict) and t.get("kind") == "PLANT":
                    crop = t.get("crop")
                    y = t.get("yield_units", 0)
                    if y > 0: harvests[crop] = harvests.get(crop, 0) + y
                elif isinstance(t, dict) and t.get("kind") in ("COOP", "PASTURE"):
                    animal = t.get("animal")
                    y = t.get("yield_units", 0)
                    if y > 0: harvests[animal] = harvests.get(animal, 0) + y
                    
        self.forecast_queue.append(harvests)
        if len(self.forecast_queue) > 5:
            self.forecast_queue.pop(0)
            
    def get_forecast(self, horizon=5):
        return self.forecast_queue[-horizon:] if self.forecast_queue else []

def get_candidates(tapes, cur_id, step, H):
    candidates = []
    tape_cur = tapes.get(cur_id, [])
    
    base_actions = []
    for i in range(H):
        if step + i < len(tape_cur):
            base_actions.append(copy.deepcopy(tape_cur[step + i]))
        else:
            base_actions.append({"farmer": ["PASS"], "hands": [], "market": []})
            
    candidates.append({"tape_id": cur_id, "actions": copy.deepcopy(base_actions), "type": "base"})
    
    adv_actions = copy.deepcopy(base_actions)
    sales_to_advance = []
    for i, act in enumerate(adv_actions):
        for order in act.get("market", []):
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL" and i > 0:
                sales_to_advance.append((i, order))
                
    if sales_to_advance:
        for i, order in sales_to_advance:
            cand = copy.deepcopy(base_actions)
            if order in cand[i].get("market", []):
                cand[i]["market"].remove(order)
            cand[0].setdefault("market", []).insert(0, order)
            candidates.append({"tape_id": cur_id, "actions": cand, "type": "front_run"})
            
    return candidates

def compute_score(candidate, obs, H, opp_forecast):
    G_profit = 0.0
    G_defense = 0.0

    market_inv = obs.get("market", {}).get("inventory", {})
    unlocked_shops = obs.get("town", {}).get("unlocked_shops", [])
    my_shed = (obs.get("private") or {}).get("shed", {})

    opp_dump_items = set()
    if opp_forecast:
        for d in opp_forecast:
            opp_dump_items.update(d.keys())

    for i, step_data in enumerate(candidate["actions"]):
        for order in step_data.get("market", []):
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                item = order[1]
                qty = int(order[2] or 0)

                # We can only actually check feasibility for the action we're about
                # to submit this real step (i == 0) -- our own shed a few steps into
                # this candidate's hypothetical future isn't known. Without this,
                # a front-run of an item we don't hold yet could still score well
                # here and then silently no-op against the live engine (_commit_unit
                # just returns False on an empty shed), while get_candidates() has
                # already dropped that same order from its originally-achievable
                # future slot -- and since nothing persists the front-run (see the
                # _TAPE write-back in agent()), a doomed front-run risks not just
                # wasting this step but also duplicating or losing the real sale.
                if i == 0 and my_shed.get(item, 0) < qty:
                    return -1e9

                inv0 = market_inv.get(item, MARKET_I0)
                proceeds_now = sell_proceeds(inv0, qty, item)

                # Forecast drain over the steps between now and *this order's own
                # slot* (i steps away), not over the whole rest of the game -- H is
                # the actual replanning horizon, and comparing "sell now" against
                # "sell after the entire remaining game has drained" was comparing
                # against a horizon this decision doesn't actually reach (the agent
                # re-plans from scratch again next step regardless).
                ticks_ahead = max(i, 1) * 4  # townShopSellInterval=4
                drain = forecast_shop_drain(item, unlocked_shops, ticks_ahead)
                inv_later = max(0, inv0 - drain)  # not MARKET_I0 -- I0 is a
                # reference point, not a floor; flooring here discarded any
                # projected scarcity that would have pushed inventory genuinely
                # below I0, which is exactly the case this comparison exists for.
                proceeds_later = sell_proceeds(inv_later, qty, item)

                # If proceeds_later > proceeds_now, we are losing money by selling now!
                if proceeds_later > proceeds_now:
                    G_profit -= (proceeds_later - proceeds_now) * 1.5 # Penalize selling early if later is better
                else:
                    G_profit += proceeds_now

                # Front run logic
                if item in opp_dump_items:
                    if i == 0:
                        G_defense += 200.0
                    else:
                        G_defense -= 500.0

    return G_profit + G_defense

def _fib(n):
    if n <= 1: return 1
    a, b = 1, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

SHED_ACCESS = {(4, 4), (5, 4), (4, 5), (5, 5)}
CARROT_TILES_PER_HAND = 4
LAND_DEV_MARGIN_MIN = 0.0
LAND_DEV_RESERVE_BUFFER = 500

_LAND_DEV = {"tiles": {}, "hand_map": {}, "last_day": -1, "started": False}


def _quadrant_of_dev(x, y, board_size):
    half = board_size // 2
    return ("N" if y < half else "S") + ("W" if x < half else "E")


def _step_toward_dev(hx, hy, tx, ty):
    if hx < tx: return "EAST"
    if hx > tx: return "WEST"
    if hy < ty: return "SOUTH"
    if hy > ty: return "NORTH"
    return "PASS"


def _find_new_land(farm, claimed, limit):
    tiles = farm.get("tiles", [])
    size = len(tiles)
    out = []
    for y in range(size):
        for x in range(size):
            if len(out) >= limit:
                return out
            if (x, y) in SHED_ACCESS or (x, y) in claimed:
                continue
            if _quadrant_of_dev(x, y, size) == "NW":
                continue
            if tiles[y][x] is None:
                out.append((x, y))
    return out


def _revenue_est_carrot(q):
    """O(1) closed-form pre-screen for CARROT's above-branch (sqrt) curve, used only
    to decide whether to commit to a land purchase. sell_proceeds() is still the
    real source of truth for actual sell decisions."""
    if q <= 0:
        return 0.0
    p = PRODUCTS["CARROT"]
    amp = p["above_target"] * p["base"] / _shape(p["above_func"], p["T"])
    return max(0.0, q * p["base"] - amp * (2.0 / 3.0) * (q ** 1.5))


def _count_unscripted_hands(action, obs):
    player = obs.get("player", 0)
    farms = obs.get("farms") or [{}] * (player + 1)
    farm = farms[player] if player < len(farms) else {}
    live_hands = farm.get("hands", [])
    tape_hands = action.get("hands", [])
    return max(0, len(live_hands) - len(tape_hands))


def _projected_land_margin(obs, step, land_price, n_tiles, n_new_hires):
    """The direct fix for the failed bolt-on attempt: a land+hire+seed bundle is only
    approved when *modeled* revenue clears *modeled* cost by a real margin, not
    merely 'not obviously negative'."""
    if n_tiles <= 0:
        return False, 0.0, 0.0
    steps_left = 720 - step
    days_left = steps_left // 24
    cycle_days = CROPS["CARROT"]["max_yield_day"]
    ramp_days = 1
    cycles = max(0, (days_left - ramp_days) // cycle_days)
    if cycles == 0:
        return False, 0.0, 0.0

    player = obs.get("player", 0)
    farms = obs.get("farms") or [{}] * (player + 1)
    farm = farms[player] if player < len(farms) else {}
    start_idx = farm.get("hires_today", 0)
    wage_per_day = sum(_fib(start_idx + i) for i in range(1, n_new_hires + 1))
    wage_cost = wage_per_day * days_left

    units_per_cycle = n_tiles * CROPS["CARROT"]["max_yield"]
    seed_cost = n_tiles * cycles * CROPS["CARROT"]["seed"]
    revenue = cycles * _revenue_est_carrot(units_per_cycle)

    cost = land_price + seed_cost + wage_cost
    net = revenue - cost
    margin = net / cost if cost > 0 else 0.0
    money_ok = farm.get("money", 0) >= cost + LAND_DEV_RESERVE_BUFFER
    return (net > 0 and margin >= LAND_DEV_MARGIN_MIN and money_ok), net, margin


def _try_develop_new_quadrant(action, obs, step):
    """Buy the next land quadrant ONLY as an atomic bundle with the hires and seed
    order needed to work it -- never land in isolation. Gated on a hard projected
    profit-margin check (see _projected_land_margin)."""
    player = obs.get("player", 0)
    farms = obs.get("farms") or [{}] * (player + 1)
    farm = farms[player] if player < len(farms) else {}
    unlocked = farm.get("unlocked_quadrants", ["NW"])
    n_extra_owned = max(0, len(unlocked) - 1)
    if n_extra_owned >= len(LAND_ORDER):
        return
    land_price = LAND_PRICES[n_extra_owned]

    idle_hands = _count_unscripted_hands(action, obs)
    n_tiles = min(25, (idle_hands + 2) * CARROT_TILES_PER_HAND)
    n_new_hires = max(0, (n_tiles // CARROT_TILES_PER_HAND) - idle_hands)

    ok, net, margin = _projected_land_margin(obs, step, land_price, n_tiles, n_new_hires)
    if not ok:
        return

    market = action.setdefault("market", [])
    if len(market) >= MAX_ORDERS:
        return
    market.append(["BUY_LAND"])
    for _ in range(n_new_hires):
        if len(market) >= MAX_ORDERS:
            break
        market.append(["HIRE"])
    if len(market) < MAX_ORDERS:
        market.append(["BUY_SEED", "CARROT", n_tiles])


def _route_land_dev_hands(action, obs, step):
    """Assign whatever hands the tape doesn't script to a CARROT tile-development
    lifecycle (EMPTY -> GROWING -> CARRYING -> EMPTY). State is keyed by TILE, not
    hand index, since hands are wiped and re-hired every night -- a hand-index ->
    tile mapping from yesterday is meaningless once today's hands are freshly hired.
    """
    player = obs.get("player", 0)
    farms = obs.get("farms") or [{}] * (player + 1)
    farm = farms[player] if player < len(farms) else {}
    private = obs.get("private", {}) or {}
    tiles = farm.get("tiles", [])
    live_hands = farm.get("hands", [])
    day = step // 24

    if step == 0:
        _LAND_DEV["tiles"].clear()
        _LAND_DEV["hand_map"].clear()
        _LAND_DEV["last_day"] = -1

    n_unscripted = _count_unscripted_hands(action, obs)
    if n_unscripted <= 0:
        return

    claimed = set(_LAND_DEV["tiles"].keys())
    while len(_LAND_DEV["tiles"]) < n_unscripted:
        new_tile = _find_new_land(farm, claimed, 1)
        if not new_tile:
            break
        pos = new_tile[0]
        _LAND_DEV["tiles"][pos] = {"state": "EMPTY", "planted_day": None}
        claimed.add(pos)

    if day != _LAND_DEV["last_day"]:
        _LAND_DEV["last_day"] = day
        unscripted_idx = list(range(len(action.get("hands", [])), len(live_hands)))
        tile_keys = sorted(_LAND_DEV["tiles"].keys())
        _LAND_DEV["hand_map"] = dict(zip(unscripted_idx, tile_keys))

    tape_hands = action.setdefault("hands", [])
    inventories = private.get("inventories", [])
    market = action.setdefault("market", [])

    for hand_idx, pos in list(_LAND_DEV["hand_map"].items()):
        if hand_idx >= len(live_hands):
            continue
        while len(tape_hands) <= hand_idx:
            tape_hands.append(["PASS"])
        if tape_hands[hand_idx] != ["PASS"]:
            continue  # already scripted by the tape or a higher-priority overlay

        hx, hy = live_hands[hand_idx]
        st = _LAND_DEV["tiles"].get(pos)
        if st is None:
            continue
        tile = None
        if 0 <= pos[1] < len(tiles) and 0 <= pos[0] < len(tiles[0] if tiles else []):
            tile = tiles[pos[1]][pos[0]]

        # Self-healing: something other than our own crop occupies the tile.
        if st["state"] in ("GROWING",) and not (isinstance(tile, dict) and tile.get("kind") == "PLANT" and tile.get("crop") == "CARROT"):
            if isinstance(tile, dict) and tile.get("kind") == "WEED":
                if (hx, hy) == pos:
                    tape_hands[hand_idx] = ["DIG"]
                else:
                    tape_hands[hand_idx] = [_step_toward_dev(hx, hy, pos[0], pos[1])]
                continue
            del _LAND_DEV["tiles"][pos]
            continue

        if st["state"] == "EMPTY":
            if (hx, hy) != pos:
                tape_hands[hand_idx] = [_step_toward_dev(hx, hy, pos[0], pos[1])]
                continue
            if private.get("seeds", {}).get("CARROT", 0) < 1:
                if len(market) < MAX_ORDERS:
                    market.append(["BUY_SEED", "CARROT", 4])
                tape_hands[hand_idx] = ["PASS"]
                continue
            tape_hands[hand_idx] = ["PLANT", "CARROT"]
            st["state"] = "GROWING"
            st["planted_day"] = day
            continue

        if st["state"] == "GROWING":
            if (hx, hy) != pos:
                tape_hands[hand_idx] = [_step_toward_dev(hx, hy, pos[0], pos[1])]
                continue
            if not isinstance(tile, dict):
                del _LAND_DEV["tiles"][pos]
                continue
            age = day - (st["planted_day"] if st["planted_day"] is not None else day)
            cd = CROPS["CARROT"]
            if age >= 2 and not tile.get("watered_today") and tile.get("yield_units", 0) < cd["max_yield"]:
                tape_hands[hand_idx] = ["WATER"]
            elif age >= cd["first_yield_day"] and tile.get("yield_units", 0) > 0:
                tape_hands[hand_idx] = ["HARVEST"]
                st["state"] = "CARRYING"
            else:
                tape_hands[hand_idx] = ["PASS"]
            continue

        if st["state"] == "CARRYING":
            inv_idx = hand_idx + 1  # inventories[0] is the farmer's own
            carried = inventories[inv_idx].get("CARROT", 0) if inv_idx < len(inventories) else 0
            if carried <= 0:
                st["state"] = "EMPTY"
                st["planted_day"] = None
                tape_hands[hand_idx] = ["PASS"]
                continue
            if (hx, hy) not in SHED_ACCESS:
                target = min(SHED_ACCESS, key=lambda q: abs(q[0] - hx) + abs(q[1] - hy))
                tape_hands[hand_idx] = [_step_toward_dev(hx, hy, target[0], target[1])]
            else:
                tape_hands[hand_idx] = ["DROP"]
            continue


def _sell_carrot(action, obs):
    """Reuse the existing hold-vs-sell-now check (same functions already used for
    front-running scheduled sells) rather than auto-selling on harvest or adding a
    new open-ended deferral rule -- CARROT has no BUY_PRODUCT price-support lever,
    so this timing check is its only downside protection."""
    private = obs.get("private", {}) or {}
    qty = private.get("shed", {}).get("CARROT", 0)
    if qty <= 0:
        return
    market_inv = obs.get("market", {}).get("inventory", {})
    unlocked_shops = obs.get("town", {}).get("unlocked_shops", [])
    inv0 = market_inv.get("CARROT", MARKET_I0)
    proceeds_now = sell_proceeds(inv0, qty, "CARROT")
    drain = forecast_shop_drain("CARROT", unlocked_shops, 20)
    proceeds_later = sell_proceeds(max(0, inv0 - drain), qty, "CARROT")
    market = action.setdefault("market", [])
    if proceeds_now >= proceeds_later and len(market) < MAX_ORDERS:
        market.append(["SELL", "CARROT", qty])


def scavenger_overlay(action, obs):
    """Ported from the reference main.py: routes any hand the tape leaves unscripted
    toward the nearest weed instead of leaving it idle. draft_main_v4.py had no
    fallback at all for unscripted hands -- a regression from the working agent."""
    player = obs["player"]
    farm = obs.get("farms", [])[player]
    live_hands = farm.get("hands", [])
    tape_hands = action.get("hands", [])

    while len(tape_hands) < len(live_hands):
        hand_idx = len(tape_hands)
        hx, hy = live_hands[hand_idx]

        weed_target = None
        for y in range(len(farm["tiles"])):
            for x in range(len(farm["tiles"][y])):
                t = farm["tiles"][y][x]
                if isinstance(t, dict) and t.get("kind") == "WEED":
                    dist = abs(hx - x) + abs(hy - y)
                    if weed_target is None or dist < weed_target[2]:
                        weed_target = (x, y, dist)

        if weed_target:
            tx, ty, d = weed_target
            if d == 0:
                tape_hands.append(["DIG"])
            else:
                if hx < tx: tape_hands.append(["EAST"])
                elif hx > tx: tape_hands.append(["WEST"])
                elif hy < ty: tape_hands.append(["SOUTH"])
                elif hy > ty: tape_hands.append(["NORTH"])
        else:
            tape_hands.append(["PASS"])

    action["hands"] = tape_hands

opp_model = OpponentModel()

def agent(obs, config=None):
    global _TAPE
    if _TAPE is None:
        path = _tape_path()
        try:
            with open(path, "r") as f:
                _TAPE = json.load(f)
        except Exception as e:
            # Swallowing this silently meant a bad path/cwd/JSON on the Kaggle host
            # would make the agent PASS for all 720 steps with zero indication why.
            print(f"[FATAL] tape load failed ({path}): {e}")
            _TAPE = []

    step = obs.get("step", 0)
    opp_model.update(obs)

    tapes = {"t1": _TAPE}
    candidates = get_candidates(tapes, "t1", step, 5)

    best_cand = None
    best_score = -float("inf")

    opp_forecast = opp_model.get_forecast(5)

    for cand in candidates:
        score = compute_score(cand, obs, 5, opp_forecast)
        if score > best_score:
            best_score = score
            best_cand = cand

    # Persist a won front-run back into the tape itself. Without this, the original
    # future slot for the same sale is untouched, and since shed inventory keeps
    # growing from ongoing farming, the tape is likely to resubmit -- and this time
    # actually execute -- the same sale again later: a double-sell, not a safe no-op.
    if best_cand and best_cand.get("type") == "front_run":
        for i_step, act in enumerate(best_cand["actions"]):
            if step + i_step < len(_TAPE):
                _TAPE[step + i_step] = act

    action = best_cand["actions"][0] if best_cand else {"farmer": ["PASS"], "hands": [], "market": []}
    _try_develop_new_quadrant(action, obs, step)
    _route_land_dev_hands(action, obs, step)
    _sell_carrot(action, obs)
    scavenger_overlay(action, obs)
    return action

