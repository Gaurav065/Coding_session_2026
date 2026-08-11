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

# --------------------------------------------------------------------------
# tunables
# --------------------------------------------------------------------------
P = {
    # never sell a unit below this price (scaled down over the last days)
    "res_WHEAT": 20, "res_CARROT": 26, "res_TOMATO": 40, "res_STRAWBERRY": 92,
    "res_MELON": 150, "res_EGG": 14, "res_MILK": 112, "res_WOOL": 145,
    "res_FERTILIZER": 55,

    "max_hands": 13,           # hard cap on hands hired per day
    "hand_budget": 150.0,      # floor on daily hand spend
    "hand_budget_frac": 0.08,  # plus this fraction of liquid cash
    "work_per_hand": 13.0,     # usable actions per hand per day (rest is travel)

    "max_geese": 18,
    "max_animals": 24,
    "wheat_buffer_days": 1.4,   # days of feed to keep in the shed
    "max_wheat_stock": 55,      # shed only holds 100 items total
    "feed_reserve_days": 3.5,   # days of feed money held back from all spending
    "max_wheat_price": 150,     # normal ceiling on bought feed wheat
    "panic_wheat_price": 260,   # ceiling when animals would otherwise starve
    "wheat_tiles_per_animal": 1.05,
    "dig_value": 130.0,         # weeds are dead tiles; clearing one is cheap

    "stop_animals_day": 25,
    "opp_share": 0.60,          # share of town drain we assume we can capture
    "yield_haircut": 0.85,      # discount on projected animal revenue
    "invest_frac": 0.90,        # share of free cash committed per planning pass
    "land_slack": 12,           # buy the next quadrant when free tiles drop here
    "dist_pow": 1.45,           # travel penalty exponent in task scoring
    "sticky": 1.6,           # bonus for continuing last turn's target
    "sticky_pos": 1.0,          # position-stickiness (1.0 = off; hurts above)
    "fert_weight": 0.6,         # COLLECT_FERTILIZER value vs its market price
    "wheat_grab_min": 8,        # minimum wheat a unit collects per shed trip
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
                 "days_left")

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
    """Units/day the town drains, blending realised shops with expected future ones."""
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
    d = st.day
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


def animal_units(kind, days_left):
    """Product units a freshly placed animal yields, assuming daily FEED+CARE."""
    a = ANIMALS[kind]
    if days_left < a["first"]:
        return 0
    n = (days_left - a["first"]) // a["interval"] + 1
    return n * (1 + a["interval"])


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
    rate = town_rates(st)
    scale = reserve_scale(st.day)
    reserve = {}
    head = {}
    for p in PRODUCTS:
        r = max(1, int(P["res_" + p] * scale)) if scale > 0 else 1
        reserve[p] = r
        head[p] = units_sellable(p, st.minv[p], r, 900) + int(rate[p] * dl * P["opp_share"])

    plan = {"reserve": reserve, "head": head, "rate": rate}

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

    plan["empties"] = empties
    plan["weeds"] = weeds
    plan["counts"] = counts
    plan["coops_free"] = coops_free
    plan["pastures_free"] = pastures_free
    animals_now = counts["GOOSE"] + counts["COW"] + counts["SHEEP"]
    plan["animals"] = animals_now
    have = dict((k, counts[k] + st.shed.get(k, 0)) for k in ANIMALS)
    owned = have["GOOSE"] + have["COW"] + have["SHEEP"]
    
    wheat_price_buy = market_price("WHEAT", st.minv["WHEAT"] - 1)
    feed_reserve = min(2600.0, owned * P["feed_reserve_days"] * wheat_price_buy)
    plan["feed_reserve"] = feed_reserve
    budget = max(0.0, st.money - feed_reserve) * P["invest_frac"]

    nq = len(st.unlocked) - 1
    effective_work_per_hand = P["work_per_hand"] - (nq * 1.5)
    if effective_work_per_hand < 7.0: effective_work_per_hand = 7.0

    # ---- dynamic crop value and MAV --------------------------------------
    cand = []
    feed_need = (owned + dl * 1.5) * dl  # rough estimate
    for crop in CROPS:
        pr = st.prices[crop]
        if crop == "WHEAT":
            pr = max(pr, min(wheat_price_buy, P["max_wheat_price"]))
        r = crop_plan_value(crop, st, pr)
        if r is None: continue
        units, occ, acts, profit = r
        if profit <= 0: continue
        room = head[crop] - pipeline[crop]
        if crop == "WHEAT": room = max(room, feed_need)
        if room < units * 0.5: continue
        
        # MAV = Marginal Action Value (profit per action)
        mav = profit / float(acts)
        cand.append((mav, crop, units, room, profit, occ, acts))
        
    cand.sort(reverse=True, key=lambda z: z[0])
    best_crop_action_val = cand[0][0] if cand else 0.0

    animal_cand = []
    for kind, a in ANIMALS.items():
        per = animal_units(kind, dl)
        if per <= 0: continue
        price = max(st.prices[a["prod"]], reserve[a["prod"]])
        gross = per * price * P["yield_haircut"]
        feed = dl * wheat_price_buy
        net = gross - a["cost"] - feed
        if net <= 0: continue
        
        acts_per_day = 1.0 + (1.0 / a["interval"]) + (1.0 / a["interval"])
        total_acts = dl * acts_per_day
        action_val = net / total_acts
        animal_cand.append((action_val, kind, per, a, net))
        
    animal_cand.sort(reverse=True, key=lambda z: z[0])
    best_animal_action_val = animal_cand[0][0] if animal_cand else 0.0
    
    MAV = max(best_crop_action_val, best_animal_action_val)
    if MAV <= 0: MAV = 10.0

    pending = coops_free + pastures_free + len(weeds)
    current_work = (animals_now * 2.8 + crop_tiles * 1.5 + pending * 1.7 + 10)
    current_hands = current_work / effective_work_per_hand

    # ---- dynamic land: evaluate ROI of 25 new tiles ----------------------
    nq = len(st.unlocked) - 1
    plan["buy_land"] = False
    if nq < 3 and dl >= 5:
        cost = (1000, 2000, 4000)[nq]
        usable_tiles = len(empties) + len(weeds)
        crowded = usable_tiles <= P["land_slack"] or nq == 0
        if crowded and budget >= cost:
            if cand:
                _, _, _, _, best_profit, best_occ, best_acts = cand[0]
                expected_cycles = max(0.5, dl / float(best_occ))
                marginal_revenue = 25 * best_profit * expected_cycles
                
                added_actions_per_day = 25 * (best_acts / float(best_occ))
                added_hands = added_actions_per_day / effective_work_per_hand
                
                current_daily_labor_cost = get_fib_cost(current_hands)
                new_daily_labor_cost = get_fib_cost(current_hands + added_hands)
                marginal_labor_cost = (new_daily_labor_cost - current_daily_labor_cost) * dl
                
                if marginal_revenue > marginal_labor_cost + cost:
                    plan["buy_land"] = True
                    budget -= cost
            elif nq == 0:
                plan["buy_land"] = True
                budget -= cost

    # ---- dynamic animal targets ------------------------------------------
    want = dict(have)
    tile_room = len(empties) + coops_free + pastures_free
    total = owned
    if st.day <= P["stop_animals_day"]:
        for action_val, kind, per, a, net in animal_cand:
            added_hands_for_animal = 2.8 / effective_work_per_hand
            marginal_labor_cost_animal = (get_fib_cost(current_hands + added_hands_for_animal) - get_fib_cost(current_hands)) * dl
            
            # If the animal's net profit over the season doesn't even cover the marginal labor cost, skip it!
            if net < marginal_labor_cost_animal:
                continue

            room = head[a["prod"]] - pipeline[a["prod"]]
            by_market = int(room // max(1, per))
            unit_cost = a["cost"] + dl * wheat_price_buy * 0.45
            by_cash = int(budget // unit_cost)
            
            n = min(by_market, by_cash, tile_room)
            if kind == "GOOSE": n = min(n, P["max_geese"] - have["GOOSE"])
            if n <= 0: continue
            
            want[kind] += n
            budget -= n * a["cost"]
            tile_room -= n
            total += n
            current_hands += n * added_hands_for_animal
    plan["want"] = want

    # ---- structures ------------------------------------------------------
    need_coops = max(0, want["GOOSE"] - counts["GOOSE"] - coops_free)
    need_past = max(0, want["COW"] + want["SHEEP"] - counts["COW"] - counts["SHEEP"] - pastures_free)
    slack = sum(st.shed.get(k, 0) for k in ANIMALS) + 2
    plan["build_coops"] = min(need_coops, slack, len(empties))
    plan["build_pastures"] = min(need_past, slack, max(0, len(empties) - plan["build_coops"]))

    ctr = (st.half - 0.5, st.half - 0.5)
    empties.sort(key=lambda p: abs(p[0] - ctr[0]) + abs(p[1] - ctr[1]))
    nb = plan["build_coops"] + plan["build_pastures"]
    plan["coop_sites"] = set(empties[:plan["build_coops"]])
    plan["pasture_sites"] = set(empties[plan["build_coops"]:nb])

    # ---- dynamic crop planting (space filling) ---------------------------
    free_for_crops = max(0, len(empties) - nb)
    feed_need = (total + want["GOOSE"] + want["COW"] + want["SHEEP"]) * dl
    
    # Re-sort cand by profit/occupancy for space efficiency
    cand_space = [(prof / float(occ), crop, units, room, prof, occ, acts) for mav, crop, units, room, prof, occ, acts in cand]
    cand_space.sort(reverse=True, key=lambda z: z[0])
    
    crop_targets = {}
    left = free_for_crops
    seed_budget = budget

    if total > 0 and dl >= 4 and left > 0:
        need = int(math.ceil(total * P["wheat_tiles_per_animal"])) - crop_counts.get("WHEAT", 0)
        n = max(0, min(need, left, int(seed_budget // CROPS["WHEAT"]["seed"])))
        if n > 0:
            crop_targets["WHEAT"] = n
            seed_budget -= n * CROPS["WHEAT"]["seed"]
            left -= n
            
    for _, crop, units, room, prof, occ, acts in cand_space:
        if left <= 0: break
        if crop in crop_targets: continue
        by_market = int(room // max(1, units)) + 1
        by_cash = int(seed_budget // CROPS[crop]["seed"])
        take = min(left, max(min(by_market, by_cash), st.seeds.get(crop, 0)))
        if take <= 0: continue
        crop_targets[crop] = take
        seed_budget -= max(0, take - st.seeds.get(crop, 0)) * CROPS[crop]["seed"]
        left -= take
        
    for crop, n in st.seeds.items():
        if n > 0 and crop not in crop_targets and left > 0:
            crop_targets[crop] = min(n, left)
            left -= crop_targets[crop]
    plan["crop_targets"] = crop_targets
    plan["plant_sites"] = [p for p in empties if p not in plan["coop_sites"] and p not in plan["pasture_sites"]]

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
        if a > MAV * effective_work_per_hand * 0.85: # 15% safety margin on labor value
            break
        spend += a
        n += 1
        a, b = b, a + b
        
    plan["hands"] = max(0, min(n, by_work)) # No max_hands cap!
    return plan

def wheat_keep(st, plan):
    """Target wheat stock in the shed.  Every animal eats one per day, so this
    has to track herd size - but the shed only holds 100 items total, so it is
    topped up through the day rather than hoarded."""
    if st.day >= FINAL_DAY:
        return 0
    n = plan["animals"] + sum(st.shed.get(k, 0) for k in ANIMALS)
    return int(min(P["max_wheat_stock"], n * P["wheat_buffer_days"] + 4))


def market_orders(st, plan, bought):
    """Sells are queued ahead of buys (they fund them), but buys reserve slots
    first - otherwise nine products in the shed eat the whole 10-order budget."""
    reserve = plan["reserve"]
    keep = wheat_keep(st, plan)

    # --- what could we sell, and what would it raise? ------------------
    sells = []
    revenue = 0.0
    for item in PRODUCTS:
        have = st.shed.get(item, 0)
        if item == "WHEAT":
            have -= keep
        if have <= 0:
            continue
        n = units_sellable(item, st.minv[item], reserve[item], have)
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
    if st.hour <= 2 and st.day < FINAL_DAY:
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
    if plan["buy_land"] and nq < 3:
        cost = (1000, 2000, 4000)[nq]
        if money - hold >= cost:
            buys.append(["BUY_LAND"])
            money -= cost

    # --- animals ------------------------------------------------------
    if st.day <= P["stop_animals_day"]:
        for kind in ("SHEEP", "COW", "GOOSE"):
            a = ANIMALS[kind]
            owned = plan["counts"][kind] + st.shed.get(kind, 0)
            need = plan["want"][kind] - owned
            free = (plan["coops_free"] + plan["build_coops"]) if kind == "GOOSE" \
                else (plan["pastures_free"] + plan["build_pastures"])
            need = min(need, free, 100 - st.shed_used - 1)
            if need <= 0:
                continue
            n = int(min(need, max(0, (money - hold) // a["cost"])))
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

    fert_val = max(pr["FERTILIZER"], reserve["FERTILIZER"])
    if pr["FERTILIZER"] < reserve["FERTILIZER"] and not endgame:
        fert_val = pr["FERTILIZER"] * 0.5
    collect_val = fert_val * P["fert_weight"]

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
                    usable = len(plan.get("empties", [])) + len(plan.get("weeds", []))
                    dig_val = 15.0 if usable > 15 else 180.0
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
                            add(T(yu * price * 0.9, pos, ["HARVEST"], ("H", x, y)))
                    else:
                        if age >= c["maxday"] or yu >= c["cap"] or decaying or dl <= 0:
                            add(T(yu * price + 40.0, pos, ["HARVEST"], ("H", x, y)))
                elif not c["ongoing"] and decaying and yu > 0:
                    add(T(yu * price, pos, ["HARVEST"], ("H", x, y)))

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
                        v = 9.0
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
                    urgency = 1.0
                    if yu + per_prod > a["held"]:
                        urgency = 1.6
                    if endgame or yu >= 2 or a["interval"] == 1:
                        add(T(max(yu * price * urgency, 180.0), pos, ["HARVEST"], ("H", x, y)))

                if endgame:
                    if t.get("fertilizer_available"):
                        add(T(collect_val, pos, ["COLLECT_FERTILIZER"], ("C", x, y)))
                    continue

                # --- feed (survival + enables production and care bonus)
                if not t["fed_today"] and dl >= 0:
                    v = max(price * (1.0 + a["interval"]) / float(a["interval"]), 200.0)
                    if t["consecutive_unfed"] >= 1:
                        v += 400.0 + a["cost"]
                    unfed += 1
                    feed_val = max(feed_val, v)
                    add(T(v, pos, ["FEED"], ("E", x, y), "WHEAT"))

                # --- care banks +1 unit on the next production, but ONLY if the
                #     animal is also fed today.  Caring an unfed animal is a
                #     wasted action, and worse, it steals the action that would
                #     have fed it.  Gate strictly on fed_today.
                if t["fed_today"] and not t["cared_today"]:
                    nxt = day + 1 - t["placed_day"] - a["first"]
                    prod_soon = nxt >= 0 and nxt % a["interval"] == 0
                    waste = prod_soon and (yu + per_prod + 1 > a["held"])
                    if not waste and dl >= 1:
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
        urgent = endgame or (st.hour >= 20) or load >= 8
        if not urgent and load < 4:
            continue
        if load > room and not endgame:
            continue
        v = worth * (0.9 if endgame else 0.22)
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
        m = {"day": -1, "plan": None, "bought": {}, "sticky": {}}
        _MEM[pid] = m
    return m


def agent(obs):
    st = S(obs)
    m = _mem(st.pid)
    if m["day"] != st.day:
        m["day"] = st.day
        m["bought"] = {}
        m["sticky"] = {}
    # Replan every turn (~0.5ms).  A stale plan re-issues the same BUY_ANIMAL
    # order before the board reflects the previous one, which silently buys the
    # herd several times over.
    plan = m["plan"] = build_plan(st)

    orders = market_orders(st, plan, m["bought"])
    acts = schedule(st, plan, m["sticky"])

    return {"farmer": acts[0] if acts else ["PASS"],
            "hands": acts[1:],
            "market": orders}
