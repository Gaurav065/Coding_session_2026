"""Fast Discrete-Event Simulation Engine for Kaggriculture - Project Maestro

Bit-for-bit exact pure-Python game engine replicating `kaggriculture.py`.
"""

import math
import random
from typing import Dict, List, Tuple, Optional, Any, Callable

BOARD_SIZE = 10
TURNS_PER_DAY = 24
TOTAL_DAYS = 30
EPISODE_STEPS = TURNS_PER_DAY * TOTAL_DAYS - 1  # 719 (matches kaggriculture.py:960 step >= cfg.episodeSteps - 2)
STARTING_MONEY = 3000.0
SHED_CAPACITY = 100
MAX_MARKET_ORDERS_PER_TURN = 10
MAX_SHOP_INSTANCES = 8
WEED_SPAWN_CHANCE = 0.005
FARM_HAND_COST_MULT = 1
PRICE_FLOOR = 1
HINGE_GAIN = 8.0
MARKET_I0 = 10000

SHED_ACCESS_TILES_LIST = [(4, 4), (5, 4), (4, 5), (5, 5)]
SHED_ACCESS_TILES = set(SHED_ACCESS_TILES_LIST)

QUADRANTS = {
    "NW": [(x, y) for y in range(5) for x in range(5)],
    "NE": [(x, y) for y in range(5) for x in range(5, 10)],
    "SW": [(x, y) for y in range(5, 10) for x in range(5)],
    "SE": [(x, y) for y in range(5, 10) for x in range(5, 10)],
}

LAND_ORDER = ["NE", "SW", "SE"]
LAND_PRICES = [1000, 2000, 4000]

CROPS = {
    "WHEAT":      {"seed": 10, "first_yield_day": 2, "max_yield_day": 4, "interval": 0, "max_yield": 6, "ongoing": False},
    "CARROT":     {"seed": 20, "first_yield_day": 2, "max_yield_day": 3, "interval": 0, "max_yield": 4, "ongoing": False},
    "TOMATO":     {"seed": 50, "first_yield_day": 8, "max_yield_day": 8, "interval": 1, "max_yield": 4, "ongoing": True},
    "STRAWBERRY": {"seed": 100, "first_yield_day": 10, "max_yield_day": 10, "interval": 2, "max_yield": 4, "ongoing": True},
    "MELON":      {"seed": 80, "first_yield_day": 10, "max_yield_day": 12, "interval": 0, "max_yield": 6, "ongoing": False},
}

ANIMALS = {
    "GOOSE": {"cost": 300, "structure": "COOP",    "first_yield_day": 4, "interval": 1, "max_held": 4, "product": "EGG"},
    "COW":   {"cost": 400, "structure": "PASTURE", "first_yield_day": 8, "interval": 2, "max_held": 6, "product": "MILK"},
    "SHEEP": {"cost": 500, "structure": "PASTURE", "first_yield_day": 6, "interval": 3, "max_held": 6, "product": "WOOL"},
}

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]

MARKET_PARAMS = {
    "WHEAT":      {"base":  25, "I0": MARKET_I0, "T": 400, "below_func": "sqrt",   "below_target": 0.80, "above_func": "log",    "above_target": 0.20},
    "CARROT":     {"base":  35, "I0": MARKET_I0, "T": 450, "below_func": "hinge",  "below_target": 1.00, "above_func": "sqrt",   "above_target": 0.70},
    "TOMATO":     {"base":  60, "I0": MARKET_I0, "T": 200, "below_func": "hinge",  "below_target": 0.40, "above_func": "sqrt",   "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": MARKET_I0, "T": 100, "below_func": "sqrt",   "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON":      {"base": 250, "I0": MARKET_I0, "T": 300, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.60},
    "EGG":        {"base":  50, "I0": MARKET_I0, "T": 332, "below_func": "hinge",  "below_target": 0.40, "above_func": "log",    "above_target": 0.20},
    "MILK":       {"base": 160, "I0": MARKET_I0, "T": 122, "below_func": "sqrt",   "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL":       {"base": 200, "I0": MARKET_I0, "T": 105, "below_func": "log",    "below_target": 0.20, "above_func": "sq",     "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": MARKET_I0, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
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

SHOP_NAMES = sorted(SHOPS.keys())
TOWN_CENTER_PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]

def _shape(func, x, T=None):
    x = max(0.0, x)
    if func == "linear": return x
    if func == "sq":     return x * x
    if func == "sqrt":   return math.sqrt(x)
    if func == "log":    return math.log(1.0 + x)
    if func == "log10":  return math.log10(1.0 + x)
    if func == "hinge":
        if not T or T <= 0:
            return x
        u = x / T
        return u + HINGE_GAIN * max(0.0, u - 1.0) ** 2
    return x

def market_price(item, inventory, params=None):
    p = (params or MARKET_PARAMS)[item]
    base = p["base"]
    I0 = p["I0"]
    T = p["T"]
    if inventory < I0:
        f = p["below_func"]
        amp = p["below_target"] * base / _shape(f, T, T)
        price = base + amp * _shape(f, I0 - inventory, T)
    else:
        f = p["above_func"]
        amp = p["above_target"] * base / _shape(f, T, T)
        price = base - amp * _shape(f, inventory - I0, T)
    return max(PRICE_FLOOR, int(round(price)))

def _fib(n: int) -> int:
    a, b = 1, 1
    for _ in range(n):
        a, b = b, a + b
    return a

def _parse_order(order):
    if not isinstance(order, list) or not order:
        return None
    op = order[0]
    if op == "HIRE":
        return {"type": "HIRE"}
    if op == "BUY_LAND":
        return {"type": "BUY_LAND"}
    if op in ("BUY_SEED", "BUY_PRODUCT", "BUY_ANIMAL", "SELL"):
        if len(order) < 3:
            return None
        try:
            n = int(order[2])
        except (TypeError, ValueError):
            return None
        if n <= 0:
            return None
        return {"type": op, "item": order[1], "remaining": n}
    return None

def _spawn_hand_pos(farmer_pos, hands_positions):
    occupants = {tile: 0 for tile in SHED_ACCESS_TILES_LIST}
    all_pos = [tuple(farmer_pos)] + [tuple(p) for p in hands_positions]
    for pos in all_pos:
        if pos in occupants:
            occupants[pos] += 1
    best = sorted(occupants.items(), key=lambda kv: (kv[1], SHED_ACCESS_TILES_LIST.index(kv[0])))
    return list(best[0][0])

def _inv_add(inv: Dict[str, int], item: str, n: int = 1):
    inv[item] = inv.get(item, 0) + n

def _inv_take(inv: Dict[str, int], item: str, n: int = 1) -> bool:
    if inv.get(item, 0) < n:
        return False
    inv[item] -= n
    if inv[item] == 0:
        del inv[item]
    return True


class FastFarm:
    def __init__(self):
        self.money = 3000.0
        self.tiles = [[None for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
        for q in ["NE", "SW", "SE"]:
            for x, y in QUADRANTS[q]:
                self.tiles[y][x] = "LOCKED"

        self.farmer = [4, 4]  # NW shed access default spawn
        self.hands: List[List[int]] = []
        self.unlocked_quadrants = ["NW"]
        self.hires_today = 0
        
        self.shed: Dict[str, int] = {
            "WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0,
            "EGG": 0, "MILK": 0, "WOOL": 0, "FERTILIZER": 0,
            "GOOSE": 0, "COW": 0, "SHEEP": 0,
        }
        self.seeds: Dict[str, int] = {
            "WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0,
        }
        self.inventories: List[Dict[str, int]] = [{}]


class FastGame:
    def __init__(self, seed: Optional[int] = 0):
        self.seed = seed or 0
        self.step = 0
        self.day = 0
        self.hour = 0
        self.farms = [FastFarm(), FastFarm()]
        self.market_inv = {k: MARKET_PARAMS[k]["I0"] for k in MARKET_PARAMS}
        self.unlocked_shops: List[str] = []

    @property
    def done(self) -> bool:
        return self.step >= EPISODE_STEPS

    def get_observation(self, player_idx: int) -> Dict[str, Any]:
        prices = {k: market_price(k, self.market_inv[k]) for k in MARKET_PARAMS}
        
        farms_obs = []
        for f in self.farms:
            farms_obs.append({
                "money": f.money,
                "tiles": [[(dict(t) if isinstance(t, dict) else t) for t in row] for row in f.tiles],
                "farmer": list(f.farmer),
                "hands": [list(h) for h in f.hands],
                "unlocked_quadrants": list(f.unlocked_quadrants),
                "hires_today": f.hires_today,
            })

        my_farm = self.farms[player_idx]
        private_obs = {
            "shed": dict(my_farm.shed),
            "seeds": dict(my_farm.seeds),
            "inventories": [dict(inv) for inv in my_farm.inventories],
        }

        return {
            "player": player_idx,
            "step": self.step,
            "day": self.day,
            "hour": self.hour,
            "farms": farms_obs,
            "private": private_obs,
            "market": {
                "inventory": dict(self.market_inv),
                "prices": prices,
            },
            "town": {
                "unlocked_shops": list(self.unlocked_shops),
            },
        }

    def execute_all_market_orders(self, p0_orders: List[List[Any]], p1_orders: List[List[Any]]):
        p0_parsed = [_parse_order(o) for o in p0_orders[:MAX_MARKET_ORDERS_PER_TURN]]
        p1_parsed = [_parse_order(o) for o in p1_orders[:MAX_MARKET_ORDERS_PER_TURN]]
        max_len = max(len(p0_parsed), len(p1_parsed))

        for order_idx in range(max_len):
            order_states = [
                p0_parsed[order_idx] if order_idx < len(p0_parsed) else None,
                p1_parsed[order_idx] if order_idx < len(p1_parsed) else None,
            ]

            # 1. Atomic Orders (HIRE, BUY_LAND)
            for p_id, ostate in enumerate(order_states):
                if ostate is None: continue
                op = ostate["type"]
                farm = self.farms[p_id]
                if op == "HIRE":
                    cost = _fib(farm.hires_today)
                    if farm.money >= cost:
                        farm.money -= cost
                        spawn_pos = _spawn_hand_pos(farm.farmer, farm.hands)
                        farm.hires_today += 1
                        farm.hands.append(spawn_pos)
                        farm.inventories.append({})
                    order_states[p_id] = None
                elif op == "BUY_LAND":
                    n_extra = len(farm.unlocked_quadrants) - 1
                    if n_extra < len(LAND_ORDER):
                        cost = LAND_PRICES[n_extra]
                        if farm.money >= cost:
                            farm.money -= cost
                            next_q = LAND_ORDER[n_extra]
                            farm.unlocked_quadrants.append(next_q)
                            for x, y in QUADRANTS[next_q]:
                                farm.tiles[y][x] = None
                    order_states[p_id] = None

            # 2. Lockstep unit-by-unit loop
            while True:
                quoted = [None, None]
                for p_id, ostate in enumerate(order_states):
                    if ostate is None or ostate["remaining"] <= 0: continue
                    op = ostate["type"]
                    item = ostate["item"]
                    if op == "SELL" and item in PRODUCTS:
                        quoted[p_id] = ("SELL", item, market_price(item, self.market_inv[item]), ostate)
                    elif op == "BUY_PRODUCT" and item in ("WHEAT", "FERTILIZER"):
                        quoted[p_id] = ("BUY_PRODUCT", item, market_price(item, self.market_inv[item] - 1), ostate)
                    elif op == "BUY_SEED" and item in CROPS:
                        quoted[p_id] = ("BUY_SEED", item, CROPS[item]["seed"], ostate)
                    elif op == "BUY_ANIMAL" and item in ANIMALS:
                        quoted[p_id] = ("BUY_ANIMAL", item, ANIMALS[item]["cost"], ostate)
                    else:
                        order_states[p_id] = None

                if all(q is None for q in quoted):
                    break

                committed_any = False
                for p_id, q in enumerate(quoted):
                    if q is None: continue
                    op, item, price, ostate = q
                    farm = self.farms[p_id]
                    ok = False

                    if op == "SELL":
                        if farm.shed.get(item, 0) > 0:
                            farm.shed[item] -= 1
                            farm.money += price
                            if price > 1:
                                self.market_inv[item] += 1
                            ok = True
                    elif op == "BUY_PRODUCT":
                        if farm.money >= price and sum(farm.shed.values()) < SHED_CAPACITY:
                            farm.money -= price
                            farm.shed[item] = farm.shed.get(item, 0) + 1
                            self.market_inv[item] -= 1
                            ok = True
                    elif op == "BUY_SEED":
                        if farm.money >= price:
                            farm.money -= price
                            farm.seeds[item] = farm.seeds.get(item, 0) + 1
                            ok = True
                    elif op == "BUY_ANIMAL":
                        if farm.money >= price and sum(farm.shed.values()) < SHED_CAPACITY:
                            farm.money -= price
                            farm.shed[item] = farm.shed.get(item, 0) + 1
                            ok = True

                    if ok:
                        ostate["remaining"] -= 1
                        committed_any = True
                    else:
                        order_states[p_id] = None

                if not committed_any:
                    break

    def execute_unit_actions(self, p_idx: int, farmer_action: List[Any], hands_actions: List[List[Any]]):
        farm = self.farms[p_idx]
        all_units = [farm.farmer] + farm.hands
        all_actions = [farmer_action] + hands_actions

        # Atomic PLANT validation: if total PLANT requests for a crop this turn
        # exceed available seeds, drop ALL PLANT requests for that crop.
        plant_demand = {}
        for a in all_actions:
            if isinstance(a, list) and len(a) >= 2 and a[0] == "PLANT":
                plant_demand[a[1]] = plant_demand.get(a[1], 0) + 1
        blocked = {crop for crop, n in plant_demand.items() if n > farm.seeds.get(crop, 0)}

        for u_idx, pos in enumerate(all_units):
            if u_idx >= len(farm.inventories): break
            inv = farm.inventories[u_idx]
            act = all_actions[u_idx] if u_idx < len(all_actions) else ["PASS"]
            if not act: act = ["PASS"]
            if isinstance(act, list) and len(act) >= 2 and act[0] == "PLANT" and act[1] in blocked:
                act = ["PASS"]
            op = act[0]
            fx, fy = pos[0], pos[1]

            # 1. Movement
            if op == "NORTH":
                if pos[1] > 0: pos[1] -= 1
                continue
            elif op == "SOUTH":
                if pos[1] < BOARD_SIZE - 1: pos[1] += 1
                continue
            elif op == "EAST":
                if pos[0] < BOARD_SIZE - 1: pos[0] += 1
                continue
            elif op == "WEST":
                if pos[0] > 0: pos[0] -= 1
                continue

            tile = farm.tiles[fy][fx]

            # 2. Shed Ops
            if op == "DROP":
                if (fx, fy) in SHED_ACCESS_TILES:
                    for item, n in list(inv.items()):
                        if n <= 0:
                            del inv[item]
                            continue
                        room = max(0, SHED_CAPACITY - sum(farm.shed.values()))
                        take = min(n, room)
                        if take > 0:
                            farm.shed[item] = farm.shed.get(item, 0) + take
                        del inv[item]
                continue

            if op == "PICKUP":
                if (fx, fy) in SHED_ACCESS_TILES and len(act) >= 2:
                    item = act[1]
                    n = int(act[2]) if len(act) >= 3 else 1
                    if n > 0:
                        avail = farm.shed.get(item, 0)
                        take = min(n, avail)
                        if take > 0:
                            farm.shed[item] -= take
                            _inv_add(inv, item, take)
                continue

            if op == "PLACE":
                if len(act) >= 2:
                    item = act[1]
                    if (
                        item in ANIMALS
                        and isinstance(tile, dict)
                        and tile.get("kind") == ANIMALS[item]["structure"]
                        and "animal" not in tile
                    ):
                        if _inv_take(inv, item, 1):
                            farm.tiles[fy][fx] = {
                                "kind": ANIMALS[item]["structure"],
                                "animal": item,
                                "placed_day": self.day,
                                "yield_units": 0,
                                "consecutive_unfed": 0,
                                "fed_today": False,
                                "cared_today": False,
                                "fertilizer_available": False,
                                "pending_care_bonus": 0,
                            }
                        continue
                    if (fx, fy) in SHED_ACCESS_TILES:
                        n = int(act[2]) if len(act) >= 3 else 1
                        if n > 0:
                            n = min(n, inv.get(item, 0))
                            if n > 0:
                                current = sum(farm.shed.values())
                                room = max(0, SHED_CAPACITY - current)
                                n = min(n, room)
                                if n > 0:
                                    inv[item] -= n
                                    if inv[item] == 0:
                                        del inv[item]
                                    farm.shed[item] = farm.shed.get(item, 0) + n
                continue

            if tile == "LOCKED":
                continue

            # 3. Terrain / Tile Ops
            if op == "PLANT":
                if len(act) >= 2:
                    crop = act[1]
                    if crop in CROPS and tile is None and farm.seeds.get(crop, 0) > 0:
                        farm.seeds[crop] -= 1
                        cd = CROPS[crop]
                        farm.tiles[fy][fx] = {
                            "kind": "PLANT",
                            "crop": crop,
                            "planted_day": self.day,
                            "watered_today": False,
                            "consecutive_unwatered": 1,
                            "yield_units": 0 if cd["ongoing"] else 1,
                            "fertilized_until_day": -1,
                            "max_lifespan_step": (-1 if cd["ongoing"] else (self.day + cd["max_yield_day"] + 1) * TURNS_PER_DAY),
                        }
                continue

            if op == "WATER":
                if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    if not tile["watered_today"]:
                        tile["watered_today"] = True
                        cd = CROPS[tile["crop"]]
                        if not cd["ongoing"]:
                            age_days = self.day - tile["planted_day"]
                            window_start = (cd["max_yield_day"] + 1) // 2
                            if window_start <= age_days <= cd["max_yield_day"]:
                                bonus = 2 if tile.get("fertilized_until_day", -1) >= self.day else 1
                                tile["yield_units"] = min(cd["max_yield"], tile["yield_units"] + bonus)
                continue

            if op == "HARVEST":
                if isinstance(tile, dict):
                    if tile.get("kind") == "PLANT":
                        cd = CROPS[tile["crop"]]
                        if self.day - tile["planted_day"] >= cd["first_yield_day"]:
                            units = tile.get("yield_units", 0)
                            if units > 0:
                                tile["yield_units"] = 0
                                _inv_add(inv, tile["crop"], units)
                                if not cd["ongoing"]:
                                    farm.tiles[fy][fx] = None
                    elif "animal" in tile:
                        units = tile.get("yield_units", 0)
                        if units > 0:
                            tile["yield_units"] = 0
                            _inv_add(inv, ANIMALS[tile["animal"]]["product"], units)
                continue

            if op == "FERTILIZE":
                if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    if _inv_take(inv, "FERTILIZER", 1):
                        tile["fertilized_until_day"] = max(tile.get("fertilized_until_day", -1), self.day + 2)
                continue

            if op == "DIG":
                if tile is not None:
                    if not (isinstance(tile, dict) and "animal" in tile):
                        farm.tiles[fy][fx] = None
                continue

            if op == "BUILD_COOP":
                if tile is None:
                    farm.tiles[fy][fx] = {"kind": "COOP"}
                continue

            if op == "BUILD_PASTURE":
                if tile is None:
                    farm.tiles[fy][fx] = {"kind": "PASTURE"}
                continue

            if op == "FEED":
                if isinstance(tile, dict) and "animal" in tile:
                    if not tile.get("fed_today", False):
                        if _inv_take(inv, "WHEAT", 1):
                            tile["fed_today"] = True
                continue

            if op == "COLLECT_FERTILIZER":
                if isinstance(tile, dict) and "animal" in tile:
                    if tile.get("fertilizer_available", False):
                        tile["fertilizer_available"] = False
                        _inv_add(inv, "FERTILIZER", 1)
                continue

            if op == "CARE":
                if isinstance(tile, dict) and "animal" in tile:
                    if not tile.get("cared_today", False):
                        tile["cared_today"] = True
                continue

    def step_game(self, p0_action: Dict[str, Any], p1_action: Dict[str, Any]):
        if self.done:
            return

        # 1. Unit Actions FIRST
        self.execute_unit_actions(0, p0_action.get("farmer", ["PASS"]), p0_action.get("hands", []))
        self.execute_unit_actions(1, p1_action.get("farmer", ["PASS"]), p1_action.get("hands", []))

        # 2. Market Orders SECOND
        self.execute_all_market_orders(p0_action.get("market", []), p1_action.get("market", []))

        # 3. Town Shops Drain (every 4 turns) THIRD
        if self.step % 4 == 0 and self.unlocked_shops:
            for shop_name in self.unlocked_shops:
                products = SHOPS[shop_name]
                multiplier = 2 if len(products) == 1 else 1
                for item in products:
                    self.market_inv[item] -= multiplier

        # 4. Town Center Drain (every 24 turns) FOURTH
        if self.step % 24 == 0:
            for item in TOWN_CENTER_PRODUCTS:
                self.market_inv[item] -= 1

        # 5. Plant decay at step
        for farm in self.farms:
            for y in range(BOARD_SIZE):
                for x in range(BOARD_SIZE):
                    tile = farm.tiles[y][x]
                    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                        mls = tile.get("max_lifespan_step", -1)
                        if mls >= 0 and self.step >= mls:
                            if (self.step - mls) % 2 == 0:
                                tile["yield_units"] -= 1
                                if tile["yield_units"] <= 0:
                                    farm.tiles[y][x] = {"kind": "WEED"}

        # Step increment
        self.step += 1
        self.hour = self.step % TURNS_PER_DAY
        self.day = self.step // TURNS_PER_DAY

        # End of Day Refresh
        if self.hour == 0 and self.step > 0 and self.step < EPISODE_STEPS:
            day_just_ended = self.day - 1
            rng = random.Random((self.seed * 1_000_003) ^ day_just_ended)

            # Refresh each farm
            for farm in self.farms:
                # 1. Plants
                next_day = self.day
                for y in range(BOARD_SIZE):
                    for x in range(BOARD_SIZE):
                        tile = farm.tiles[y][x]
                        if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                            was_watered = tile["watered_today"]
                            if was_watered:
                                tile["consecutive_unwatered"] = 0
                            else:
                                tile["consecutive_unwatered"] += 1
                            tile["watered_today"] = False
                            if tile["consecutive_unwatered"] >= 2:
                                farm.tiles[y][x] = {"kind": "WEED"}
                                continue
                            cd = CROPS[tile["crop"]]
                            if not cd["ongoing"]:
                                continue

                            days_since_first = next_day - tile["planted_day"] - cd["first_yield_day"]
                            if days_since_first < 0:
                                continue
                            interval = cd["interval"]
                            if days_since_first % interval != 0:
                                continue
                            production_count = days_since_first // interval + 1
                            if production_count > cd["max_yield"]:
                                continue
                            fertilized = was_watered and tile.get("fertilized_until_day", -1) >= day_just_ended
                            tile["yield_units"] = min(cd["max_yield"], tile["yield_units"] + (2 if fertilized else 1))
                            if production_count == cd["max_yield"]:
                                tile["max_lifespan_step"] = (next_day + 1) * TURNS_PER_DAY

                        # 2. Animals
                        elif isinstance(tile, dict) and "animal" in tile:
                            if tile["fed_today"]:
                                tile["consecutive_unfed"] = 0
                            else:
                                tile["consecutive_unfed"] += 1
                            if tile["consecutive_unfed"] >= 2:
                                farm.tiles[y][x] = {"kind": ANIMALS[tile["animal"]]["structure"]}
                                continue
                            a = ANIMALS[tile["animal"]]
                            days_since_first = next_day - tile["placed_day"] - a["first_yield_day"]
                            if days_since_first >= 0 and days_since_first % a["interval"] == 0:
                                base = 1
                                bonus = tile.pop("pending_care_bonus", 0) if tile["fed_today"] else 0
                                tile["yield_units"] = min(a["max_held"], tile["yield_units"] + base + bonus)
                                tile["pending_care_bonus"] = 0
                            if tile["cared_today"] and tile["fed_today"]:
                                tile["pending_care_bonus"] = tile.get("pending_care_bonus", 0) + 1
                            tile["fertilizer_available"] = True
                            tile["fed_today"] = False
                            tile["cared_today"] = False

                # 3. Weeds
                for y in range(BOARD_SIZE):
                    for x in range(BOARD_SIZE):
                        if farm.tiles[y][x] is None and rng.random() < WEED_SPAWN_CHANCE:
                            farm.tiles[y][x] = {"kind": "WEED"}

                # 4. Drop inventories to shed
                for inv in farm.inventories:
                    for item, n in list(inv.items()):
                        if n <= 0:
                            del inv[item]
                            continue
                        current = sum(v for k, v in farm.shed.items())
                        room = max(0, SHED_CAPACITY - current)
                        take = min(n, room)
                        if take > 0:
                            farm.shed[item] = farm.shed.get(item, 0) + take
                        del inv[item]

                # 5. Reset units
                farm.farmer = [4, 4]
                farm.hands = []
                farm.hires_today = 0
                farm.inventories = [{}]

            # 6. Unlock new shop every 3 days
            next_day = self.day
            if next_day > 0 and next_day % 3 == 0:
                if len(self.unlocked_shops) < MAX_SHOP_INSTANCES:
                    self.unlocked_shops.append(rng.choice(SHOP_NAMES))


def simulate_match(agent_0_factory: Callable, agent_1_factory: Callable, seed: int = 42) -> Tuple[float, float]:
    game = FastGame(seed=seed)
    agent_0 = agent_0_factory()
    agent_1 = agent_1_factory()

    while not game.done:
        obs_0 = game.get_observation(0)
        obs_1 = game.get_observation(1)

        act_0 = agent_0(obs_0)
        act_1 = agent_1(obs_1)

        game.step_game(act_0, act_1)

    return float(game.farms[0].money), float(game.farms[1].money)
