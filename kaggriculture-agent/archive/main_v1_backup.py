"""Kaggriculture agent - single file submission.

Strategy summary
----------------
The season's money is capped by what the *town* drains from the market, not by
what we can grow.  Per-season town drain at base price is roughly:

    MILK 327 x $160 = $52k    STRAWBERRY 426 x $120 = $51k
    WOOL 228 x $200 = $46k    TOMATO 228 x $60 = $14k
    WHEAT 525 x $25 = $13k    CARROT 327 x $35 = $11k
    EGG  228 x $50  = $11k    MELON 30 x $250 = $8k

On top of that, EGG / WHEAT have log-shaped glut curves (they stay near $38 /
$19 no matter how much you dump), and MELON / FERTILIZER absorb ~$26k / ~$25k
of overproduction before hitting the floor.  So:

  1. Saturate the premium drains (milk, wool, strawberry) - animals first,
     because CARE makes them 3-4x better per tile than any crop.  Cows get the
     lion's share: milk is the biggest single market and stays undersupplied.
  2. Dump the surplus action budget into geese/eggs and melon, which do not
     crash.
  3. Never sell below a per-product reserve price; that keeps inventory near
     I0 where the price is highest.  Reserves collapse over the last few days
     so the shed is fully liquidated before the game ends.
  4. Buy the extra quadrants as tiles run short - land is cheap versus a
     tile's $50-250/day earning power, but early cash is better spent on the
     first animals, whose payback clock starts 6-8 days out.
  5. Hire hands hard.  Fib pricing means ~12 hands cost a few hundred a day for
     hundreds of extra actions, each worth $20-100.  Labour, not cash, is the
     real ceiling, so the herd is deliberately capped (~24) at the size the
     crew can actually feed, care for, and harvest every day.

Execution is a greedy value/(1+distance)^p task scheduler over every unit.
The best knobs were found by the sweep harness in sweep.py.
"""

import math
import time
import random

# --------------------------------------------------------------------------
# game tables (mirrored from kaggriculture.py)
# --------------------------------------------------------------------------
TPD = 24
FINAL_DAY = 29

CROPS = {
    "WHEAT":      {"seed": 10,  "first": 2,  "maxday": 4,  "interval": 0, "cap": 6, "ongoing": False},
    "CARROT":     {"seed": 20,  "first": 2,  "maxday": 3,  "interval": 0, "cap": 4, "ongoing": False},
    "TOMATO":     {"seed": 50,  "first": 8,  "maxday": 8,  "interval": 1, "cap": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first": 10, "maxday": 10, "interval": 2, "cap": 4, "ongoing": True},
    "MELON":      {"seed": 80,  "first": 10, "maxday": 12, "interval": 0, "cap": 6, "ongoing": False},
}

ANIMALS = {
    "GOOSE": {"cost": 300, "struct": "COOP",    "first": 4, "interval": 1, "held": 4, "prod": "EGG"},
    "COW":   {"cost": 400, "struct": "PASTURE", "first": 8, "interval": 2, "held": 6, "prod": "MILK"},
    "SHEEP": {"cost": 500, "struct": "PASTURE", "first": 6, "interval": 3, "held": 6, "prod": "WOOL"},
}

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON",
            "EGG", "MILK", "WOOL", "FERTILIZER"]

MARKET_PARAMS = {
    "WHEAT":      {"base":  25, "I0": 10000, "T": 400, "bf": "sqrt",   "bt": 0.80, "af": "log",    "at": 0.20},
    "CARROT":     {"base":  35, "I0": 10000, "T": 450, "bf": "log",    "bt": 0.20, "af": "sqrt",   "at": 0.70},
    "TOMATO":     {"base":  60, "I0": 10000, "T": 200, "bf": "linear", "bt": 0.40, "af": "sqrt",   "at": 0.60},
    "STRAWBERRY": {"base": 120, "I0": 10000, "T": 100, "bf": "sqrt",   "bt": 0.70, "af": "linear", "at": 1.60},
    "MELON":      {"base": 250, "I0": 10000, "T": 300, "bf": "log",    "bt": 0.20, "af": "sq",     "at": 3.60},
    "EGG":        {"base":  50, "I0": 10000, "T": 332, "bf": "linear", "bt": 0.40, "af": "log",    "at": 0.20},
    "MILK":       {"base": 160, "I0": 10000, "T": 122, "bf": "sqrt",   "bt": 0.60, "af": "linear", "at": 1.60},
    "WOOL":       {"base": 200, "I0": 10000, "T": 105, "bf": "log",    "bt": 0.20, "af": "sq",     "at": 3.20},
    "FERTILIZER": {"base": 100, "I0": 10000, "T": 200, "bf": "linear", "bt": 0.40, "af": "linear", "at": 0.40},
}

SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}

# expected units/day a single future shop instance drains, per product
_EXPECTED_SHOP_RATE = {}
for _p in PRODUCTS:
    _tot = 0.0
    for _s, _pl in SHOPS.items():
        if _p in _pl:
            _tot += 2.0 if len(_pl) == 1 else 1.0
    _EXPECTED_SHOP_RATE[_p] = 6.0 * _tot / len(SHOPS)

# Replay-informed opponent dump priors (loaded from historical logs)
REPLAY_DUMP_STATS = {
    "FERTILIZER": {"prob": 0.78, "avg_dump_qty": 180, "trigger_day": 6, "trigger_inv": 150, "velocity_threshold": -1.5},
    "EGG":        {"prob": 0.45, "avg_dump_qty": 90,  "trigger_day": 10, "trigger_inv": 100, "velocity_threshold": -1.0},
    "WHEAT":      {"prob": 0.30, "avg_dump_qty": 200, "trigger_day": 12, "trigger_inv": 200, "velocity_threshold": -1.0},
    "MILK":       {"prob": 0.20, "avg_dump_qty": 60,  "trigger_day": 15, "trigger_inv": 150, "velocity_threshold": -1.5},
    "WOOL":       {"prob": 0.15, "avg_dump_qty": 40,  "trigger_day": 15, "trigger_inv": 100, "velocity_threshold": -1.5},
}

# =============================================================================
# PHASE 3: LIGHTWEIGHT MCTS FOR STRATEGIC DECISIONS
# =============================================================================

# -----------------------------------------------------------------------------
# Strategic Action Space
# -----------------------------------------------------------------------------
STRATEGIC_ACTIONS = [
    ("MAINTAIN",),
    ("PIVOT_FROM", "FERTILIZER"),
    ("PIVOT_FROM", "EGG"),
    ("PIVOT_FROM", "MILK"),
    ("PIVOT_FROM", "WOOL"),
    ("PIVOT_TO", "STRAWBERRY"),
    ("PIVOT_TO", "MELON"),
    ("PIVOT_TO", "MILK"),
    ("PIVOT_TO", "WOOL"),
    ("HOARD", "FERTILIZER"),
    ("HOARD", "STRAWBERRY"),
    ("HOARD", "MELON"),
    ("SHORT", "FERTILIZER"),
    ("BUY_LAND",),
    ("HIRE_HANDS",),
]

# -----------------------------------------------------------------------------
# MCTS Node
# -----------------------------------------------------------------------------
class MCTSNode:
    __slots__ = ("state_hash", "parent", "children", "visits", "value", 
                 "action", "depth", "untried_actions")
    
    def __init__(self, state_hash, parent=None, action=None):
        self.state_hash = state_hash
        self.parent = parent
        self.children = {}
        self.visits = 0
        self.value = 0.0
        self.action = action
        self.depth = 0 if parent is None else parent.depth + 1
        self.untried_actions = None

# -----------------------------------------------------------------------------
# State Compression
# -----------------------------------------------------------------------------
def compress_state(st, plan):
    h = st.day
    h = (h << 6) | min(63, int(st.money // 5000))
    h = (h << 4) | min(15, plan.get("have", {}).get("COW", 0))
    h = (h << 4) | min(15, plan.get("have", {}).get("SHEEP", 0))
    h = (h << 4) | min(15, plan.get("have", {}).get("GOOSE", 0))
    for crop in ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"):
        cnt = sum(1 for row in st.tiles for t in row 
                  if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == crop)
        h = (h << 3) | min(7, cnt)
    for prod in ("FERTILIZER", "EGG", "MILK", "WOOL", "WHEAT"):
        inv_bin = min(15, int(st.minv.get(prod, 0) // 500))
        h = (h << 4) | inv_bin
    return h

# -----------------------------------------------------------------------------
# Opponent Dump Prediction (replay-informed)
# -----------------------------------------------------------------------------
def predict_opp_dumps(market_inv, day, current_dumps):
    dumps = {}
    for item, stats in REPLAY_DUMP_STATS.items():
        if current_dumps.get(item, False):
            dumps[item] = stats["avg_dump_qty"] / max(1, stats.get("duration", 10))
        elif day >= stats["trigger_day"] and market_inv.get(item, 0) >= stats["trigger_inv"]:
            if random.random() < stats["prob"]:
                dumps[item] = stats["avg_dump_qty"] / max(1, stats.get("duration", 10))
    return dumps

# -----------------------------------------------------------------------------
# Fast Forward Simulation (5-day horizon)
# -----------------------------------------------------------------------------
SIM_HORIZON = 5

def simulate(st, plan, strategic_action, seed=None):
    if seed is not None:
        random.seed(seed)
    
    money = st.money
    animals = dict(plan.get("have", {}))
    market_inv = dict(st.minv)
    pipeline = dict(plan.get("pipeline", {}))
    crop_targets = dict(plan.get("crop_targets", {}))
    opp_dumps_active = dict(plan.get("opp_dump", {}))
    
    action_type = strategic_action[0]
    
    if action_type == "PIVOT_FROM":
        item = strategic_action[1]
        if item in crop_targets:
            crop_targets[item] = 0
    
    elif action_type == "PIVOT_TO":
        item = strategic_action[1]
        if item in CROPS:
            crop_targets[item] = crop_targets.get(item, 0) + 3
    
    elif action_type == "BUY_LAND":
        if len(st.unlocked) < 4:
            cost = (1000, 2000, 4000)[len(st.unlocked) - 1]
            if money >= cost:
                money -= cost
    
    daily_drain = dict(plan.get("rate", {}))
    
    for day_offset in range(SIM_HORIZON):
        current_day = st.day + day_offset
        days_left = max(1, st.days_left - day_offset)
        wheat_price = market_price("WHEAT", market_inv.get("WHEAT", 0))
        
        new_dumps = predict_opp_dumps(market_inv, current_day, opp_dumps_active)
        for item, qty in new_dumps.items():
            market_inv[item] = market_inv.get(item, 0) + qty
            opp_dumps_active[item] = True
        
        for item, qty in pipeline.items():
            if days_left > 0:
                market_inv[item] = market_inv.get(item, 0) + qty / days_left
                
        # Approximate daily production based on targets
        for crop, count in crop_targets.items():
            if crop in CROPS:
                interval = CROPS[crop]["interval"]
                daily_yield = count * (1.5 / max(1, interval))
                daily_cost = count * (CROPS[crop]["seed"] / max(1, interval))
                market_inv[crop] = market_inv.get(crop, 0) + daily_yield
                money -= daily_cost
                
        for animal, count in animals.items():
            if animal == "COW":
                market_inv["MILK"] = market_inv.get("MILK", 0) + count * 0.75
                market_inv["FERTILIZER"] = market_inv.get("FERTILIZER", 0) + count * 0.75
            elif animal == "SHEEP":
                market_inv["WOOL"] = market_inv.get("WOOL", 0) + count * 0.5
                market_inv["FERTILIZER"] = market_inv.get("FERTILIZER", 0) + count * 0.5
            elif animal == "GOOSE":
                market_inv["EGG"] = market_inv.get("EGG", 0) + count * 0.5
                market_inv["FERTILIZER"] = market_inv.get("FERTILIZER", 0) + count * 0.5
        
        for item, rate in daily_drain.items():
            market_inv[item] = max(0, market_inv.get(item, 0) - rate)
        
        for item in PRODUCTS:
            reserve = plan.get("reserve", {}).get(item, 1)
            inv = market_inv.get(item, 0)
            sellable = units_sellable(item, inv, reserve, 9999)
            if sellable > 0:
                price = market_price(item, inv - sellable + 1)
                money += sellable * price
                market_inv[item] -= sellable
        
        total_animals = sum(animals.values())
        feed_cost = total_animals * wheat_price
        money -= feed_cost
        
        hands_est = max(1, int(total_animals * 2.8 / 13 + len(crop_targets) * 1.5 / 13))
        hand_cost = get_fib_cost(hands_est)
        money -= hand_cost
        
        for item in pipeline:
            if pipeline[item] > 0:
                pipeline[item] *= 0.8
    
    terminal_value = money
    for item, inv in market_inv.items():
        if inv > 0:
            terminal_value += inv * market_price(item, inv)
    for item, count in animals.items():
        if count > 0:
            terminal_value += count * ANIMALS[item]["cost"] * 0.5
    
    return terminal_value

# -----------------------------------------------------------------------------
# MCTS Search Loop (100ms budget)
# -----------------------------------------------------------------------------
MCTS_TIME_BUDGET_MS = 100
MCTS_EXPLORATION = 1.414

def mcts_search(root_state_hash, st, plan, time_budget_ms=MCTS_TIME_BUDGET_MS):
    root = MCTSNode(root_state_hash)
    root.untried_actions = list(STRATEGIC_ACTIONS)
    
    start_time = time.time()
    deadline = start_time + time_budget_ms / 1000.0
    search_seed = hash((root_state_hash, st.day)) & 0x7FFFFFFF
    
    while time.time() < deadline:
        node = root
        while node.untried_actions is None or len(node.untried_actions) == 0:
            if not node.children:
                break
            best_score = -float('inf')
            best_child = None
            for child in node.children.values():
                if child.visits == 0:
                    score = float('inf')
                else:
                    exploit = child.value / child.visits
                    explore = MCTS_EXPLORATION * math.sqrt(math.log(node.visits) / child.visits)
                    score = exploit + explore
                if score > best_score:
                    best_score = score
                    best_child = child
            if best_child is None:
                break
            node = best_child
        
        if node.untried_actions is not None and node.untried_actions:
            action = node.untried_actions.pop()
            child_hash = (node.state_hash ^ hash(action)) & 0xFFFFFFFFFFFFFFFF
            child = MCTSNode(child_hash, parent=node, action=action)
            node.children[action] = child
            node = child
            node.untried_actions = list(STRATEGIC_ACTIONS)
        
        sim_seed = (search_seed ^ node.state_hash) & 0x7FFFFFFF
        value = simulate(st, plan, node.action, seed=sim_seed)
        
        while node is not None:
            node.visits += 1
            node.value += value
            node = node.parent
    
    if not root.children:
        return ("MAINTAIN",)
    
    best_action = max(root.children.items(), key=lambda kv: kv[1].visits)[0]
    return best_action

# -----------------------------------------------------------------------------
# Strategic Action Application
# -----------------------------------------------------------------------------
def apply_strategic_action(plan, action, st):
    action_type = action[0]
    
    # Initialize adjs if not present
    plan.setdefault("max_animals_adj", 1.0)
    plan.setdefault("crop_boost_adj", 1.0)
    
    # Floor for animal adjustment - never go below 0.7
    ANIMAL_ADJ_FLOOR = 0.7
    
    if action_type == "PIVOT_FROM":
        item = action[1]
        plan.setdefault("reserve", {})[item] = 1
        plan.setdefault("head", {})[item] = 0
        plan.setdefault("pipeline", {})[item] = 0
        
        # If pivoting from animal products, reduce animal cap moderately
        if item in ["FERTILIZER", "MILK", "WOOL", "EGG"]:
            plan["max_animals_adj"] = max(ANIMAL_ADJ_FLOOR, plan["max_animals_adj"])
            plan["crop_boost_adj"] = max(plan["crop_boost_adj"], 1.3)
            
        for alt in ("STRAWBERRY", "MELON", "MILK", "WOOL"):
            if alt != item and not plan.get("opp_dump", {}).get(alt, False):
                plan.setdefault("head", {})[alt] = int(plan.get("head", {}).get(alt, 0) * 1.3)
                plan.setdefault("reserve", {})[alt] = int(plan.get("reserve", {}).get(alt, 1) * 1.15)
    
    elif action_type == "PIVOT_TO":
        item = action[1]
        plan.setdefault("head", {})[item] = int(plan.get("head", {}).get(item, 0) * 1.5)
        plan.setdefault("reserve", {})[item] = int(plan.get("reserve", {}).get(item, 1) * 1.2)
        if item in CROPS:
            plan["crop_boost_adj"] = max(plan["crop_boost_adj"], 1.3)
        else:
            plan["max_animals_adj"] = max(plan["max_animals_adj"], 1.1)
    
    elif action_type == "HOARD":
        item = action[1]
        plan.setdefault("reserve", {})[item] = 9999
    
    elif action_type == "SHORT":
        item = action[1]
        if item in plan.get("crop_targets", {}):
            plan["crop_targets"][item] = 0
        plan.setdefault("reserve", {})[item] = 1
    
    elif action_type == "BUY_LAND":
        plan["buy_land"] = True
    
    elif action_type == "HIRE_HANDS":
        plan["hands"] = min(plan.get("hands", 0) + 1, P["max_hands"])
    
    # Enforce floor
    plan["max_animals_adj"] = max(plan["max_animals_adj"], ANIMAL_ADJ_FLOOR)

last_strategic_action = ("MAINTAIN",)

# -----------------------------------------------------------------------------
# Integration Hook (call from build_plan)
# -----------------------------------------------------------------------------
def run_strategic_mcts(st, plan):
    global last_strategic_action
    
    needs_search = (
        st.hour == 0 and (
            st.day % 3 == 0 or
            any(plan.get("opp_dump", {}).values()) or
            st.day <= 5
        )
    )
    if needs_search:
        state_hash = compress_state(st, plan)
        last_strategic_action = mcts_search(state_hash, st, plan)
        apply_strategic_action(plan, last_strategic_action, st)

# Price history window for velocity computation
PRICE_HISTORY_WINDOW = 4

# --------------------------------------------------------------------------
# tunables
# --------------------------------------------------------------------------
P = {
    # Reserves are a floor, not a normal-price target: adaptive_reserve()
    # discounts them 4x the moment a dump is detected, so the base value must
    # sit well above the observed dump-floor price or the floor vanishes
    # exactly when a crash makes it matter. Milk/wool dump-floor around
    # 108-110, so res_MILK/res_WOOL must clear that even after the discount.
    "res_WHEAT": 16, "res_CARROT": 24, "res_TOMATO": 42, "res_STRAWBERRY": 75,
    "res_MELON": 160, "res_EGG": 10, "res_MILK": 130, "res_WOOL": 150,
    "res_FERTILIZER": 30,

    "max_hands": 11,           # Cap hands strictly to 11 to avoid Fibonacci labor trap (opponent uses 10)
    "hand_budget": 200.0,      # floor on daily hand spend
    "hand_budget_frac": 0.10,  # plus this fraction of liquid cash
    "work_per_hand": 13.0,     # usable actions per hand per day (rest is travel)

    "max_geese": 0,             # Keep 0
    "early_sheep_boost": 3.0,   # Ladder-informed: prior 1.35 was too weak against
                                # the 20x/5x animal boost - sheep still lost budget
                                # race to cows. 3.0 makes sheep dominate ranking
                                # when have["SHEEP"] < 4 on days 0-2, matching
                                # every replay winner's day-1 4-sheep purchase.
    "max_animals": 14,          # Total herd cap. Ladder feedback: 20 caused
                                # milk-market self-crash. Winners run 12-15 total.
    "max_cows": 10,             # Per-kind cow cap. Even inside 14-total, cows
                                # above 10 push milk to $1-5 vs any opponent
                                # that also runs cows.
    "wheat_buffer_days": 1.4,   # days of feed to keep in the shed
    "max_wheat_stock": 55,      # shed only holds 100 items total
    "feed_reserve_days": 1.0,   # days of feed money held back from all spending
    "max_wheat_price": 70,      # normal ceiling on bought feed wheat (buy from market to save land)
    "panic_wheat_price": 90,    # ceiling when animals would otherwise starve
    "wheat_tiles_per_animal": 0.0, # Do not waste land on wheat if we can buy it!
    "dig_value": 15.0,          # weeds are dead tiles; clearing one is cheap. Deprioritize!

    "stop_animals_day": 25,
    "yield_haircut": 0.85,      # discount on projected animal revenue
    "invest_frac": 0.98,        # share of free cash committed per planning pass
    "land_slack": 12,           # buy the next quadrant when free tiles drop here
    "dist_pow": 1.45,           # travel penalty exponent in task scoring
    "sticky": 1.6,              # bonus for continuing last turn's target
    "sticky_pos": 1.0,          # position-stickiness (1.0 = off; hurts above)
    "fert_weight": 2.5,         # COLLECT_FERTILIZER value vs its market price. EXTREMELY HIGH PRIORITY.
    "wheat_grab_min": 8,        # minimum wheat a unit collects per shed trip
    "headroom_floor_frac": 0.80, # floor on headroom to prevent getting shut out by opponent
    "animal_buy_buffer": 400.0, # cash reserve held back when buying animals to prevent hand-hire starvation
    # Wheat carry trade: buy low early, sell high late (price rises ~$1/day guaranteed)
    "wheat_carry_max": 20,      # max surplus wheat units to hold as carry position
    "wheat_carry_buy_day": 8,   # stop buying carry wheat after this day
    "wheat_carry_sell_day": 18, # start releasing carry wheat for sale after this day
    "wheat_carry_buy_price": 32, # only buy carry wheat below this price (genuinely cheap)
}


def _shape(f, x):
    x = max(0.0, x)
    if f == "linear":
        return x
    if f == "sq":
        return x * x
    if f == "sqrt":
        return math.sqrt(x)
    if f == "log":
        return math.log(1.0 + x)
    return math.log10(1.0 + x)


_AMP = {}
for _it, _p in MARKET_PARAMS.items():
    _AMP[_it] = (_p["bt"] * _p["base"] / _shape(_p["bf"], _p["T"]),
                 _p["at"] * _p["base"] / _shape(_p["af"], _p["T"]))


def market_price(item, inv):
    p = MARKET_PARAMS[item]
    i0 = p["I0"]
    if inv < i0:
        v = p["base"] + _AMP[item][0] * _shape(p["bf"], i0 - inv)
    else:
        v = p["base"] - _AMP[item][1] * _shape(p["af"], inv - i0)
    return max(1, int(round(v)))


def update_price_history(st):
    """Track price history for velocity computation - call once per day"""
    # price_history/market_velocity are restored from _MEM before build_plan;
    # if still None (very first step) initialize them now.
    if st.price_history is None:
        st.price_history = {p: [] for p in PRODUCTS}
    if st.market_velocity is None:
        st.market_velocity = {p: 0.0 for p in PRODUCTS}
    if st.hour != 0:
        return
    for p in PRODUCTS:
        hist = st.price_history[p]
        hist.append(st.prices[p])
        if len(hist) > PRICE_HISTORY_WINDOW:
            hist.pop(0)
        if len(hist) >= 2:
            st.market_velocity[p] = (hist[-1] - hist[0]) / len(hist)
        else:
            st.market_velocity[p] = 0.0


def compute_price_velocity(st, item):
    """Current price velocity (dPrice/dt) for an item"""
    return st.market_velocity.get(item, 0.0)


def detect_opp_dump(st, item):
    """Returns True if opponent is aggressively flooding item based on price velocity"""
    vel = compute_price_velocity(st, item)
    p = MARKET_PARAMS.get(item, {})
    base = p.get("base", 100)
    
    # Threshold for dump: velocity <= -0.015 * base price per day
    threshold = -0.015 * base
    
    # We also require a trigger day and minimum market inventory to avoid noise early on
    if st.day >= 4 and vel <= threshold and st.minv.get(item, 0) >= base * 0.4:
        return True
    return False


def estimate_production(st, pid, item):
    """Estimate a player's daily production of an item from visible tiles"""
    prod = 0
    if pid < len(st.obs["farms"]):
        farm = st.obs["farms"][pid]
        for row in farm["tiles"]:
            for t in row:
                if not isinstance(t, dict):
                    continue
                k = t.get("kind")
                if k == "PLANT":
                    c = CROPS.get(t.get("crop", ""), {})
                    if c.get("ongoing"):
                        age = st.day - t.get("planted_day", st.day)
                        done = 0 if age < c["first"] else (age - c["first"]) // c["interval"] + 1
                        prod += max(0, c["cap"] - done) * 1.5
                    else:
                        prod += c.get("cap", 0)
                elif k in ("COOP", "PASTURE"):
                    a = t.get("animal")
                    if a:
                        ad = ANIMALS.get(a, {})
                        if ad.get("prod") == item:
                            wait = max(0, ad["first"] - (st.day - t.get("placed_day", st.day)))
                            left = st.days_left - wait
                            nprod = 0 if left < 0 else left // ad["interval"] + 1
                            prod += nprod * (1 + ad["interval"])
    return prod


def projected_price(item, current_inv, our_daily_supply, opp_daily_supply, days_left, town_drain, current_price=None):
    """Simulates market inventory trajectory and returns expected average price"""
    if days_left <= 0:
        return market_price(item, current_inv)
    
    inv = float(current_inv)
    total_daily_supply = our_daily_supply + opp_daily_supply
    prices = []
    for _ in range(days_left):
        inv += total_daily_supply - town_drain
        inv = max(0.0, inv)
        prices.append(market_price(item, inv))
    return sum(prices) / len(prices) if prices else (current_price if current_price else market_price(item, current_inv))


def adaptive_reserve(base_reserve, price_vel, dump_detected, days_left):
    """Dynamically adjust reserve price based on market conditions"""
    if dump_detected:
        return max(1, int(base_reserve * 0.25))  # Fire sale prevention - liquidate fast
    if price_vel < -3.0:
        return max(1, int(base_reserve * 0.5))   # Softening market
    if price_vel < -1.0:
        return max(1, int(base_reserve * 0.75))  # Early warning
    if days_left <= 3:
        return max(1, int(base_reserve * 0.4))   # Endgame liquidation
    return base_reserve


def elastic_mav(crop, st, plan, price_proj, reserve):
    """MAV using projected price instead of spot price"""
    r = crop_plan_value(crop, st, price_proj)
    if r is None:
        return 0.0
    units, occ, acts, profit = r
    room = plan["head"][crop] - plan["pipeline"][crop]
    if crop == "WHEAT":
        feed_need = (plan["animals"] + st.days_left * 1.5) * st.days_left
        room = max(room, feed_need)
    if room < units * 0.5:
        return 0.0
    if profit <= 0:
        return 0.0
    return profit / float(acts)


def units_sellable(item, inv, reserve, limit):
    """How many units can be sold starting at `inv` before price < reserve."""
    lo, hi = 0, limit
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if market_price(item, inv + mid - 1) >= reserve:
            lo = mid
        else:
            hi = mid - 1
    return lo


# --------------------------------------------------------------------------
# observation wrapper
# --------------------------------------------------------------------------
class S(object):
    __slots__ = ("obs", "pid", "day", "hour", "farm", "tiles", "n", "half",
                 "money", "shed", "seeds", "invs", "units", "minv", "prices",
                 "unlocked", "hires_today", "shed_tiles", "shed_used",
                 "days_left", "price_history", "opp_dump_flags", "market_velocity")

    def __init__(self, obs):
        self.obs = obs
        self.pid = obs["player"]
        self.day = obs["day"]
        self.hour = obs["hour"]
        self.farm = obs["farms"][self.pid]
        self.tiles = self.farm["tiles"]
        self.n = len(self.tiles)
        self.half = self.n // 2
        self.money = self.farm["money"]
        priv = obs["private"]
        self.shed = priv["shed"]
        self.seeds = priv["seeds"]
        self.invs = priv["inventories"]
        self.units = [tuple(self.farm["farmer"])] + [tuple(h) for h in self.farm["hands"]]
        mk = obs["market"]
        self.minv = mk["inventory"]
        self.prices = mk["prices"]
        self.unlocked = self.farm["unlocked_quadrants"]
        self.hires_today = self.farm["hires_today"]
        h = self.half
        self.shed_tiles = [(h - 1, h - 1), (h, h - 1), (h - 1, h), (h, h)]
        self.shed_used = sum(self.shed.values())
        self.days_left = FINAL_DAY - self.day
        
        # Adaptive market tracking — initialized to None so agent() can
        # restore persisted values from _MEM before build_plan() runs.
        self.price_history = None
        self.opp_dump_flags = {p: False for p in PRODUCTS}
        self.market_velocity = None

    def inv(self, i):
        return self.invs[i] if i < len(self.invs) else {}


def dist(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def step_toward(a, b):
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    if abs(dx) >= abs(dy):
        if dx > 0:
            return ["EAST"]
        if dx < 0:
            return ["WEST"]
    if dy > 0:
        return ["SOUTH"]
    if dy < 0:
        return ["NORTH"]
    return ["PASS"]


# --------------------------------------------------------------------------
# daily plan
# --------------------------------------------------------------------------
def reserve_scale(day):
    if day >= FINAL_DAY:
        return 0.0
    if day >= FINAL_DAY - 1:
        return 0.16
    if day >= FINAL_DAY - 2:
        return 0.42
    if day >= FINAL_DAY - 3:
        return 0.68
    if day >= FINAL_DAY - 4:
        return 0.86
    return 1.0


def town_rates(st):
    """Units/day the town drains, blending realised shops with expected future ones.
    Used for EV projections — includes future shop unlock estimates."""
    rate = {}
    for p in PRODUCTS:
        rate[p] = 0.0 if p == "FERTILIZER" else 1.0
    shops = st.obs["town"].get("unlocked_shops", [])
    for name in shops:
        pl = SHOPS.get(name)
        if not pl:
            continue
        mult = 2.0 if len(pl) == 1 else 1.0
        for p in pl:
            rate[p] += 6.0 * mult
    # expected additional unlocks still to come this season
    future = 0
    while len(shops) + future < 8:
        nxt = (len(shops) + future + 1) * 3
        if nxt > FINAL_DAY:
            break
        future += 1
    if future and st.days_left > 0:
        # each future shop is live for roughly half the remaining season
        w = 0.5 * future
        for p in PRODUCTS:
            rate[p] += w * _EXPECTED_SHOP_RATE[p]
    return rate


def town_rates_current(st):
    """Units/day from CURRENTLY unlocked shops only — no future blending.
    Used for headroom calculations to avoid overestimating available market
    capacity before shops actually open."""
    rate = {}
    for p in PRODUCTS:
        rate[p] = 0.0 if p == "FERTILIZER" else 1.0
    shops = st.obs["town"].get("unlocked_shops", [])
    for name in shops:
        pl = SHOPS.get(name)
        if not pl:
            continue
        mult = 2.0 if len(pl) == 1 else 1.0
        for p in pl:
            rate[p] += 6.0 * mult
    return rate


def animal_units(kind, days_left):
    """Product units a freshly placed animal yields, assuming daily FEED+CARE."""
    a = ANIMALS[kind]
    if days_left < a["first"]:
        return 0
    n = (days_left - a["first"]) // a["interval"] + 1
    return n * (1 + a["interval"])


def compute_exact_animal_ev(st, plan, kind, wheat_price_buy, proj_price, rate, our_base_supply, opp_base_supply, dl):
    """Rigorous Expected Value calculation for buying ONE marginal animal."""
    a = ANIMALS[kind]
    prod = a["prod"]
    if dl < a["first"]: return -float('inf'), 0, 0, None
    prod_days = []
    day = a["first"]
    while day <= dl:
        prod_days.append(day)
        day += a["interval"]
    n_productions = len(prod_days)
    if n_productions == 0: return -float('inf'), 0, 0, None
    units_per_prod = 1 + a["interval"]
    total_units = n_productions * units_per_prod
    our_total_supply = our_base_supply + (total_units / dl)
    opp_total_supply = opp_base_supply
    town_drain = rate.get(prod, 1.0)
    prod_prices = []
    for pd in prod_days:
        days_remaining = dl - pd + 1
        price = projected_price(prod, st.minv.get(prod, 0), our_total_supply, opp_total_supply, days_remaining, town_drain, proj_price)
        prod_prices.append(price)
    avg_prod_price = sum(prod_prices) / len(prod_prices) if prod_prices else proj_price
    revenue = total_units * avg_prod_price * P["yield_haircut"]
    fert_rates = {"COW": 0.75, "SHEEP": 0.5, "GOOSE": 0.5}
    fert_per_day = fert_rates.get(kind, 0.5)
    total_fert = fert_per_day * (dl - a["first"] + 1)
    fert_price_proj = projected_price("FERTILIZER", st.minv.get("FERTILIZER", 0), 0, 0, dl, rate.get("FERTILIZER", 1.0), st.prices.get("FERTILIZER", 50))
    fert_revenue = total_fert * fert_price_proj * plan.get("fert_weight_adj", 1.0)
    feed_days = dl - a["first"] + 1
    wheat_price_proj = projected_price("WHEAT", st.minv.get("WHEAT", 0), 0, 0, dl, rate.get("WHEAT", 1.0), wheat_price_buy)
    feed_cost = feed_days * wheat_price_proj
    total_actions = feed_days + n_productions + n_productions + feed_days + 1
    actions_per_day = total_actions / max(1, dl)
    hands_required = actions_per_day / P["work_per_hand"]
    hand_cost = 0
    current_hands = plan.get("hands", 0)
    for i in range(int(math.ceil(hands_required))):
        hand_idx = current_hands + i
        if hand_idx >= P["max_hands"]: hand_cost += get_fib_cost(P["max_hands"]) * 2
        else: hand_cost += get_fib_cost(hand_idx + 1) - get_fib_cost(hand_idx)
    gross_revenue = revenue + fert_revenue
    total_cost = a["cost"] + feed_cost + hand_cost
    net_ev = gross_revenue - total_cost
    daily_cashflow = (gross_revenue - total_cost) / dl if dl > 0 else 0
    cum_rev, cum_cost, break_even = 0, a["cost"], None
    for i, pd in enumerate(prod_days):
        cum_rev += units_per_prod * prod_prices[i]
        cum_cost += feed_cost / feed_days + hand_cost / max(1, n_productions)
        if cum_rev >= cum_cost and break_even is None: break_even = pd
    return net_ev, total_actions, daily_cashflow, break_even

def compute_exact_crop_ev(st, plan, crop, proj_price, rate, opp_production, dl):
    c = CROPS[crop]
    if dl < c["first"]: return -float('inf'), 0, 0, None
    if c["ongoing"]:
        n_harvests = min((dl - c["first"]) // c["interval"] + 1, c["cap"])
        units_per_harvest = 2
        total_units = n_harvests * units_per_harvest
        harvest_days = [c["first"] + i * c["interval"] for i in range(n_harvests)]
        occ_days = c["first"] + (n_harvests - 1) * c["interval"] + 1
    else:
        age = min(c["maxday"], dl)
        w0 = (c["maxday"] + 1) // 2
        n_harvests = min(c["cap"], 1 + max(0, age - w0 + 1))
        total_units = n_harvests
        harvest_days = [w0 + i for i in range(n_harvests)] if n_harvests > 0 else []
        occ_days = max(1, age)
    if total_units <= 0: return -float('inf'), 0, 0, None
    our_daily_supply = total_units / dl
    opp_daily_supply = opp_production.get(crop, 0) / max(1, dl)
    town_drain = rate.get(crop, 1.0)
    harvest_prices = []
    for hd in harvest_days:
        days_rem = dl - hd + 1
        price = projected_price(crop, st.minv.get(crop, 0), our_daily_supply, opp_daily_supply, days_rem, town_drain, proj_price)
        harvest_prices.append(price)
    avg_price = sum(harvest_prices) / len(harvest_prices) if harvest_prices else proj_price
    revenue = total_units * avg_price
    total_actions = 1 + occ_days // 2 + (2 if c["ongoing"] else 0) + n_harvests
    actions_per_day = total_actions / max(1, dl)
    hands_required = actions_per_day / P["work_per_hand"]
    hand_cost = 0
    current_hands = plan.get("hands", 0)
    for i in range(int(math.ceil(hands_required))):
        hand_idx = current_hands + i
        if hand_idx >= P["max_hands"]: hand_cost += get_fib_cost(P["max_hands"]) * 2
        else: hand_cost += get_fib_cost(hand_idx + 1) - get_fib_cost(hand_idx)
    net_ev = revenue - c["seed"] - hand_cost
    daily_cashflow = net_ev / dl if dl > 0 else 0
    cum_rev, cum_cost, break_even = 0, c["seed"], None
    for i, hd in enumerate(harvest_days):
        cum_rev += units_per_harvest * harvest_prices[i] if c["ongoing"] else harvest_prices[i]
        cum_cost += hand_cost / max(1, n_harvests)
        if cum_rev >= cum_cost and break_even is None: break_even = hd
    return net_ev, total_actions, daily_cashflow, break_even

def compute_animal_mav_exact(st, plan, kind, a, dl, wheat_price_buy, proj_price, rate, our_base_supply, opp_base_supply):
    net_ev, total_acts, daily_cf, break_even = compute_exact_animal_ev(st, plan, kind, wheat_price_buy, proj_price, rate, our_base_supply, opp_base_supply, dl)
    if net_ev <= 0: return None
    action_val = net_ev / max(1, total_acts)
    return (action_val, kind, net_ev, total_acts, daily_cf, break_even)

def compute_crop_mav_exact(st, plan, crop, c, dl, proj_price, rate, opp_production):
    net_ev, total_acts, daily_cf, break_even = compute_exact_crop_ev(st, plan, crop, proj_price, rate, opp_production, dl)
    if net_ev <= 0: return None
    action_val = net_ev / max(1, total_acts)
    return (action_val, crop, net_ev, total_acts, daily_cf, break_even)

def crop_plan_value(crop, st, price):
    """(units, days occupied, actions) for planting `crop` today."""
    c = CROPS[crop]
    dl = st.days_left
    if c["ongoing"]:
        if dl < c["first"]:
            return None
        n = (dl - c["first"]) // c["interval"] + 1
        n = min(n, c["cap"])
        units = n * 2  # fertilised
        occ = c["first"] + (n - 1) * c["interval"] + 1
        acts = 1 + occ // 2 + n + n
    else:
        if dl < c["first"]:
            return None
        age = min(c["maxday"], dl)
        w0 = (c["maxday"] + 1) // 2
        units = min(c["cap"], 1 + max(0, age - w0 + 1))
        occ = max(1, age)
        acts = 1 + (w0 // 2) + (age - w0 + 1) + 1
    profit = units * price - c["seed"]
    return units, occ, acts, profit


def get_fib_cost(n):
    if n <= 0: return 0.0
    n_int = int(math.floor(n))
    frac = n - n_int
    s, a, b = 0.0, 1.0, 1.0
    for _ in range(n_int):
        s += a
        a, b = b, a + b
    s += a * frac
    return s

def build_plan(st):
    dl = st.days_left
    
    # Update price history for velocity tracking (once per day at hour 0)
    update_price_history(st)
    
    rate = town_rates(st)
    rate_current = town_rates_current(st)  # Gap 4: current-only drain for headroom
    scale = reserve_scale(st.day)
    reserve = {}
    head = {}
    opp_production = {p: 0 for p in PRODUCTS}
    our_production = {p: 0 for p in PRODUCTS}
    opp_dump_detected = {p: False for p in PRODUCTS}
    
    if dl > 0:
        for p in PRODUCTS:
            opp_production[p] = estimate_production(st, 1 - st.pid, p)
            our_production[p] = estimate_production(st, st.pid, p)
            opp_dump_detected[p] = detect_opp_dump(st, p)
            vel = compute_price_velocity(st, p)
            base_r = max(1, int(P["res_" + p] * scale)) if scale > 0 else 1
            reserve[p] = adaptive_reserve(base_r, vel, opp_dump_detected[p], dl)

            # Gap 4 (refined): use blended rate for headroom MAGNITUDE so early-game
            # animal purchases aren't capped before shops open. But use rate_current
            # (shops actually unlocked) for the floor THRESHOLD check — this prevents
            # the headroom floor from activating when a shop (e.g. Yarn Store) hasn't
            # opened yet, protecting against the 18-sheep Wool crash scenario.
            if p == "MELON":
                # Melon has high market absorption (T=300) and absorbs ~180 units of supply
                # before price drops below $180. Dynamically subtract opponent melon production
                # so we self-balance and never double-saturate the market.
                headroom = max(40, 180 - int(opp_production["MELON"]))
            else:
                blended_drain = rate[p] * dl
                if (rate_current[p] >= 5.0 or (st.day <= 3 and p in ("MILK", "WOOL"))) and p in ("STRAWBERRY", "TOMATO", "MILK", "WOOL"):
                    min_h = int(blended_drain * P.get("headroom_floor_frac", 0.80))
                    opp_mult = 1.5 if (st.day <= 3 and p == "MILK") else 1.0
                    headroom = max(min_h, int(blended_drain * 1.5) - int(opp_production[p] * opp_mult))
                else:
                    headroom = max(0, int(blended_drain * 1.5) - int(opp_production[p]))
            head[p] = headroom # DO NOT add units_sellable here, it encourages market crashing!
            
            if p == "WHEAT":
                head[p] = 9999

    plan = {"reserve": reserve, "head": head, "rate": rate, "opp_dump": opp_dump_detected}

    # ---- Endgame Liquidation Protocol ----
    if dl <= 3:
        for p in PRODUCTS:
            plan["reserve"][p] = 1
            plan["head"][p] = 0

    plan["fert_weight_adj"] = 1.0
    plan["max_animals_adj"] = 1.0
    plan["crop_boost_adj"] = 1.0
    pipeline = dict((p, 0.0) for p in PRODUCTS)
    counts = {"GOOSE": 0, "COW": 0, "SHEEP": 0}
    coops_free = 0
    pastures_free = 0
    empties = []
    weeds = []
    crop_tiles = 0
    crop_counts = {}
    for y in range(st.n):
        row = st.tiles[y]
        for x in range(st.n):
            t = row[x]
            if t is None:
                empties.append((x, y))
                continue
            if t == "LOCKED" or not isinstance(t, dict):
                continue
            k = t.get("kind")
            if k == "WEED":
                weeds.append((x, y))
            elif k == "PLANT":
                crop_tiles += 1
                crop_counts[t["crop"]] = crop_counts.get(t["crop"], 0) + 1
                c = CROPS[t["crop"]]
                if c["ongoing"]:
                    age = st.day - t["planted_day"]
                    done = 0 if age < c["first"] else (age - c["first"]) // c["interval"] + 1
                    pipeline[t["crop"]] += max(0, c["cap"] - done) * 2
                else:
                    pipeline[t["crop"]] += c["cap"]
            elif k in ("COOP", "PASTURE"):
                a = t.get("animal")
                if a is None:
                    if k == "COOP":
                        coops_free += 1
                    else:
                        pastures_free += 1
                else:
                    counts[a] += 1
                    ad = ANIMALS[a]
                    wait = max(0, ad["first"] - (st.day - t["placed_day"]))
                    left = dl - wait
                    nprod = 0 if left < 0 else left // ad["interval"] + 1
                    pipeline[ad["prod"]] += nprod * (1 + ad["interval"])

    plan["pipeline"] = pipeline
    plan["empties"] = empties
    plan["weeds"] = weeds
    plan["counts"] = counts
    plan["coops_free"] = coops_free
    plan["pastures_free"] = pastures_free
    animals_now = counts["GOOSE"] + counts["COW"] + counts["SHEEP"]
    plan["animals"] = animals_now
    
    carried = {k: 0 for k in ANIMALS}
    for inv in st.invs:
        for k in ANIMALS:
            carried[k] += inv.get("animal:" + k, 0)
            carried[k] += inv.get(k, 0)
            
    have = dict((k, counts[k] + st.shed.get(k, 0) + carried[k]) for k in ANIMALS)
    plan["have"] = have
    owned = have["GOOSE"] + have["COW"] + have["SHEEP"]
    
    wheat_price_buy = market_price("WHEAT", st.minv["WHEAT"] - 1)
    # Gap 6: remove hardcoded $2600 cap — scale with actual wheat price
    # (late-game wheat can be $50+; 20 cows x 3 days x $50 = $3000 needed)
    feed_reserve = owned * P["feed_reserve_days"] * wheat_price_buy
    plan["feed_reserve"] = feed_reserve

    nq = len(st.unlocked) - 1
    effective_work_per_hand = P["work_per_hand"] - (nq * 1.5)
    if effective_work_per_hand < 7.0: effective_work_per_hand = 7.0

    # ---- MCTS Strategic Layer ----
    # run_strategic_mcts(st, plan)

    # ---- dynamic crop value and MAV (exact EV) -------------
    cand = []
    feed_need = (owned + dl * 1.5) * dl  # rough estimate
    
    for crop in CROPS:
        c = CROPS[crop]
        
        # Project price for this crop
        our_daily_supply = 2.0 * (c["cap"] / max(1, c["interval"])) if c["ongoing"] and c["interval"] > 0 else c["cap"] / max(1, c["maxday"])
        our_supply = our_daily_supply * max(1, plan.get("crop_targets", {}).get(crop, 0) or 1)
        base_opp_supply = opp_production.get(crop, 0) / max(1, dl)
        if opp_dump_detected.get(crop, False):
            dump_stats = REPLAY_DUMP_STATS.get(crop, {})
            dump_qty = dump_stats.get("avg_dump_qty", 100)
            opp_supply = base_opp_supply + dump_qty / max(1, dl)
        else:
            opp_supply = base_opp_supply
        town_drain = rate.get(crop, 1.0)
        
        price_proj = projected_price(
            crop, st.minv.get(crop, 0), our_supply, opp_supply, dl, town_drain, st.prices.get(crop, 0))
        
        if crop == "WHEAT":
            price_proj = max(price_proj, min(wheat_price_buy, 60))
        
        # Use exact EV calculation
        exact = compute_crop_mav_exact(st, plan, crop, c, dl, price_proj, rate, opp_production)
        if exact is None:
            continue
        action_val, _, net_ev, total_acts, daily_cf, break_even = exact
        
        if action_val <= 0:
            continue
        
        # Recompute details for storage
        r = crop_plan_value(crop, st, price_proj)
        if r is None: continue
        units, occ, acts, profit = r
        room = head[crop] - pipeline[crop]
        if crop == "WHEAT": room = max(room, feed_need)
        if room < units * 0.5: continue
        
        cand.append((action_val, crop, units, room, profit, occ, acts, net_ev, total_acts, daily_cf, break_even))
        
    cand.sort(reverse=True, key=lambda z: z[0])
    best_crop_action_val = cand[0][0] if cand else 0.0

    # ---- animal evaluation with exact EV ---------------------------
    # Gap 3: track committed want per kind so marginal EV reflects cumulative
    # price depression from the full planned herd, not just one animal.
    committed_want = dict(have)  # starts at current holdings
    animal_cand = []
    for kind, a in ANIMALS.items():
        per = animal_units(kind, dl)
        if per <= 0: continue
        
        # Project product price accounting for already-committed herd supply
        prod = a["prod"]
        committed_count = committed_want.get(kind, 0)
        
        # Calculate our existing base supply from tiles + shed + committed
        our_prod_base = our_production.get(prod, 0) / max(1, dl)
        unplaced_count = st.shed.get(kind, 0) + committed_count
        our_base_supply = our_prod_base + (per / max(1, dl) * unplaced_count)
        
        # Calculate marginal supply for the price projection
        our_supply = our_base_supply + (per / max(1, dl))
        
        base_opp_supply = opp_production.get(prod, 0) / max(1, dl)
        if opp_dump_detected.get(prod, False):
            dump_stats = REPLAY_DUMP_STATS.get(prod, {})
            dump_qty = dump_stats.get("avg_dump_qty", 100)
            opp_supply = base_opp_supply + dump_qty / max(1, dl)
        else:
            opp_supply = base_opp_supply
        town_drain = rate.get(prod, 1.0)
        
        price_proj = projected_price(prod, st.minv.get(prod, 0), our_supply, opp_supply, dl, town_drain, st.prices.get(prod, 0))
        price = max(price_proj, reserve[prod])
        
        # Use exact EV calculation
        exact = compute_animal_mav_exact(st, plan, kind, a, dl, wheat_price_buy, price, rate, our_base_supply, opp_supply)
        
        if exact is None:
            continue
        action_val, _, net_ev, total_acts, daily_cf, break_even = exact
        
        animal_cand.append((action_val, kind, per, a, net_ev, total_acts, daily_cf, break_even))
        
    animal_cand.sort(reverse=True, key=lambda z: z[0])
    best_animal_action_val = animal_cand[0][0] if animal_cand else 0.0
    
    MAV = max(best_crop_action_val, best_animal_action_val)
    if MAV <= 0: MAV = 10.0

    pending = coops_free + pastures_free + len(weeds)
    current_work = (animals_now * 2.8 + crop_tiles * 1.5 + pending * 1.7 + 10)
    current_hands = current_work / effective_work_per_hand
    
    labor_reserve = get_fib_cost(current_hands) * 1.5
    budget = max(0.0, st.money - feed_reserve - labor_reserve) * P["invest_frac"]

    # ---- dynamic land: evaluate ROI of 25 new tiles ----------------------
    # ---- dynamic land: evaluate ROI of 25 new tiles ----------------------
    # Optimized Land Timing:
    # 1. Protects Days 0-4 capital strictly for early animal compounding.
    # 2. Quad 1 unlocks on Day 5-8 once herd reaches 6+ and cash >= $1,450.
    # 3. Quad 2 unlocks in mid-game (Days 9-18) when tile room drops <= 14.
    nq = len(st.unlocked) - 1
    plan["buy_land"] = False
    if nq < 2 and dl >= 5:
        cost = (1000, 2000, 4000)[nq]
        usable_tiles = len(empties) + len(weeds)
        if nq == 0:
            should_buy_q1 = (st.day >= 5 and owned >= 6 and st.money >= cost + 450) or (usable_tiles <= 8 and st.money >= cost + 300)
            if should_buy_q1 and budget >= cost * 0.85:
                plan["buy_land"] = True
                budget -= cost
        elif nq == 1:
            should_buy_q2 = (st.day >= 9 and usable_tiles <= 14 and st.money >= cost + 600)
            if should_buy_q2 and budget >= cost * 0.85:
                plan["buy_land"] = True
                budget -= cost

    # ---- dynamic animal targets ------------------------------------------
    global_cand = []
    for item in cand:
        # item: (mav, crop, units, room, prof, occ, acts, net_ev, total_acts, daily_cf, break_even)
        mav = item[0]
        global_cand.append((mav, "CROP", item))
        
    if st.day <= P["stop_animals_day"]:
        for item in animal_cand:
            action_val = item[0]
            kind = item[1]
            # Gap 1: Replaced the 100x/10x blind boost with a moderate 20x/5x.
            # Strong enough to strongly prefer animals early (genuine time-value
            # advantage), but the headroom cap (by_market) is now the real
            # protection — not the EV multiplier. The corrected opp_production
            # parsing ensures headroom correctly reflects the market state.
            if dl >= 20:
                action_val *= 20.0  # early game: long payback window
            elif dl >= 15:
                action_val *= 5.0   # mid-early: still prefer animals over crops
            if kind == "SHEEP" and st.day <= 2 and have.get("SHEEP", 0) < 4:
                action_val *= P.get("early_sheep_boost", 1.35)
            global_cand.append((action_val, "ANIMAL", item))
            
    global_cand.sort(reverse=True, key=lambda z: z[0])
    
    crop_targets = {}
    want = dict(have)
    tile_room = len(empties) + coops_free + pastures_free
    total = owned
    
    structures_can_build = min(sum(st.shed.get(k, 0) for k in ANIMALS) + 4, len(empties))
    sim_coops_free = coops_free
    sim_pastures_free = pastures_free
    sim_shed_used = st.shed_used
    
    for entry in global_cand:
        if entry[1] == "CROP":
            # (mav, crop, units, room, prof, occ, acts, net_ev, total_acts, daily_cf, break_even)
            mav, crop, units, room, prof, occ, acts, net_ev, total_acts, daily_cf, break_even = entry[2]
            crop_boost = plan.get("crop_boost_adj", 1.0)
            by_market = int(room * crop_boost // max(1, units)) + 1
            by_cash = int(budget // CROPS[crop]["seed"])

            # Phased Melon Target Staging (Exploit-Proof):
            # Days 0-4: Cap at 8 seeds to 100% preserve initial capital for Cows & Sheep.
            # Days 5-16: Scale up to 25 seeds on outer quadrant tiles.
            # Days 17+: 0 seeds (won't mature before season ends).
            if crop == "MELON":
                if st.day <= 4:
                    by_market = min(by_market, 8)
                elif st.day <= 16:
                    by_market = min(by_market, 25)
                else:
                    by_market = 0

            take = min(tile_room, max(min(by_market, by_cash), st.seeds.get(crop, 0)))
            if take <= 0: continue
            crop_targets[crop] = take
            budget -= max(0, take - st.seeds.get(crop, 0)) * CROPS[crop]["seed"]
            tile_room -= take
        elif entry[1] == "ANIMAL":
            # (action_val, kind, per, a, net_ev, total_acts, daily_cf, break_even)
            action_val, kind, per, a, net_ev, total_acts, daily_cf, break_even = entry[2]
            added_hands_for_animal = 2.8 / effective_work_per_hand
            
            # Gap 1: Removed by_market = 999 override. Now respects actual market
            # headroom using current-only drain rates (no future blending).
            room = head[a["prod"]] - pipeline[a["prod"]]
            by_market = int(room // max(1, per))
            
            unit_cost = a["cost"] + 5 * wheat_price_buy
            by_cash = int(budget // unit_cost)
            
            # Gap 7: Upstream budget guard — ensure at least 1x animal_buy_buffer
            # remains after this purchase for subsequent hires and seeds.
            # (3x was too aggressive, limiting to 2 cows at $3k starting cash)
            buf = P.get("animal_buy_buffer", 400.0)
            by_cash_buffered = int(max(0, budget - buf) // unit_cost)
            by_cash = min(by_cash, by_cash_buffered)
            
            n = min(by_market, by_cash, tile_room)
            
            free_structs = sim_coops_free + structures_can_build if kind == "GOOSE" else sim_pastures_free + structures_can_build
            n = min(n, free_structs, 100 - sim_shed_used - 1)
            
            if kind == "GOOSE": n = min(n, P["max_geese"] - have["GOOSE"])
            if kind == "SHEEP": n = min(n, P["max_animals"] - have["SHEEP"])
            if kind == "COW": n = min(n, P.get("max_cows", P["max_animals"]) - have["COW"])
            max_animals_adj = max(1.0, plan.get("max_animals_adj", 1.0))  # Force floor at 1.0
            effective_max_animals = int(P["max_animals"] * max_animals_adj)
            n = min(n, effective_max_animals - total)
            if n <= 0: continue
            
            want[kind] += n
            budget -= n * a["cost"]
            tile_room -= n
            total += n
            current_hands += n * added_hands_for_animal
            # Gap 3: update committed_want so subsequent animal evaluations in
            # later iterations see the correct cumulative herd price depression.
            committed_want[kind] = committed_want.get(kind, 0) + n
            
            if kind == "GOOSE":
                used_structs = max(0, n - sim_coops_free)
                sim_coops_free = max(0, sim_coops_free - n)
            else:
                used_structs = max(0, n - sim_pastures_free)
                sim_pastures_free = max(0, sim_pastures_free - n)
            structures_can_build -= used_structs
            sim_shed_used += n
            
    if total > 0 and dl >= 4 and tile_room > 0:
        need = int(math.ceil(total * P["wheat_tiles_per_animal"])) - crop_counts.get("WHEAT", 0)
        n = max(0, min(need, tile_room, int(budget // CROPS["WHEAT"]["seed"])))
        if n > 0:
            crop_targets["WHEAT"] = n
            budget -= n * CROPS["WHEAT"]["seed"]
            tile_room -= n
            
    # WHEAT is now allocated natively via global_cand based on MAV.

    for crop, n in st.seeds.items():
        if n > 0 and crop not in crop_targets and tile_room > 0:
            crop_targets[crop] = min(n, tile_room)
            tile_room -= crop_targets[crop]

    plan["want"] = want
    plan["crop_targets"] = crop_targets

    # ---- structures ------------------------------------------------------
    need_coops = max(0, want["GOOSE"] - counts["GOOSE"] - coops_free)
    need_past = max(0, want["COW"] + want["SHEEP"] - counts["COW"] - counts["SHEEP"] - pastures_free)
    slack = sum(st.shed.get(k, 0) for k in ANIMALS) + 4
    plan["build_coops"] = min(need_coops, slack, len(empties))
    plan["build_pastures"] = min(need_past, slack, max(0, len(empties) - plan["build_coops"]))

    # Sort empty tiles by squared Euclidean distance to the central shed center (half-0.5, half-0.5)
    # This forms a compact, symmetric circular donut around the 4 shed doors,
    # eliminating diamond/cross skew and strictly minimizing maximum travel radius.
    cx = st.half - 0.5
    cy = st.half - 0.5
    empties.sort(key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
    nb = plan["build_coops"] + plan["build_pastures"]
    plan["coop_sites"] = set(empties[:plan["build_coops"]])
    plan["pasture_sites"] = set(empties[plan["build_coops"]:nb])
    
    # Crops take the remaining outer tiles where in-place watering requires no shed trips
    plan["plant_sites"] = [p for p in empties if p not in plan["coop_sites"] and p not in plan["pasture_sites"]]
    
    def plant_priority(p):
        d2 = (p[0] - cx) ** 2 + (p[1] - cy) ** 2
        # After early game, push crops away from the inner 20 tiles so animals can take them
        if st.day >= 3 and d2 <= 8.5:
            return 1000 + d2
        return d2
        
    plan["plant_sites"].sort(key=plant_priority)


    # ---- dynamic labour budgeting ----------------------------------------
    pending_tasks = plan["build_coops"] + plan["build_pastures"] + len(weeds)
    pending_tasks += sum(crop_targets.values())
    work = (total * 2.8 + crop_tiles * 1.5 + pending_tasks * 1.7 + 10)
    by_work = int(math.ceil(work / effective_work_per_hand))
    
    hand_cash = max(P["hand_budget"], st.money * P["hand_budget_frac"])
    n, spend, a, b = 0, 0.0, 1, 1
    while True:
        if spend + a > hand_cash:
            break
        # DYNAMIC CAP: Does this hand cost more than the value of the actions they provide?
        if a > MAV * effective_work_per_hand * 0.95: # 5% safety margin on labor value
            break
        spend += a
        n += 1
        a, b = b, a + b
        
    # Elastic labor scaling: scale up to 13-14 hands when flush with cash and land
    max_h = P["max_hands"]
    if st.money >= 3500 and nq >= 1:
        max_h = 14
    elif st.money >= 2000 and nq >= 1:
        max_h = 13

    if st.day >= FINAL_DAY:
        # Endgame harvest sweep: guarantee 8-12 hands on the final day to sweep all tiles
        sweep_hands = max(8, min(12, by_work))
        plan["hands"] = max(0, min(sweep_hands, max_h))
    else:
        plan["hands"] = max(0, min(n, by_work, max_h))
    return plan

def wheat_keep(st, plan):
    """Target wheat stock in the shed.  Every animal eats one per day, so this
    has to track herd size - but the shed only holds 100 items total, so it is
    topped up through the day rather than hoarded.
    Gap 8: Also reserves carry wheat before wheat_carry_sell_day so it is
    held as a commodity position and released for sale after that day."""
    if st.day >= FINAL_DAY:
        return 0
    n = plan["animals"] + sum(st.shed.get(k, 0) for k in ANIMALS)
    feed_keep = int(min(P["max_wheat_stock"], n * P["wheat_buffer_days"] + 4))
    # Add carry position only while we're in the hold window
    carry = P["wheat_carry_max"] if st.day <= P["wheat_carry_sell_day"] else 0
    return int(min(P["max_wheat_stock"], feed_keep + carry))


def sell_timing_mult(hour):
    """Town shops drain shared market inventory every 4 steps (hour % 4 == 0,
    i.e. hours 0, 4, 8 ... are the actual drain ticks). Price rises after each
    drain tick as inventory empties. Bias the effective reserve accordingly:
    lower (sell more readily) at hour%4==1 (just after drain, price rising),
    higher (hold back) at hour%4==0 (drain tick itself, price about to rise)."""
    if hour % 4 == 1:
        return 0.90
    if hour % 4 == 0:
        return 1.12
    return 1.0


def market_orders(st, plan, bought):
    """Sells are queued ahead of buys (they fund them), but buys reserve slots
    first - otherwise nine products in the shed eat the whole 10-order budget."""
    reserve = plan["reserve"]
    keep = wheat_keep(st, plan)
    timing = sell_timing_mult(st.hour)

    # --- what could we sell, and what would it raise? ------------------
    sells = []
    revenue = 0.0
    for item in PRODUCTS:
        have = st.shed.get(item, 0)
        if item == "WHEAT":
            have -= keep
        if have <= 0:
            continue
        n = units_sellable(item, st.minv[item], reserve[item] * timing, have)
        if n > 0:
            gain = n * st.prices[item]
            revenue += gain
            sells.append((gain, ["SELL", item, int(n)]))
    sells.sort(reverse=True, key=lambda z: z[0])

    buys = []
    money = st.money + revenue * 0.9
    hold = plan["feed_reserve"]

    # --- hires: 10 hands cost $143 for 230 extra actions.  Nothing else on
    #     the board is remotely this cheap, so they queue ahead of everything.
    #     Fixed: st.day <= FINAL_DAY allows hiring on Day 29 for final harvest sweep!
    if st.hour <= 2 and st.day <= FINAL_DAY:
        want_h = plan["hands"] - st.hires_today
        a, b = 1, 1
        for _ in range(st.hires_today):
            a, b = b, a + b
        while want_h > 0 and len(buys) < 6:
            if money - 20 < a:
                break
            buys.append(["HIRE"])
            money -= a
            a, b = b, a + b
            want_h -= 1

    # --- feed wheat: a starved animal is a total write-off -------------
    if plan["animals"] > 0 and st.day < FINAL_DAY:
        short = keep - st.shed.get("WHEAT", 0)
        short = min(short, 100 - st.shed_used - 2, 60 - bought.get("WHEAT", 0))
        if short > 0:
            wp = market_price("WHEAT", st.minv["WHEAT"] - 1)
            # Starving an animal forfeits its purchase price and every future
            # yield, so when the buffer runs dry we pay almost any price.
            ceiling = P["panic_wheat_price"] \
                if st.shed.get("WHEAT", 0) < plan["animals"] else P["max_wheat_price"]
            if wp <= ceiling:
                n = int(min(short, max(0, money // wp)))
                if n > 0:
                    buys.append(["BUY_PRODUCT", "WHEAT", n])
                    bought["WHEAT"] = bought.get("WHEAT", 0) + n
                    money -= n * wp

    # --- land: cheapest $/tile on the board ----------------------------
    nq = len(st.unlocked) - 1
    if plan["buy_land"] and nq < 2:
        cost = (1000, 2000, 4000)[nq]
        if money - hold >= cost:
            buys.append(["BUY_LAND"])
            money -= cost

    # --- animals ------------------------------------------------------
    if st.day <= P["stop_animals_day"]:
        for kind in ("SHEEP", "COW", "GOOSE"):
            a = ANIMALS[kind]
            owned = plan["have"][kind]
            need = plan["want"][kind] - owned
            free = (plan["coops_free"] + plan["build_coops"]) if kind == "GOOSE" \
                else (plan["pastures_free"] + plan["build_pastures"])
            need = min(need, free, 100 - st.shed_used - 1)
            if need <= 0:
                continue
            n = int(min(need, max(0, (money - hold - P.get("animal_buy_buffer", 400.0)) // a["cost"])))
            if n > 0:
                buys.append(["BUY_ANIMAL", kind, n])
                money -= n * a["cost"]

    # --- seeds --------------------------------------------------------
    for crop, target in sorted(plan["crop_targets"].items(),
                               key=lambda kv: -CROPS[kv[0]]["seed"]):
        have = st.seeds.get(crop, 0)
        need = target - have - bought.get(crop, 0)
        if need <= 0:
            continue
        cost = CROPS[crop]["seed"]
        n = int(min(need, max(0, (money - hold) // cost)))
        if n > 0:
            buys.append(["BUY_SEED", crop, n])
            bought[crop] = bought.get(crop, 0) + n
            money -= n * cost

    # --- wheat carry trade: buy low early, sell high late (Gap 8) -------
    # Placed AFTER animals and seeds so it never competes with early-game
    # animal purchases. Wheat price rises ~$1/day guaranteed.
    # On Day 0-8 (when price is $25-32), buy up to wheat_carry_max surplus units.
    # On Day 18+, wheat_keep drops the carry reservation and the normal sell
    # loop liquidates the held wheat at the higher late-game price.
    wheat_price_buy = market_price("WHEAT", st.minv["WHEAT"] - 1)
    if (P["wheat_carry_max"] > 0 and
            st.day <= P["wheat_carry_buy_day"] and
            wheat_price_buy <= P["wheat_carry_buy_price"] and
            st.day < FINAL_DAY):
        carry_have = st.shed.get("WHEAT", 0) - (keep - P["wheat_carry_max"])
        carry_short = P["wheat_carry_max"] - max(0, carry_have)
        carry_short = min(carry_short, 100 - st.shed_used - 2,
                          60 - bought.get("WHEAT", 0))
        if carry_short > 0 and money - hold > carry_short * wheat_price_buy:
            n = int(min(carry_short, max(0, (money - hold) // wheat_price_buy)))
            if n > 0:
                buys.append(["BUY_PRODUCT", "WHEAT", n])
                bought["WHEAT"] = bought.get("WHEAT", 0) + n
                money -= n * wheat_price_buy

    buys = buys[:8]
    room = 10 - len(buys)
    return [o for _, o in sells[:room]] + buys


# --------------------------------------------------------------------------
# tasks
# --------------------------------------------------------------------------
class T(object):
    __slots__ = ("v", "pos", "act", "need", "key", "unit")

    def __init__(self, v, pos, act, key, need=None, unit=None):
        self.v = v
        self.pos = pos
        self.act = act
        self.key = key
        self.need = need
        self.unit = unit          # None = any unit; else only that unit index


def build_tasks(st, plan):
    tasks = []
    add = tasks.append
    day = st.day
    dl = st.days_left
    step = day * TPD + st.hour
    pr = st.prices
    reserve = plan["reserve"]
    endgame = day >= FINAL_DAY
    opp_dump = plan.get("opp_dump", {})

    fert_val = max(pr["FERTILIZER"], reserve["FERTILIZER"])
    if pr["FERTILIZER"] < reserve["FERTILIZER"] and not endgame:
        fert_val = pr["FERTILIZER"] * 0.5
    
    # Reduce fertilizer collection priority during opponent dump
    fert_weight = P["fert_weight"]
    if opp_dump.get("FERTILIZER", False):
        fert_weight *= 0.3  # Don't chase crashing fertilizer prices
    elif compute_price_velocity(st, "FERTILIZER") < -2.0:
        fert_weight *= 0.6  # Softening market
    
    collect_val = fert_val * fert_weight

    seeds_left = dict(st.seeds)
    plant_quota = {}
    for crop, target in plan["crop_targets"].items():
        plant_quota[crop] = min(seeds_left.get(crop, 0), target)

    unfed = 0
    feed_val = 0.0
    want_fert = 0
    placing = {}

    coop_sites = plan["coop_sites"]
    pasture_sites = plan["pasture_sites"]
    plant_iter = iter(plan["plant_sites"])
    planted_here = {}
    for crop in plant_quota:
        for _ in range(plant_quota[crop]):
            pos = next(plant_iter, None)
            if pos is None:
                break
            planted_here[pos] = crop

    for y in range(st.n):
        row = st.tiles[y]
        for x in range(st.n):
            t = row[x]
            pos = (x, y)

            if t is None:
                if pos in coop_sites:
                    add(T(430.0, pos, ["BUILD_COOP"], ("B", x, y)))
                elif pos in pasture_sites:
                    add(T(560.0, pos, ["BUILD_PASTURE"], ("B", x, y)))
                elif pos in planted_here:
                    crop = planted_here[pos]
                    c = CROPS[crop]
                    val = 30.0 + 6.0 * pr[crop] / max(1, c["maxday"])
                    add(T(val, pos, ["PLANT", crop], ("P", x, y), "seed:" + crop))
                continue

            if t == "LOCKED" or not isinstance(t, dict):
                continue

            kind = t.get("kind")

            if kind == "WEED":
                if dl >= 2:
                    d_shed = min(abs(x - sx) + abs(y - sy) for sx, sy in st.shed_tiles)
                    usable = len(plan.get("empties", []))
                    # Weeds adjacent to shed (d <= 2) are high value to clear prime pasture space
                    if d_shed <= 2 and usable < 15:
                        dig_val = 220.0 - d_shed * 30.0
                    elif usable <= 8:
                        dig_val = 160.0 / (1.0 + d_shed * 0.3)
                    else:
                        dig_val = 15.0 # deprioritize distant weeds when plenty of land is free
                    add(T(dig_val, pos, ["DIG"], ("D", x, y)))
                continue

            if kind == "PLANT":
                c = CROPS[t["crop"]]
                price = pr[t["crop"]]
                age = day - t["planted_day"]
                yu = t["yield_units"]
                mls = t["max_lifespan_step"]
                decaying = 0 <= mls <= step
                fert_on = t.get("fertilized_until_day", -1) >= day

                # --- harvest
                if yu > 0 and age >= c["first"]:
                    if c["ongoing"]:
                        if yu >= 2 or decaying or dl <= 0 or (endgame and st.hour > 4):
                            val = max(yu * price * (2.0 if endgame else 0.9), 250.0 if endgame else 40.0)
                            add(T(val, pos, ["HARVEST"], ("H", x, y)))
                    else:
                        if age >= c["maxday"] or yu >= c["cap"] or decaying or dl <= 0:
                            val = max(yu * price * (2.0 if endgame else 1.0) + 40.0, 300.0 if endgame else 40.0)
                            add(T(val, pos, ["HARVEST"], ("H", x, y)))
                elif not c["ongoing"] and decaying and yu > 0:
                    add(T(yu * price * (2.0 if endgame else 1.0), pos, ["HARVEST"], ("H", x, y)))

                if endgame:
                    continue

                # --- water
                if not t["watered_today"]:
                    v = 0.0
                    if t["consecutive_unwatered"] >= 1:
                        v = 55.0 + 3.0 * price  # dies tonight otherwise
                    if c["ongoing"]:
                        if fert_on:
                            nd = day + 1 - t["planted_day"] - c["first"]
                            if nd >= 0 and nd % c["interval"] == 0 and yu < c["cap"]:
                                v = max(v, price * 0.95)
                    else:
                        w0 = (c["maxday"] + 1) // 2
                        if w0 <= age <= c["maxday"] and yu < c["cap"]:
                            v = max(v, price * (2.0 if fert_on else 1.0) * 0.95)
                    if v <= 0.0 and age < c["maxday"] + 2:
                        v = max(90.0, 40.0 + 7.0 * price / max(1, c["maxday"]))
                    if v > 0.0:
                        add(T(v, pos, ["WATER"], ("W", x, y)))

                # --- fertilise (only pays on ongoing crops)
                if c["ongoing"] and not fert_on and age + 2 >= c["first"] - 1:
                    remaining = (dl - max(0, c["first"] - age)) // c["interval"] + 1
                    hits = min(2, max(0, remaining))
                    if hits > 0 and price > fert_val * 0.8:
                        want_fert += 1
                        add(T(hits * price * 0.85, pos, ["FERTILIZE"], ("F", x, y),
                              "FERTILIZER"))
                continue

            if kind in ("COOP", "PASTURE"):
                animal = t.get("animal")
                if animal is None:
                    for a_kind in ("SHEEP", "COW", "GOOSE"):
                        if ANIMALS[a_kind]["struct"] != kind:
                            continue
                        if st.shed.get(a_kind, 0) - placing.get(a_kind, 0) > 0:
                            placing[a_kind] = placing.get(a_kind, 0) + 1
                            add(T(900.0, pos, ["PLACE", a_kind], ("A", x, y),
                                  "animal:" + a_kind))
                            break
                    continue

                a = ANIMALS[animal]
                price = pr[a["prod"]]
                yu = t["yield_units"]
                per_prod = 1 + t.get("pending_care_bonus", 0)

                # --- harvest first (frees the max_held cap)
                if yu > 0:
                    urgency = 2.5 if endgame else (1.6 if yu + per_prod > a["held"] else 1.0)
                    h_val = max(yu * price * urgency, 350.0 if endgame else 180.0)
                    if endgame or yu >= 2 or a["interval"] == 1:
                        add(T(h_val, pos, ["HARVEST"], ("H", x, y)))

                if endgame:
                    if t.get("fertilizer_available"):
                        add(T(collect_val * 1.5, pos, ["COLLECT_FERTILIZER"], ("C", x, y)))
                    continue

                # --- feed (survival + enables production and care bonus)
                if not t["fed_today"] and dl > 0:
                    v = max(price * (1.0 + a["interval"]) / float(a["interval"]), 200.0)
                    if t["consecutive_unfed"] >= 1:
                        v += 400.0 + a["cost"]
                    unfed += 1
                    feed_val = max(feed_val, v)
                    add(T(v, pos, ["FEED"], ("E", x, y), "WHEAT"))

                # --- care banks +1 unit on the next production, but ONLY if the
                #     animal is also fed today and has enough time left to produce.
                if t["fed_today"] and not t["cared_today"]:
                    nxt = day + 1 - t["placed_day"] - a["first"]
                    prod_soon = nxt >= 0 and nxt % a["interval"] == 0
                    waste = prod_soon and (yu + per_prod + 1 > a["held"])
                    # Suppress care if the animal's next harvest falls past season end
                    if not waste and dl >= a["interval"]:
                        add(T(max(price * 0.92, 190.0), pos, ["CARE"], ("R", x, y)))

                if t.get("fertilizer_available"):
                    add(T(collect_val, pos, ["COLLECT_FERTILIZER"], ("C", x, y)))
                continue

    # ---- logistics --------------------------------------------------------
    # These must be real tasks.  As idle-unit fallbacks they never fire: with a
    # full board no unit is ever idle, and animals rot in the shed unplaced.
    sheds = st.shed_tiles
    nu = len(st.units)
    held = [st.inv(i) for i in range(nu)]

    for a_kind, n in placing.items():
        have_carried = sum(1 for iv in held if iv.get(a_kind, 0) > 0)
        for i in range(min(n - have_carried, 3)):
            add(T(880.0, sheds[i % 4], ["PICKUP", a_kind, 1],
                  ("PKA", a_kind, i), None))

    # Wheat has to be spread across *many* units, not fetched by one courier.
    # A unit with no wheat cannot FEED, so it burns its turn on fertilizer or
    # care instead and the herd starves next to a full shed.  Every unit spawns
    # shed-adjacent at hour 0, so a stock-up there costs one action and no
    # travel at all.
    stock = st.shed.get("WHEAT", 0)
    if unfed > 0 and stock > 0:
        carried = sum(iv.get("WHEAT", 0) for iv in held)
        short = unfed - carried
        if short > 0:
            per = max(P["wheat_grab_min"], int(math.ceil(unfed / float(max(1, nu)))) + 2)
            grab = int(min(stock, per, 15))
            wanted = int(math.ceil(short / float(grab)))
            given = 0
            for ui in range(nu):
                if given >= wanted:
                    break
                if held[ui].get("WHEAT", 0) > 0:
                    continue
                sd = min(sheds, key=lambda p: dist(st.units[ui], p))
                add(T(feed_val * 0.9, sd, ["PICKUP", "WHEAT", grab],
                      ("PKW", ui), None, ui))
                given += 1

    if want_fert > 0 and st.shed.get("FERTILIZER", 0) > 0:
        carried = sum(iv.get("FERTILIZER", 0) for iv in held)
        if want_fert > carried:
            grab = int(min(st.shed.get("FERTILIZER", 0), want_fert - carried, 8))
            add(T(fert_val * 1.1, sheds[0], ["PICKUP", "FERTILIZER", grab],
                  ("PKF", 0), None))

    # Produce is only sellable once it reaches the shed, and end-of-day
    # overflow past shedCapacity is destroyed outright.
    room = 100 - st.shed_used
    for ui in range(nu):
        iv = held[ui]
        load = 0
        worth = 0.0
        for k, v in iv.items():
            if k in SELLABLE:
                load += v
                worth += v * pr.get(k, 0)
        if load <= 0:
            continue
        urgent = endgame or (st.hour >= 18) or load >= 8
        if not urgent and load < 4:
            continue
        if load > room and not endgame:
            continue
        v = worth * (3.0 if endgame else 0.22)
        sd = min(sheds, key=lambda p: dist(st.units[ui], p))
        add(T(v, sd, ["DROP"], ("DR", ui), None, ui))

    return tasks


def can_do(need, inv, st):
    if need is None:
        return True
    if need.startswith("seed:"):
        return True
    if need.startswith("animal:"):
        return inv.get(need[7:], 0) > 0
    return inv.get(need, 0) > 0


# --------------------------------------------------------------------------
# unit scheduling
# --------------------------------------------------------------------------
SELLABLE = set(PRODUCTS)


def schedule(st, plan, sticky):
    tasks = build_tasks(st, plan)
    nu = len(st.units)
    acts = [None] * nu
    endgame = st.day >= FINAL_DAY

    pairs = []
    for ui in range(nu):
        upos = st.units[ui]
        inv = st.inv(ui)
        for t in tasks:
            if t.unit is not None and t.unit != ui:
                continue
            if not can_do(t.need, inv, st):
                continue
            d = dist(upos, t.pos)
            # Value per action spent, with travel penalised super-linearly:
            # a unit that stays put can chain feed -> care -> harvest -> collect
            # on one tile, which is worth far more than any single far task.
            sc = t.v / (1.0 + d) ** P["dist_pow"]
            last = sticky.get(ui)
            if last is not None:
                if last[0] == t.key:
                    sc *= P["sticky"]
                elif last[1] == t.pos:
                    # same tile as last turn -> chain the animal's other chores
                    sc *= P["sticky_pos"]
            pairs.append((sc, ui, t))
    pairs.sort(key=lambda z: -z[0])

    used_u = set()
    used_k = set()
    plant_used = {}
    for sc, ui, t in pairs:
        if ui in used_u or t.key in used_k:
            continue
        if t.need and t.need.startswith("seed:"):
            crop = t.need[5:]
            avail = st.seeds.get(crop, 0)
            if plant_used.get(crop, 0) >= avail:
                continue
            if st.units[ui] == t.pos:
                plant_used[crop] = plant_used.get(crop, 0) + 1
        used_u.add(ui)
        used_k.add(t.key)
        sticky[ui] = (t.key, t.pos)
        if st.units[ui] == t.pos:
            acts[ui] = t.act
        else:
            acts[ui] = step_toward(st.units[ui], t.pos)

    # ---- idle units: fetch what blocked tasks need, or drop produce -----
    need_wheat = 0
    need_fert = 0
    need_animal = None
    for t in tasks:
        if t.key in used_k or not t.need:
            continue
        if t.need == "WHEAT":
            need_wheat += 1
        elif t.need == "FERTILIZER":
            need_fert += 1
        elif t.need.startswith("animal:"):
            need_animal = t.need[7:]

    for ui in range(nu):
        if acts[ui] is not None:
            continue
        upos = st.units[ui]
        inv = st.inv(ui)
        sd = min(st.shed_tiles, key=lambda p: dist(upos, p))
        at_shed = upos in st.shed_tiles

        carried = sum(v for k, v in inv.items() if k in SELLABLE)
        if endgame and carried > 0:
            acts[ui] = ["DROP"] if at_shed else step_toward(upos, sd)
            sticky[ui] = None
            continue

        if need_animal and st.shed.get(need_animal, 0) > 0 and inv.get(need_animal, 0) == 0:
            acts[ui] = ["PICKUP", need_animal, 1] if at_shed else step_toward(upos, sd)
            sticky[ui] = None
            need_animal = None
            continue

        if need_wheat > 0 and inv.get("WHEAT", 0) == 0 and st.shed.get("WHEAT", 0) > 0:
            n = int(min(st.shed.get("WHEAT", 0), max(4, need_wheat)))
            acts[ui] = ["PICKUP", "WHEAT", n] if at_shed else step_toward(upos, sd)
            sticky[ui] = None
            need_wheat -= n
            continue

        if need_fert > 0 and inv.get("FERTILIZER", 0) == 0 and st.shed.get("FERTILIZER", 0) > 0:
            n = int(min(st.shed.get("FERTILIZER", 0), max(2, need_fert)))
            acts[ui] = ["PICKUP", "FERTILIZER", n] if at_shed else step_toward(upos, sd)
            sticky[ui] = None
            need_fert -= n
            continue

        if carried >= 3 and st.shed_used + carried <= 100:
            acts[ui] = ["DROP"] if at_shed else step_toward(upos, sd)
            sticky[ui] = None
            continue

        if not at_shed and carried > 0:
            acts[ui] = step_toward(upos, sd)
            sticky[ui] = None
            continue

        acts[ui] = ["PASS"]
        sticky[ui] = None

    return acts


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------
_MEM = {}


def _mem(pid):
    m = _MEM.get(pid)
    if m is None:
        m = {"day": -1, "plan": None, "bought": {}, "sticky": {}, 
             "price_history": {p: [] for p in PRODUCTS}, "market_velocity": {p: 0.0 for p in PRODUCTS}}
        _MEM[pid] = m
    return m


def agent(obs):
    if obs.get("step", 0) == 0:
        _MEM.pop(obs.get("player"), None)
    st = S(obs)
    m = _mem(st.pid)
    if m["day"] != st.day:
        m["day"] = st.day
        m["bought"] = {}
        m["sticky"] = {}
    # Restore persisted price history
    st.price_history = m["price_history"]
    st.market_velocity = m["market_velocity"]
    # Replan every turn (~0.5ms).  A stale plan re-issues the same BUY_ANIMAL
    # order before the board reflects the previous one, which silently buys the
    # herd several times over.
    plan = m["plan"] = build_plan(st)
    # Persist updated price history
    m["price_history"] = st.price_history
    m["market_velocity"] = st.market_velocity

    # Our native Endgame Liquidation Protocol is already running inside build_plan()

    orders = market_orders(st, plan, m["bought"])
    acts = schedule(st, plan, m["sticky"])

    return {"farmer": acts[0] if acts else ["PASS"],
            "hands": acts[1:],
            "market": orders}
