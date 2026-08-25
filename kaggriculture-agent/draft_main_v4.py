
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

MAX_ORDERS = 10

# --- Terminal liquidation -----------------------------------------------
# From the decoded top-100 agent: in the last few steps, sell everything left
# in shed regardless of forecast. No forecasting needed this close to the end
# -- holding inventory past game-over is strictly worse than selling it at
# whatever price is available right now.
_LIQUIDATION_ITEMS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
                      "EGG", "MILK", "WOOL", "FERTILIZER")

def _terminal_liquidation(obs, action, step):
    if step < 716:
        return action
    shed = (obs.get("private") or {}).get("shed", {}) or {}
    market = action.setdefault("market", [])
    planned = {}
    for order in market:
        if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
            planned[order[1]] = planned.get(order[1], 0) + max(0, int(order[2] or 0))
    for item in _LIQUIDATION_ITEMS:
        available = max(0, int(shed.get(item, 0) or 0) - planned.get(item, 0))
        if available > 0 and len(market) < MAX_ORDERS:
            market.append(["SELL", item, available])
    return action


# --- Family-B detection ---------------------------------------------------
# Verified against 14 real losses: the recurring "Family-B" opponent hits
# quadrants>=2, cows>=4, sheep<=2 at step 160 in every single one, exactly
# matching a real top-100 player's own "MD" archetype signature -- this is
# the same real opponent population, not a coincidental resemblance.
_FAMILY_B_STATE = {"last_step": -1, "detected": False}

def _detect_family_b(obs, step):
    state = _FAMILY_B_STATE
    if step == 0 or step < state["last_step"]:
        state["last_step"] = step
        state["detected"] = False
    state["last_step"] = step
    if state["detected"] or step < 160:
        return state["detected"]
    player = obs.get("player", 0)
    farms = obs.get("farms") or [{}] * (player + 1)
    opp_farm = farms[1 - player] if len(farms) > 1 - player else {}
    cows = sheep = 0
    for row in opp_farm.get("tiles", []) or []:
        for tile in row or []:
            if isinstance(tile, dict):
                if tile.get("animal") == "COW":
                    cows += 1
                elif tile.get("animal") == "SHEEP":
                    sheep += 1
    quadrants = len(opp_farm.get("unlocked_quadrants", []) or [])
    if quadrants >= 2 and cows >= 4 and sheep <= 2:
        state["detected"] = True
    return state["detected"]


# --- Family-B counter: front-run our own future premium sells -------------
# From the decoded top-100 agent: once this archetype is detected, pull a
# fraction of our OWN already-scheduled near-future sells for the shared
# premium items forward to today, rather than changing what we produce or
# buy. We track a "debt" (due_step/due) and repay it by shrinking the real
# future order when it actually arrives, instead of mutating the tape in
# place -- avoids the double-sell risk a naive pull-forward would create.
# Measured against the only live sparring proxy available (a cow-heavy tape, not the
# real Family-B opponent -- we only have their historical replay trace, not runnable
# code): the detector fires correctly (confirmed), but the counter itself scored a
# small net NEGATIVE (-0.24%, 120969 vs 121255 baseline over 10 games) versus doing
# nothing. Left present but disabled pending a better test opponent or retuning --
# same "implemented but not promoted" outcome as the three prior gap-closing attempts.
_FAMILY_B_COUNTER_ENABLED = False
_FAMILY_B_ITEMS = ("MELON", "MILK", "STRAWBERRY", "WOOL")
_FAMILY_B_FRACTION = 0.5
_FAMILY_B_LOOKAHEAD = 96  # steps (4 days) to search the tape for the next scheduled sell
_FAMILY_B_SHIFT = {"last_step": -1, "due_step": -1, "due": {}}

def _family_b_repay(obs, action, step):
    state = _FAMILY_B_SHIFT
    if step == 0 or step < state["last_step"]:
        state.update(last_step=step, due_step=-1, due={})
        return action
    state["last_step"] = step
    if state["due_step"] != step or not state["due"]:
        if state["due_step"] < step:
            state["due_step"], state["due"] = -1, {}
        return action
    due = dict(state["due"])
    market = []
    for raw in action.get("market", []) or []:
        order = list(raw)
        if len(order) >= 3 and order[0] == "SELL" and due.get(order[1], 0) > 0:
            item = order[1]
            qty = max(0, int(order[2] or 0))
            reduction = min(qty, due[item])
            qty -= reduction
            due[item] -= reduction
            if qty <= 0:
                continue
            order[2] = qty
        market.append(order)
    action["market"] = market
    state["due_step"], state["due"] = -1, {}
    return action


def _family_b_counter(obs, action, step):
    if not _FAMILY_B_COUNTER_ENABLED or not _detect_family_b(obs, step) or not _TAPE:
        return action
    if _FAMILY_B_SHIFT.get("due"):
        return action  # don't stack a second pull-forward before the first is repaid
    shed = (obs.get("private") or {}).get("shed", {}) or {}
    market = action.setdefault("market", [])
    already_selling = {}
    for order in market:
        if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
            already_selling[order[1]] = already_selling.get(order[1], 0) + max(0, int(order[2] or 0))

    shifted = {}
    for item in _FAMILY_B_ITEMS:
        found_step, found_qty = None, 0
        for i in range(1, _FAMILY_B_LOOKAHEAD + 1):
            idx = step + i
            if idx >= len(_TAPE):
                break
            for raw in _TAPE[idx].get("market", []) or []:
                if isinstance(raw, list) and len(raw) >= 3 and raw[0] == "SELL" and raw[1] == item:
                    found_step, found_qty = idx, max(0, int(raw[2] or 0))
                    break
            if found_step is not None:
                break
        if found_step is None or found_qty <= 0:
            continue
        available = max(0, int(shed.get(item, 0) or 0) - already_selling.get(item, 0))
        pull = min(available, max(1, int(round(found_qty * _FAMILY_B_FRACTION))))
        if pull <= 0 or len(market) >= MAX_ORDERS:
            continue
        market.append(["SELL", item, pull])
        already_selling[item] = already_selling.get(item, 0) + pull
        shifted[item] = shifted.get(item, 0) + pull
        targets = _FAMILY_B_SHIFT.setdefault("_targets", {})
        if item not in targets:
            targets[item] = found_step

    if shifted:
        # Record repayment against the exact tape step each item's sale was found at.
        targets = _FAMILY_B_SHIFT.pop("_targets", {})
        by_step = {}
        for item, qty in shifted.items():
            due_step = targets.get(item, step + 1)
            by_step.setdefault(due_step, {})[item] = qty
        # Only one due_step is tracked at a time by _family_b_repay; if items landed
        # on different future steps, repay against the earliest (most conservative).
        earliest = min(by_step)
        _FAMILY_B_SHIFT["due_step"] = earliest
        _FAMILY_B_SHIFT["due"] = by_step[earliest]
    action["market"] = market[:MAX_ORDERS]
    return action


def _agent_impl(obs, config=None):
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
    action = _family_b_repay(obs, action, step)
    action = _family_b_counter(obs, action, step)
    action = _terminal_liquidation(obs, action, step)
    scavenger_overlay(action, obs)
    return action


def agent(obs, config=None):
    try:
        return _agent_impl(obs, config)
    except Exception:
        player = obs.get("player", 0) if isinstance(obs, dict) else 0
        farms = obs.get("farms", []) if isinstance(obs, dict) else []
        me = farms[player] if len(farms) > player else {}
        hands_count = len(me.get("hands", []) or [])
        return {"farmer": ["PASS"], "hands": [["PASS"] for _ in range(hands_count)], "market": []}

