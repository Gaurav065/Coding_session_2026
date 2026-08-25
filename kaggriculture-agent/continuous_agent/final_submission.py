import json

CROPS = {"WHEAT": {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False}, "CARROT": {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False}, "TOMATO": {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True}, "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True}, "MELON": {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False}}
ANIMALS = {"GOOSE": {"cost": 300, "structure": "COOP", "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"}, "COW": {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"}, "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"}}
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

import numpy as np
import heapq
import math

SHAPES = {
    "linear": lambda x: max(x, 0),
    "sq":     lambda x: max(x, 0) ** 2,
    "sqrt":   lambda x: math.sqrt(max(x, 0)),
    "log":    lambda x: math.log2(max(x, 0) + 1)
}

PRODUCTS = {
    "WHEAT":      {"base":  25, "I0": MARKET_I0, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "I0": MARKET_I0, "T": 450, "below_func": "log",    "below_target": 0.20, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "I0": MARKET_I0, "T": 332, "below_func": "linear", "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
}

def market_price(inv, base, I0, T, below_target, below_func, above_target, above_func):
    if inv < I0:
        amp = below_target * base / SHAPES[below_func](T)
        return max(PRICE_FLOOR, base + amp * SHAPES[below_func](I0 - inv))
    amp = above_target * base / SHAPES[above_func](T)
    return max(PRICE_FLOOR, base - amp * SHAPES[above_func](inv - I0))

def water_fill_allocate(items, capacity):
    for name, p in items.items():
        if p["cost"] <= 0:
            raise ValueError(f"{name}: cost must be > 0, got {p['cost']}")

    heap, state, used = [], {}, 0.0
    for name, p in items.items():
        state[name] = {"inv": p["inv0"], "units": 0}
        price0 = market_price(p["inv0"], p["base"], p["I0"], p["T"],
                               p["below_target"], p["below_func"], p["above_target"], p["above_func"])
        heapq.heappush(heap, (-price0 / p["cost"], name))

    while heap and used < capacity:
        neg_mp, name = heapq.heappop(heap)
        p, cost = items[name], items[name]["cost"]
        if used + cost > capacity:
            continue

        price = market_price(state[name]["inv"], p["base"], p["I0"], p["T"],
                              p["below_target"], p["below_func"], p["above_target"], p["above_func"])
        state[name]["units"] += 1
        used += cost

        if price > 1.0:
            state[name]["inv"] += 1

        next_price = market_price(state[name]["inv"], p["base"], p["I0"], p["T"],
                                   p["below_target"], p["below_func"], p["above_target"], p["above_func"])
        heapq.heappush(heap, (-next_price / cost, name))

    lam = -heap[0][0] if heap else 50.0
    return {n: s["units"] for n, s in state.items()}, lam

def expected_remaining_yield(item, steps_left):
    days_left = steps_left / 24.0
    if item in CROPS:
        crop = CROPS[item]
        first = crop["first_yield_day"]
        if days_left <= first: return 0
        if not crop["ongoing"]:
            return crop["max_yield"]
        else:
            productive_days = days_left - first
            return productive_days / (crop["interval"] + 1)
    elif item in ANIMAL_PRODUCT.values():
        animal = PRODUCT_ANIMAL[item]
        a = ANIMALS[animal]
        first = a["first_yield_day"]
        if days_left <= first: return 0
        productive_days = days_left - first
        return productive_days / (a["interval"] + 1)
    return 0

_CURRENT_GAP = {}
_LAST_SHADOW_PRICE = 50.0
_PLANNED_PLACEMENTS = {}

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
    # Max tiles per item: crops split 20 tiles, animals get 1 tile each (max 2 of each)
    MAX_CROP_TILES = 8   # per crop type
    MAX_ANIMAL_TILES = 2 # per animal type
    for item, target in alloc_units.items():
        if item in CROPS:
            expected_yield = expected_remaining_yield(item, steps_left)
            if expected_yield > 0:
                target_capacity = math.ceil(target / expected_yield)
            else:
                target_capacity = 0
            target_capacity = min(target_capacity, MAX_CROP_TILES)
        elif item in ANIMAL_PRODUCT.values():
            animal = PRODUCT_ANIMAL[item]
            expected_yield = expected_remaining_yield(item, steps_left)
            if expected_yield > 0:
                target_capacity = math.ceil(target / expected_yield)
            else:
                target_capacity = 0
            target_capacity = min(target_capacity, MAX_ANIMAL_TILES)
            item = animal
        else:
            continue

        target_capacity = max(target_capacity, 1)
        gap[item] = max(0, target_capacity - committed.get(item, 0))
    return gap

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
        if (lam / 30.0) > cost and money > cost:
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
        if s not in SHOPS: continue
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
        if item in ANIMALS or item == "FERTILIZER": continue  # not sellable through PRODUCTS
        if item not in PRODUCTS: continue
        inv0 = market_inv.get(item, MARKET_I0)
        proceeds_now = sell_proceeds(inv0, qty, item)
        
        drain = forecast_shop_drain(item, unlocked_shops, steps_left)
        inv_later = max(MARKET_I0, inv0 - drain)
        proceeds_later = sell_proceeds(inv_later, qty, item)
        
        if proceeds_now >= proceeds_later or step >= 720 - 24:
            orders.append(["SELL", item, qty])
            
    return orders

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

def assign_placements(farm, gap, private):
    empty_tiles = []
    size = len(farm["tiles"])
    for y in range(size):
        for x in range(size):
            if farm["tiles"][y][x] is None and (x, y) not in [(4,4), (5,4), (4,5), (5,5)]:
                empty_tiles.append((x, y))
    
    sorted_gap = sorted(gap.items(), key=lambda kv: kv[1], reverse=True)
    
    placements = {}
    for item, qty in sorted_gap:
        while qty > 0 and empty_tiles:
            pos = empty_tiles.pop(0)
            if item in CROPS:
                placements[pos] = item
            else:
                placements[pos] = item
            qty -= 1
            
    return placements

def efficiency_overlay(action, obs):
    player = obs.get("player", 0)
    farm = (obs.get("farms") or [])[player]
    private = obs.get("private", {})
    tiles = farm.get("tiles") or []
    step = obs.get("step", 0)

    global _CURRENT_GAP, _PLANNED_PLACEMENTS
    if _CURRENT_GAP and not _PLANNED_PLACEMENTS:
        _PLANNED_PLACEMENTS = assign_placements(farm, _CURRENT_GAP, private)

    positions = [farm.get("farmer", [0, 0])] + (farm.get("hands") or [])
    inventories = private.get("inventories", [])

    SHED_TILES = {(4, 4), (5, 4), (4, 5), (5, 5)}

    # Scan field state
    unwatered = set()
    unfed = set()
    weeds = set()
    harvests = set()
    need_place = {}   # (x,y) → animal_name: empty structure needing PLACE

    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if not isinstance(tile, dict):
                continue
            kind = tile.get("kind")
            if kind == "WEED":
                weeds.add((x, y))
            elif kind == "PLANT":
                crop = tile.get("crop")
                if crop not in CROPS:
                    continue
                ci = CROPS[crop]
                crop_age = (step // 24) - tile.get("planted_day", 0)
                if ci["ongoing"]:
                    if tile.get("yield_units", 0) > 0 and crop_age >= ci["first_yield_day"]:
                        harvests.add((x, y))
                else:
                    if crop_age >= ci["max_yield_day"]:
                        harvests.add((x, y))
                if not tile.get("watered_today"):
                    unwatered.add((x, y))
            elif kind in ("COOP", "PASTURE"):
                animal = tile.get("animal")
                if animal and animal in ANIMALS:
                    a_age = (step // 24) - tile.get("placed_day", 0)
                    if tile.get("yield_units", 0) > 0 and a_age >= ANIMALS[animal]["first_yield_day"]:
                        harvests.add((x, y))
                    elif not tile.get("fed_today"):
                        unfed.add((x, y))
                else:
                    # Empty structure — find an animal in shed that matches
                    want = "COOP" if kind == "COOP" else "PASTURE"
                    for anim, ainfo in ANIMALS.items():
                        if ainfo["structure"] == want and private.get("shed", {}).get(anim, 0) > 0:
                            need_place[(x, y)] = anim
                            break

    # Planting/building targets (only on still-empty tiles)
    valid_planned = {}
    for pos, item in _PLANNED_PLACEMENTS.items():
        px, py = pos
        if not (0 <= py < len(tiles) and 0 <= px < len(tiles[py])):
            continue
        if tiles[py][px] is not None:
            continue  # tile already occupied
        if item in CROPS and private.get("seeds", {}).get(item, 0) > 0:
            valid_planned[pos] = item
        elif item in ANIMALS and private.get("shed", {}).get(item, 0) > 0:
            valid_planned[pos] = item

    shed_wheat = private.get("shed", {}).get("WHEAT", 0)

    ops = [action.get("farmer", ["PASS"])] + (action.get("hands") or [])
    ops += [["PASS"]] * max(0, len(positions) - len(ops))

    for i, (pos_raw, op) in enumerate(zip(positions, ops)):
        if op and op[0] != "PASS":
            continue  # already has a non-PASS action

        pos = tuple(pos_raw)
        x, y = pos
        inv_i = inventories[i] if i < len(inventories) else {}
        wheat_inv = inv_i.get("WHEAT", 0)
        has_harvest_goods = any(v > 0 for k, v in inv_i.items() if k != "WHEAT")

        new_op = None

        # P1: HARVEST
        if pos in harvests:
            new_op = ["HARVEST"]
            harvests.discard(pos)

        # P2: DROP harvested goods to shed (so SELL orders can process them)
        elif pos in SHED_TILES and has_harvest_goods:
            new_op = ["DROP"]

        # P3: PLACE animal on empty structure (only if animal in carried inventory)
        elif pos in need_place:
            anim = need_place[pos]
            if inv_i.get(anim, 0) > 0:
                need_place.pop(pos)
                new_op = ["PLACE", anim, 1]
            else:
                # Don't fetch from shed here - let P5-pickup handle it
                # Just skip this priority and fall through
                pass

        # P3b: PICKUP animal from shed when at shed and there's an empty structure waiting
        if new_op is None and pos in SHED_TILES and need_place:
            # Find any animal we need to place that we don't have in inventory
            for (sx, sy), anim in need_place.items():
                if inv_i.get(anim, 0) == 0 and private.get("shed", {}).get(anim, 0) > 0:
                    new_op = ["PICKUP", anim, 1]
                    break

        # P4: FEED animal (only if already carrying wheat)
        elif pos in unfed and wheat_inv > 0:
            new_op = ["FEED"]
            unfed.discard(pos)

        # P5: PICKUP wheat from shed when there are unfed animals and no wheat in hand
        elif unfed and wheat_inv == 0 and shed_wheat > 0 and pos in SHED_TILES:
            n_pickup = min(shed_wheat, max(1, len(unfed)))
            new_op = ["PICKUP", "WHEAT", n_pickup]

        # P6: PLANT / BUILD_COOP / BUILD_PASTURE
        elif pos in valid_planned:
            item = valid_planned.pop(pos)
            if item in CROPS:
                new_op = ["PLANT", item]
            elif item == "GOOSE":
                new_op = ["BUILD_COOP"]
            else:
                new_op = ["BUILD_PASTURE"]

        # P7: WATER unwatered plant
        elif pos in unwatered:
            new_op = ["WATER"]
            unwatered.discard(pos)

        # P8: DIG weed
        elif pos in weeds:
            new_op = ["DIG"]
            weeds.discard(pos)

        else:
            # Move toward nearest priority target
            if has_harvest_goods:
                # Rush to shed to drop goods
                target = min(SHED_TILES, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
            elif wheat_inv > 0 and unfed:
                # Rush to feed animals
                target = min(unfed, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
            elif unfed and wheat_inv == 0 and shed_wheat > 0:
                # Rush to shed to pick up wheat
                target = min(SHED_TILES, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
            else:
                # Check if farmer is carrying an animal that needs to go to a structure
                carrying_animal_for_place = None
                for (sx, sy), anim in need_place.items():
                    if inv_i.get(anim, 0) > 0:
                        carrying_animal_for_place = (sx, sy)
                        break

                if carrying_animal_for_place:
                    # Move toward the structure to PLACE the animal
                    target = carrying_animal_for_place
                elif need_place and not any(inv_i.get(a, 0) > 0 for a in need_place.values()):
                    # Have empty structures but no animals in inventory → go to shed to PICKUP
                    any_in_shed = any(private.get("shed", {}).get(a, 0) > 0 for a in need_place.values())
                    if any_in_shed:
                        target = min(SHED_TILES, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
                    else:
                        # Structures need animals but none in shed — fall to general tasks
                        has_planting = bool(valid_planned)
                        target_tasks = (set(harvests) | set(valid_planned.keys()) | set(unwatered) | set(unfed))
                        if not has_planting:
                            target_tasks |= set(weeds)
                        if not target_tasks:
                            new_op = ["PASS"]
                            if i == 0:
                                action["farmer"] = new_op
                            else:
                                while len(action.setdefault("hands", [])) <= i - 1:
                                    action["hands"].append(["PASS"])
                                action["hands"][i - 1] = new_op
                            continue
                        target = min(target_tasks, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
                else:
                    # Only include weeds if no planting/harvesting tasks remain
                    has_planting = bool(valid_planned or need_place)
                    target_tasks = (set(harvests) | set(need_place.keys()) |
                                    set(valid_planned.keys()) | set(unwatered) | set(unfed))
                    if not has_planting:
                        target_tasks |= set(weeds)
                    if not target_tasks:
                        new_op = ["PASS"]
                        if i == 0:
                            action["farmer"] = new_op
                        else:
                            while len(action.setdefault("hands", [])) <= i - 1:
                                action["hands"].append(["PASS"])
                            action["hands"][i - 1] = new_op
                        continue
                    target = min(target_tasks, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
            new_op = move_toward(pos, target, tiles)

        if new_op is None:
            new_op = ["PASS"]

        if i == 0:
            action["farmer"] = new_op
        else:
            while len(action.setdefault("hands", [])) <= i - 1:
                action["hands"].append(["PASS"])
            action["hands"][i - 1] = new_op


def internal_agent(obs):
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
            base_cost = CROPS[item]["seed"]
            
        cost_per_unit = max(0.1, base_cost / max(1, per_unit_capacity))
        
        items_to_allocate[item] = {
            **p, 
            "inv0": market_inv.get(item, MARKET_I0), 
            "cost": cost_per_unit
        }
    
    alloc_units, lam = water_fill_allocate(items_to_allocate, 250)
    _LAST_SHADOW_PRICE = lam
    
    gap = targets_to_capacity_gap(alloc_units, committed, steps_left)
    
    _CURRENT_GAP = {k: int(v) for k, v in gap.items() if v > 0}
    place_targets = dict(_CURRENT_GAP)
    for item, qty in obs.get("private", {}).get("seeds", {}).items():
        place_targets[item] = place_targets.get(item, 0) + qty
    for item, qty in obs.get("private", {}).get("shed", {}).items():
        if item in ANIMALS:
            place_targets[item] = place_targets.get(item, 0) + qty
            
    _PLANNED_PLACEMENTS.clear()
    farm = obs.get("farms", [{}])[obs.get("player", 0)]
    _PLANNED_PLACEMENTS.update(assign_placements(farm, place_targets, private=obs.get("private", {})))

    action = {"farmer": ["PASS"], "hands": [], "market": []}
    
    # Sell finished goods
    action["market"].extend(sell_finished_goods(obs))
    
    # Hires
    orders, remaining_money = daily_hire_routine(obs)
    action["market"].extend(orders)
    
    # Buy seeds
    player = obs.get("player", 0)
    HARD_RESERVE = 500 if step < 600 else 0
    money = obs["farms"][player].get("money", 0) - HARD_RESERVE
    money = max(0, money)
    sorted_gap = sorted(_CURRENT_GAP.items(), key=lambda kv: kv[1], reverse=True)
    for item, qty in sorted_gap:
        if item in CROPS:
            seeds_owned = obs["private"].get("seeds", {}).get(item, 0)
            if seeds_owned < qty:
                cost_per = CROPS[item]["seed"]
                to_buy = min(qty - seeds_owned, int(money // cost_per))
                if to_buy > 0:
                    action["market"].append(["BUY_SEED", item, to_buy])
                    money -= to_buy * cost_per
        elif item in ANIMALS:
            animals_owned = obs["private"].get("shed", {}).get(item, 0)
            if animals_owned < qty:
                cost_per = ANIMALS[item]["cost"]
                to_buy = min(qty - animals_owned, int(money // cost_per))
                if to_buy > 0:
                    action["market"].append(["BUY_ANIMAL", item, to_buy])
                    money -= to_buy * cost_per
    efficiency_overlay(action, obs)
    return action

import traceback

def agent(obs):
    try:
        return internal_agent(obs)
    except Exception as e:
        with open('agent_error.log', 'a') as f:
            f.write(traceback.format_exc() + '\n')
        return {"farmer": ["PASS"], "hands": [], "market": []}
