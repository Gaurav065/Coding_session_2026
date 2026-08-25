


ANIMALS = {
    "GOOSE": {"cost": 100, "product": "EGG"},
    "SHEEP": {"cost": 400, "product": "WOOL"},
    "COW": {"cost": 500, "product": "MILK"}
}
PRODUCT_ANIMAL = {v["product"]: k for k, v in ANIMALS.items()}
ANIMAL_PRODUCT = {k: v["product"] for k, v in ANIMALS.items()}

FARM_HAND_COST_MULT = 1
PRICE_FLOOR = 1
MARKET_I0 = 1000

SHOPS = {
    "Restaurant": ["CARROT", "TOMATO", "MILK", "EGG"],
    "Bakery": ["WHEAT", "EGG", "MILK", "STRAWBERRY"],
    "Market": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"],
    "Farm Stand": ["CARROT", "STRAWBERRY", "MELON", "EGG"],
    "Textile Mill": ["WOOL"],
    "Butcher": ["EGG"],
    "Dairy": ["MILK"],
    "Greengrocer": ["TOMATO", "MELON"]
}
ARCHETYPES = list(SHOPS.keys())

with open('continuous_agent/main_dynamic.py', 'r') as f:
    text = f.read()

import re
idx = text.find('
ANIMALS = {
    "GOOSE": {"cost": 100, "product": "EGG"},
    "SHEEP": {"cost": 400, "product": "WOOL"},
    "COW": {"cost": 500, "product": "MILK"}
}
PRODUCT_ANIMAL = {v["product"]: k for k, v in ANIMALS.items()}
ANIMAL_PRODUCT = {k: v["product"] for k, v in ANIMALS.items()}

FARM_HAND_COST_MULT = 1
PRICE_FLOOR = 1
MARKET_I0 = 1000

SHOPS = {
    "Restaurant": ["CARROT", "TOMATO", "MILK", "EGG"],
    "Bakery": ["WHEAT", "EGG", "MILK", "STRAWBERRY"],
    "Market": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"],
    "Farm Stand": ["CARROT", "STRAWBERRY", "MELON", "EGG"],
    "Textile Mill": ["WOOL"],
    "Butcher": ["EGG"],
    "Dairy": ["MILK"],
    "Greengrocer": ["TOMATO", "MELON"]
}
ARCHETYPES = list(SHOPS.keys())

with open('continuous_agent/main_dynamic.py', 'r') as f:
    text = f.read()

import re
idx = text.find('
CROPS = {"WHEAT": {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": false}, "CARROT": {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": false}, "TOMATO": {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": true}, "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": true}, "MELON": {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": false}}
ANIMALS = {"GOOSE": {"cost": 300, "structure": "COOP", "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"}, "COW": {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"}, "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"}}
PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]
PRODUCT_ANIMAL = {v["product"]: k for k, v in ANIMALS.items()}
ANIMAL_PRODUCT = {k: v["product"] for k, v in ANIMALS.items()}
FARM_HAND_COST_MULT = 1
PRICE_FLOOR = 1
MARKET_I0 = 1000
SHOPS = {
    "Restaurant": ["CARROT", "TOMATO", "MILK", "EGG"],
    "Bakery": ["WHEAT", "EGG", "MILK", "STRAWBERRY"],
    "Market": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"],
    "Farm Stand": ["CARROT", "STRAWBERRY", "MELON", "EGG"],
    "Textile Mill": ["WOOL"],
    "Butcher": ["EGG"],
    "Dairy": ["MILK"],
    "Greengrocer": ["TOMATO", "MELON"]
}
ARCHETYPES = list(SHOPS.keys())

_CURRENT_GAP = {}')
if idx != -1:
    text = text[:idx] + "\n" + open('add_animals.py', 'r').read() + "\n" + text[idx:]

with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(text)
print("ANIMALS AND CONSTANTS ADDED")

_CURRENT_GAP = {}')
if idx != -1:
    text = text[:idx] + "\n" + open('add_animals.py', 'r').read() + "\n" + text[idx:]

with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(text)
print("ANIMALS AND CONSTANTS ADDED")

_CURRENT_GAP = {}
_LAST_SHADOW_PRICE = 50.0
_PLANNED_PLACEMENTS = {}
import json
import copy
import os

_TAPES = {}
_OPP_MODEL = None
_CURRENT_TAPE = "143k"
_LAST_STEP = -1

_BASE_PRICE = {"MELON": 250, "STRAWBERRY": 120, "MILK": 160, "WOOL": 200, "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "EGG": 50, "FERTILIZER": 100}
_GLUT_WEIGHT = {"MELON": 3.6, "STRAWBERRY": 1.6, "MILK": 1.6, "WOOL": 3.2, "WHEAT": 0.2, "CARROT": 0.7, "TOMATO": 0.6, "EGG": 0.2, "FERTILIZER": 0.4}
_SELLABLE = ("STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "TOMATO", "CARROT", "WHEAT", "FERTILIZER")

def load_tapes():
    pass

    global _TAPES
    if _TAPES: return
    base_dir = os.path.dirname(os.path.abspath(__file__))
    tapes_to_load = {
        "143k": "top_tape_143954.json",
        "133k": "second_best_tape_133k.json"
    }
    for tid, fname in tapes_to_load.items():
        path = os.path.join(base_dir, fname)
        if os.path.exists(path):
            with open(path, 'r') as f:
                _TAPES[tid] = json.load(f)
        else:
            _TAPES[tid] = [{"farmer": ["PASS"], "hands": [], "market": []}] * 720

class OpponentModel:
    def __init__(self):
        self.shed_inventory = {}

    def update(self, obs):
        pass 

    def forecast(self, obs, H=5):
        player = obs.get("player", 0)
        farms = obs.get("farms", [])
        if len(farms) < 2: return [{}] * H
        
        opp_farm = farms[1 - player]
        tiles = opp_farm.get("tiles", [])
        
        ripe_counts = {}
        for row in tiles:
            for tile in row:
                if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    crop = tile.get("crop")
                    y = int(tile.get("yield_units", 0) or 0)
                    if y > 0:
                        ripe_counts[crop] = ripe_counts.get(crop, 0) + y
                elif isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    y = int(tile.get("yield_units", 0) or 0)
                    if y > 0:
                        product = {"COW": "MILK", "SHEEP": "WOOL", "GOOSE": "EGG"}.get(animal)
                        if product:
                            ripe_counts[product] = ripe_counts.get(product, 0) + y
                            
        forecast_sales = []
        for step_delta in range(1, H+1):
            expected = {}
            if step_delta == min(H, 2): 
                for item, count in ripe_counts.items():
                    if item in ["MELON", "STRAWBERRY", "MILK", "WOOL"] and count >= 2:
                        expected[item] = count
            forecast_sales.append(expected)
            
        return forecast_sales

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
            
    for alt_id, alt_tape in tapes.items():
        if alt_id != cur_id:
            alt_actions = []
            for i in range(H):
                if step + i < len(alt_tape):
                    alt_actions.append(copy.deepcopy(alt_tape[step + i]))
                else:
                    alt_actions.append({"farmer": ["PASS"], "hands": [], "market": []})
            candidates.append({"tape_id": alt_id, "actions": alt_actions, "type": "switch"})
            
    return candidates

def compute_score(c, state, H, opp_forecast):
    G_profit = 0
    G_defense = 0
    C_risk = 0
    market_prices = state.get("market", {}).get("prices", {})
    
    for i, act in enumerate(c["actions"]):
        for order in act.get("market", []):
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                item = order[1]
                qty = int(order[2] or 0)
                p = float(market_prices.get(item, _BASE_PRICE.get(item, 10)))
                G_profit += qty * p
                
                opp_dump = opp_forecast[i].get(item, 0)
                if opp_dump > 0:
                    price_drop = _GLUT_WEIGHT.get(item, 1.0) * opp_dump
                    G_defense -= qty * price_drop * 10
                    
                for future_i in range(i+1, H):
                    if opp_forecast[future_i].get(item, 0) > 0:
                        G_defense += qty * 50
                        
    if c["type"] == "switch":
        C_risk += 500
    if c["type"] == "front_run":
        G_defense += 10
        
    return G_profit + G_defense - C_risk

def move_toward(pos, target, tiles):
    x, y = pos
    tx, ty = target
    choices = []
    if tx < x: choices.append(("WEST", (x - 1, y)))
    if tx > x: choices.append(("EAST", (x + 1, y)))
    if ty < y: choices.append(("NORTH", (x, y - 1)))
    if ty > y: choices.append(("SOUTH", (x, y + 1)))
    size = len(tiles)
    for op, (nx, ny) in choices:
        if 0 <= nx < size and 0 <= ny < size and tiles[ny][nx] != "LOCKED":
            return [op]
    return ["PASS"]

def efficiency_overlay(action, obs):
    player = obs.get("player", 0)
    farm = (obs.get("farms") or [])[player]
    tiles = farm.get("tiles") or []
    size = len(tiles)
    positions = [farm.get("farmer", [0, 0])] + (farm.get("hands") or [])
    
    unwatered = set()
    unfed = set()
    weeds = set()
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if isinstance(tile, dict):
                if tile.get("kind") == "WEED":
                    weeds.add((x, y))
                elif tile.get("kind") == "PLANT" and int(tile.get("consecutive_unwatered", 0) or 0) > 0:
                    if int(tile.get("yield_units", 10) or 0) > 0:
                        unwatered.add((x, y))
                elif tile.get("kind") in ["COOP", "PASTURE"] and tile.get("animal") and int(tile.get("consecutive_unfed", 0) or 0) > 0:
                    unfed.add((x, y))

    tasks = unwatered | unfed | weeds
    ops = [action.get("farmer", ["PASS"])] + (action.get("hands") or [])
    ops += [["PASS"]] * max(0, len(positions) - len(ops))
    
    for i, (pos_raw, op) in enumerate(zip(positions, ops)):
        if op and op[0] == "PASS" and tasks:
            pos = tuple(pos_raw)
            x, y = pos
            if pos in unwatered:
                new_op = ["WATER"]
                unwatered.discard(pos)
                tasks.discard(pos)
            elif pos in unfed:
                my_inv = (obs.get("private") or {}).get("shed", {}).get("WHEAT", 0)
                if my_inv > 0:
                    new_op = ["FEED"]
                    unfed.discard(pos)
                    tasks.discard(pos)
                else:
                    new_op = ["PASS"]
            elif pos in weeds:
                new_op = ["DIG"]
                weeds.discard(pos)
                tasks.discard(pos)
            else:
                target = min(tasks, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
                new_op = move_toward(pos, target, tiles)
                
            if i == 0:
                action["farmer"] = new_op
            else:
                while len(action.setdefault("hands", [])) <= i - 1:
                    action["hands"].append(["PASS"])
                action["hands"][i - 1] = new_op

def fib(n):
    if n <= 1: return 1
    a, b = 1, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

def should_buy_land(shadow_price_lambda, steps_left, extra_tiles_unlocked, land_price):
    expected_value = shadow_price_lambda * extra_tiles_unlocked * (steps_left / 720)
    return expected_value > land_price

def daily_hire_routine(obs):
    farm = obs["farms"][obs["player"]]
    n = farm.get("hires_today", 0)
    money = farm.get("money", 0)
    orders = []
    
    lam = _LAST_SHADOW_PRICE
    if lam <= 0:
        lam = 50.0 
        
    while True:
        cost = FARM_HAND_COST_MULT * fib(n)
        if lam > cost and money > cost:
            orders.append(["HIRE"])
            money -= cost
            n += 1
        else:
            break
            
    return orders, money

def _shape(f, q):
    if f == "linear": return q
    if f == "sq": return q**2
    if f == "sqrt": return math.sqrt(q)
    if f == "log": return math.log2(q+1)
    return q

def sell_proceeds(inv0, q, item):
    if q <= 0: return 0.0
    p = PRODUCTS[item]
    base, I0, T = p["base"], p["I0"], p["T"]
    above_target, f_above = p["above_target"], p["above_func"]
    
    amp = above_target * base / _shape(f_above, T)
    revenue = 0.0
    inv = inv0
    
    for _ in range(q):
        if inv >= I0:
            price = max(PRICE_FLOOR, base - amp * _shape(f_above, inv - I0))
        else:
            price = base
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
    
    ticks_left = steps_remaining // 4 
    exp_rate = current_rate + R * p_hit * hit_drain
    return int(exp_rate * ticks_left)

def sell_finished_goods(obs):
    private = obs.get("private", {})
    market_inv = obs.get("market", {}).get("inventory", {})
    unlocked_shops = obs.get("town", {}).get("unlocked_shops", [])
    step = obs.get("step", 0)
    steps_left = 720 - step
    
    orders = []
    for item, qty in private.get("shed", {}).items():
        if qty <= 0: continue
        inv0 = market_inv.get(item, MARKET_I0)
        proceeds_now = sell_proceeds(inv0, qty, item)
        
        drain = forecast_shop_drain(item, unlocked_shops, steps_left)
        inv_later = max(MARKET_I0, inv0 - drain)
        proceeds_later = sell_proceeds(inv_later, qty, item)
        
        if proceeds_now >= proceeds_later or step >= 720 - 24:
            orders.append(["SELL", item, qty])
            
    return orders


def scan_committed_capacity(obs):
    private = obs.get("private", {})
    committed = {}
    for item, qty in private.get("seeds", {}).items():
        committed[item] = committed.get(item, 0) + qty
    for item, qty in private.get("shed", {}).items():
        if item in ANIMALS:
            committed[item] = committed.get(item, 0) + qty
    farm = obs.get("farms", [{}])[obs.get("player", 0)]
    for y, row in enumerate(farm.get("tiles", [])):
        for x, tile in enumerate(row):
            if isinstance(tile, dict):
                if tile.get("kind") == "PLANT":
                    item = tile.get("crop")
                    if item:
                        committed[item] = committed.get(item, 0) + 1
                elif tile.get("kind") in ("COOP", "PASTURE"):
                    if tile.get("animal"):
                        item = tile.get("animal")
                        committed[item] = committed.get(item, 0) + 1
    return committed

def targets_to_capacity_gap(alloc_units, committed, steps_left):
    gap = {}
    for item, target in alloc_units.items():
        if item in CROPS:
            expected_yield = expected_remaining_yield(item, steps_left)
            if expected_yield > 0:
                target_capacity = math.ceil(target / expected_yield)
            else:
                target_capacity = 0
        elif item in ANIMAL_PRODUCT.values():
            animal = PRODUCT_ANIMAL[item]
            expected_yield = steps_left 
            target_capacity = math.ceil(target / max(1, expected_yield))
            item = animal 
        else:
            continue
            
        target_capacity = max(target_capacity, 1)
        gap[item] = max(0, target_capacity - committed.get(item, 0))
    return gap

def agent(obs):
    global _CURRENT_GAP, _LAST_SHADOW_PRICE, _PLANNED_PLACEMENTS
    step = obs.get("step", 0)
    steps_left = 720 - step
    market_inv = obs.get("market", {}).get("inventory", {})
    
    committed = scan_committed_capacity(obs)
    
    items_to_allocate = {}
    for item, p in PRODUCTS.items():
        if item == "FERTILIZER": continue
        per_unit_capacity = expected_remaining_yield(item, steps_left)
        if per_unit_capacity <= 0: continue
        
        if item in ANIMAL_PRODUCT.values():
            base_cost = ANIMALS[PRODUCT_ANIMAL[item]]["cost"]
        else:
            base_cost = CROPS[item]["seed_cost"]
            
        cost_per_unit = max(0.1, base_cost / max(1, per_unit_capacity))
        
        items_to_allocate[item] = {
            **p, 
            "inv0": market_inv.get(item, MARKET_I0), 
            "cost": cost_per_unit
        }
    
    alloc_units, lam = water_fill_allocate(items_to_allocate, 5000)
    _LAST_SHADOW_PRICE = lam
    
    gap = targets_to_capacity_gap(alloc_units, committed, steps_left)
    
    _CURRENT_GAP = {k: int(v) for k, v in gap.items() if v > 0}
    _PLANNED_PLACEMENTS.clear()

    action = {"farmer": ["PASS"], "hands": [], "market": []}
    
    # Sell finished goods
    action["market"].extend(sell_finished_goods(obs))
    
    # Hires
    orders, remaining_money = daily_hire_routine(obs)
    action["market"].extend(orders)
    
    # Buy seeds
    money = remaining_money
    sorted_gap = sorted(_CURRENT_GAP.items(), key=lambda kv: kv[1], reverse=True)
    for item, qty in sorted_gap:
        if item in CROPS:
            seeds_owned = obs["private"].get("seeds", {}).get(item, 0)
            if seeds_owned < qty:
                cost_per = CROPS[item]["seed_cost"]
                to_buy = min(qty - seeds_owned, int(money // cost_per))
                if to_buy > 0:
                    action["market"].append(["BUY_SEED", item, to_buy])
                    money -= to_buy * cost_per
        elif item in ANIMAL_PRODUCT.values():
            animal = PRODUCT_ANIMAL[item]
            animals_owned = obs["private"].get("shed", {}).get(animal, 0)
            if animals_owned < qty:
                cost_per = ANIMALS[animal]["cost"]
                to_buy = min(qty - animals_owned, int(money // cost_per))
                if to_buy > 0:
                    action["market"].append(["BUY_ANIMAL", animal, to_buy])
                    money -= to_buy * cost_per

    efficiency_overlay(action, obs)
    return action
