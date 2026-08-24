"""Master Scaled Crew & 850+ Wheat Engine Agent - Project Maestro

Throughput & Capital Optimization:
1. Dynamic Seed Order Sizing:
   - Strawberry: `buy_n = min(16 - planted, int((money - 200) // 300))`, smooth accumulation across Days 3-6 up to 16 full ongoing plants.
   - Melon: `buy_n = min(6 - planted, int((money - 200) // 100))`, 6 plants on Day 8.
   - Wheat: continuous bulk replenishment (40 seeds whenever bank >= $400).
2. 16 Full Ongoing Strawberries:
   - Produces 300+ strawberries per player across Days 7-30.
3. 33 Scaled Wheat Plots:
   - 18 SW + 8 NE + 7 NW generating 850+ wheat sold.
4. Immediate Same-Tile Water-After-Plant.
5. 13-Worker Labor Allocation:
   - Units 0-3: Animal Sweep & Care Lock.
   - Units 4-5: NW Wheat Engine.
   - Units 6-8: NE Strawberry & Wheat.
   - Units 9-12: SW Wheat & Melon.
"""

from typing import Dict, List, Tuple, Optional, Any, Set

MOVES = {
    (0, -1): "NORTH",
    (0, 1):  "SOUTH",
    (1, 0):  "EAST",
    (-1, 0): "WEST",
}

SHED_ACCESS_TILES_LIST = [(4, 4), (5, 4), (4, 5), (5, 5)]
SHED_ACCESS_TILES = set(SHED_ACCESS_TILES_LIST)

COW_PASTURES = [
    (4, 3), (3, 4),
    (4, 2), (3, 3), (2, 4),
    (4, 1), (3, 2), (2, 3), (1, 4),
    (4, 0)
]

GOOSE_COOPS = [
    (3, 1), (2, 2), (1, 3), (0, 4)
]

SHEEP_PASTURES = [
    (3, 1), (2, 2), (1, 3), (0, 4)
]

NW_WHEAT = [
    (0, 0), (1, 0), (2, 0), (3, 0),
    (0, 1), (1, 1), (2, 1),
    (0, 2), (1, 2),
    (0, 3)
]

NE_STRAWBERRY = [
    (5, 0), (6, 0), (7, 0), (8, 0), (9, 0),
    (5, 1), (6, 1), (7, 1), (8, 1), (9, 1),
    (5, 2), (6, 2), (7, 2), (8, 2), (9, 2),
    (5, 3)
]

NE_WHEAT = [
    (6, 3), (7, 3), (8, 3), (9, 3),
    (6, 4), (7, 4), (8, 4), (9, 4)
]

SW_MELON = [
    (0, 6), (1, 6), (2, 6),
    (0, 7), (1, 7), (2, 7)
]

SW_WHEAT = [
    (0, 5), (1, 5), (2, 5), (3, 5),
    (0, 8), (1, 8), (2, 8), (3, 8),
    (0, 9), (1, 9), (2, 9), (3, 9),
    (4, 6), (4, 7), (4, 8), (4, 9),
    (3, 6), (3, 7)
]

# Verified against kaggriculture.py MARKET_PARAMS (engine:41-51). The previous
# table here was fabricated (wrong on 7/8 products) and was driving the sell
# threshold below, so the agent was dumping steep-glut-curve products (MILK,
# WOOL, MELON, STRAWBERRY -- above_target 1.6-3.6) into a shared, contention-
# sensitive market far too early, crashing its own realized price. WHEAT and
# EGG (above_target 0.20) barely move under glut and can be sold freely.
BASE_PRICES = {
    "WHEAT": 25,
    "CARROT": 35,
    "TOMATO": 60,
    "STRAWBERRY": 120,
    "MELON": 250,
    "EGG": 50,
    "MILK": 160,
    "WOOL": 200,
    "FERTILIZER": 100,
}

# above_target from MARKET_PARAMS: how punishing oversupply is for this
# product. FERTILIZER has zero drain of any kind -- no shop demands it and it
# is explicitly excluded from TOWN_CENTER_PRODUCTS -- so its market inventory
# only ever rises (both players sell into it) and price never recovers.
# Trickling it just delays into a strictly worse price later; sell it as fast
# as possible instead. Every other product gets some relief from shop and/or
# town-center drain, so trickling to let price recover is worthwhile there.
ABOVE_TARGET = {
    "WHEAT": 0.20, "EGG": 0.20,
    "TOMATO": 0.60, "CARROT": 0.70, "FERTILIZER": 0.40,
    "STRAWBERRY": 1.60, "MILK": 1.60, "WOOL": 3.20, "MELON": 3.60,
}
GLUT_RESISTANT = {"WHEAT", "EGG"}
GLUT_PRONE = {"STRAWBERRY", "MILK", "WOOL", "MELON"}

def get_step_towards(curr: Tuple[int, int], target: Tuple[int, int]) -> str:
    cx, cy = curr
    tx, ty = target
    if cx == tx and cy == ty:
        return "PASS"

    dx = tx - cx
    dy = ty - cy

    if abs(dx) >= abs(dy) and dx != 0:
        step = (1 if dx > 0 else -1, 0)
        return MOVES.get(step, "PASS")
    elif dy != 0:
        step = (0, 1 if dy > 0 else -1)
        return MOVES.get(step, "PASS")
    return "PASS"

def dist(p1: Tuple[int, int], p2: Tuple[int, int]) -> int:
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])


# Empirical Causal Shop Values & Displacement Cost Model (NOTES.md §2n)
# Derived under integrated dispatcher (N=100 seeds, 1,100 full games)
GAMMA_INTEGRATED = {
    "SMOOTHIE_SHOP":  18469.37,
    "ICE_CREAM_SHOP": 17190.58,
    "PIZZA_SHOP":     14724.84,
    "FARMERS_MARKET":  4047.12,
    "BRUNCH_SPOT":     2267.06,
    "PET_CAFE":         979.34,
    "YARN_STORE":     -1870.32,
    "BAKERY":             0.00,
}
K_COST_CORRECTED = 208.74  # Derived empirical opportunity cost per early NW wheat tile ($208.74/tile)
STEERING_GAIN_THRESHOLD = 1000.0  # Gain threshold ($1,000) required to clear steering gate


def compute_optimal_steering_kw(seed: int) -> int:
    """Compute optimal Day 0-2 NW wheat tile count (0-10) to steer Day 3 shop unlock.
    
    Formula: Gain(S, Kw) = (gamma_S - gamma_S_0) - $208.74 * (10 - Kw)
    Steers if Gain > $1,000; defaults to Kw=10 (unsteered) otherwise.
    """
    from project_maestro.engine.fast_engine import FastGame
    
    # 1. Determine natural baseline shop S_0 (Kw=10)
    game_nat = FastGame(seed=seed)
    p0_n = MaestroFullPortfolioAgent(kw_early=10)
    p1_n = MaestroFullPortfolioAgent(kw_early=10)
    while game_nat.day < 3:
        p0_n(game_nat.get_observation(0))
        p1_n(game_nat.get_observation(1))
        game_nat.step_game(p0_n(game_nat.get_observation(0)), p1_n(game_nat.get_observation(1)))
    natural_shop = game_nat.unlocked_shops[0] if game_nat.unlocked_shops else "BAKERY"

    # 2. Sweep Kw in 0..10 to map achievable shops
    achievable = {}
    for kw in range(11):
        g = FastGame(seed=seed)
        p0 = MaestroFullPortfolioAgent(kw_early=kw)
        p1 = MaestroFullPortfolioAgent(kw_early=10)
        while g.day < 3:
            act0 = p0(g.get_observation(0))
            act1 = p1(g.get_observation(1))
            g.step_game(act0, act1)
        if g.unlocked_shops:
            s = g.unlocked_shops[0]
            if s not in achievable:
                achievable[s] = kw

    # 3. Value-gated selection
    best_shop = natural_shop
    best_kw = 10
    best_gain = 0.0

    for shop, kw in achievable.items():
        gain = (GAMMA_INTEGRATED[shop] - GAMMA_INTEGRATED[natural_shop]) - K_COST_CORRECTED * (10 - kw)
        if gain > best_gain:
            best_gain = gain
            best_shop = shop
            best_kw = kw

    return best_kw if best_gain > STEERING_GAIN_THRESHOLD else 10


DEFAULT_PARAMS = {
    "cow_cap_low": 6,       # cap when milk_shop_count<=1 (day>=15, downward-only, see 2b/2d)
    "cow_cap_base": 10,
    "sheep_cap": 4,
    "goose_cap": 4,
    "melon_seed_target": 6,
    "strawberry_target": 16,
    "crew_late": 10,        # target_crew once SW is unlocked (capped at 10 to match optimal single-turn HIRE ceiling)
    "crew_mid": 9,          # target_crew day>=8, SW not yet unlocked
}


class MaestroFullPortfolioAgent:
    def __init__(self, params=None, kw_early: Optional[int] = None, seed: Optional[int] = None):
        self.params = {**DEFAULT_PARAMS, **(params or {})}
        self.seed = seed
        self.kw_early = kw_early
        self._planned_steering = (kw_early is not None)
        self.cow_pastures = list(COW_PASTURES)
        self.goose_coops = list(GOOSE_COOPS)
        self.sheep_pastures = list(SHEEP_PASTURES)
        self.nw_wheat = list(NW_WHEAT[:kw_early]) if kw_early is not None else list(NW_WHEAT)
        self.ne_strawberry = list(NE_STRAWBERRY)
        self.ne_wheat = list(NE_WHEAT)
        self.sw_melon = list(SW_MELON)
        self.sw_wheat = list(SW_WHEAT)

    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        day = obs["day"]
        hour = obs["hour"]
        money = me["money"]
        unlocked_quads = set(me.get("unlocked_quadrants", []))
        market_prices = obs.get("market", {}).get("prices", {})
        unlocked_shops = obs.get("town", {}).get("unlocked_shops", [])
        has_yarn_store = ("YARN_STORE" in unlocked_shops)

        # Plan / Apply Day 0-2 Value-Gated Shop Steering
        if not self._planned_steering and day == 0:
            if self.seed is None and "seed" in obs:
                self.seed = obs["seed"]
            if self.seed is not None:
                self.kw_early = compute_optimal_steering_kw(self.seed)
            else:
                self.kw_early = 10
            self._planned_steering = True

        if day < 3:
            kw = self.kw_early if self.kw_early is not None else 10
            self.nw_wheat = list(NW_WHEAT[:kw])
        else:
            self.nw_wheat = list(NW_WHEAT)
        # Downward-only: a fast-engine sweep (60 seeds) showed milk_shop_count
        # <=1 is a real disaster zone (~$29-31k avg, vs $61-81k at count>=4),
        # ~15-18% of games. An earlier attempt to also scale UP to 14 cows
        # when demand was high regressed badly (-4.8%) via mutual escalation
        # -- both players scale together and flood the shared market harder.
        # Scaling DOWN has no such trap: cutting your own bad-bet exposure
        # doesn't race the opponent into anything. Never scale above the
        # baseline 10.
        MILK_SHOPS = {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}
        milk_shop_count = sum(1 for s in unlocked_shops if s in MILK_SHOPS)

        market_orders = []

        # Dynamic Crew Sizing: Scale down on season finale (Day 29) where
        # watering and planting are inactive, saving wages while retaining
        # full harvesting and shed dump throughput.
        if day >= 29:
            target_crew = 7
        elif day < 3:
            target_crew = 6
        elif day < 8:
            target_crew = 8
        elif "SW" in unlocked_quads:
            target_crew = self.params["crew_late"]
        else:
            target_crew = self.params["crew_mid"]

        placed_animals = []
        for py in range(5):
            for px in range(5):
                t = me["tiles"][py][px]
                if isinstance(t, dict) and ("animal" in t):
                    placed_animals.append((px, py, t["animal"]))

        placed_c = sum(1 for _, _, a in placed_animals if a == "COW")
        placed_g = sum(1 for _, _, a in placed_animals if a == "GOOSE")
        placed_s = sum(1 for _, _, a in placed_animals if a == "SHEEP")

        shed = private.get("shed", {})
        shed_total_items = sum(shed.values())
        shed_c = shed.get("COW", 0)
        shed_g = shed.get("GOOSE", 0)
        shed_s = shed.get("SHEEP", 0)
        carried_c = sum(inv.get("COW", 0) for inv in private.get("inventories", []))
        carried_g = sum(inv.get("GOOSE", 0) for inv in private.get("inventories", []))
        carried_s = sum(inv.get("SHEEP", 0) for inv in private.get("inventories", []))

        total_c = placed_c + shed_c + carried_c
        total_g = placed_g + shed_g + carried_g
        total_s = placed_s + shed_s + carried_s
        shed_wheat = shed.get("WHEAT", 0)

        # 1. Market Operations
        if hour == 0:
            current_hands = len(me.get("hands", []))
            needed_hires = max(0, target_crew - current_hands)
            for _ in range(needed_hires):
                market_orders.append(["HIRE"])

            # Day 0 Opening: 4 Cows + 1 Sheep + 10 Wheat Seeds + 10 Feed
            if day == 0:
                market_orders.append(["BUY_SEED", "WHEAT", 10])
                market_orders.append(["BUY_PRODUCT", "WHEAT", 10])
                market_orders.append(["BUY_ANIMAL", "COW", 4])
                market_orders.append(["BUY_ANIMAL", "SHEEP", 1])

        # Emergency Feed Guard
        if day < 29 and shed_wheat == 0 and money >= 120:
            if len(market_orders) < 8:
                market_orders.append(["BUY_PRODUCT", "WHEAT", 6])

        # Expansion Pipeline: Smooth Capital Batching
        if len(market_orders) < 8:
            # 1. Land Unlock Priority
            if "NE" not in unlocked_quads and money >= 1000:
                market_orders.append(["BUY_LAND"])
            elif "NE" in unlocked_quads and "SW" not in unlocked_quads and money >= 2000 and day >= 6:
                market_orders.append(["BUY_LAND"])

            # 2. Strawberry Seeds: Smooth Batched Purchases (up to 16 total seeds/plants)
            if "NE" in unlocked_quads and day < 20:
                strawberry_plants = 0
                for sx, sy in self.ne_strawberry:
                    t = me["tiles"][sy][sx]
                    if isinstance(t, dict) and t.get("kind") == "PLANT" and t.get("crop") == "STRAWBERRY":
                        strawberry_plants += 1
                straw_needed = max(0, self.params["strawberry_target"] - strawberry_plants
                                    - private["seeds"].get("STRAWBERRY", 0))
                if straw_needed > 0 and money >= 300:
                    buy_straw = min(straw_needed, int((money - 100) // 300))
                    if buy_straw > 0:
                        market_orders.append(["BUY_SEED", "STRAWBERRY", min(4, buy_straw)])

            # 3. Melon Seeds
            melon_target = self.params["melon_seed_target"]
            if "SW" in unlocked_quads and private["seeds"].get("MELON", 0) < melon_target and money >= 300 and day < 16:
                market_orders.append(["BUY_SEED", "MELON", melon_target])

            # 4. Wheat Seeds (Continuous Supply)
            if private["seeds"].get("WHEAT", 0) < 40 and money >= 300 and day < 28:
                market_orders.append(["BUY_SEED", "WHEAT", 40])

            # 5. Carrot Replanting Pipeline (Days 18-27)
            if day >= 18 and day < 27 and private["seeds"].get("CARROT", 0) < 16 and money >= 350:
                market_orders.append(["BUY_SEED", "CARROT", 16])

            # 6. Additive Animals only after SW land is secured
            allow_animal_expansion = ("SW" in unlocked_quads or day >= 10)
            if allow_animal_expansion:
                # NOTE: previously gated on "not has_yarn_store", which is a
                # wool signal with no bearing on eggs -- looked like a
                # copy-paste leftover from the sheep condition below. Removed;
                # geese are additive to the cow/sheep core and unconditional.
                goose_cap = self.params["goose_cap"]
                if total_g < goose_cap and money >= 600 and shed_total_items <= 90 and day < 16:
                    buy_g = min(goose_cap - total_g, int((money - 300) // 300))
                    if buy_g > 0:
                        market_orders.append(["BUY_ANIMAL", "GOOSE", min(2, buy_g)])

                cow_cap = (self.params["cow_cap_low"] if (day >= 15 and milk_shop_count <= 1)
                           else self.params["cow_cap_base"])
                if total_c < cow_cap and money >= 700 and shed_total_items <= 90 and day < 18:
                    buy_c = min(cow_cap - total_c, int((money - 300) // 400))
                    if buy_c > 0:
                        market_orders.append(["BUY_ANIMAL", "COW", min(2, buy_c)])

                else:
                    sheep_cap = self.params["sheep_cap"]
                    if has_yarn_store and total_s < sheep_cap and money >= 800 and shed_total_items <= 90 and day < 20:
                        buy_s = min(sheep_cap - total_s, int((money - 300) // 500))
                        if buy_s > 0:
                            market_orders.append(["BUY_ANIMAL", "SHEEP", min(2, buy_s)])

        # 2. Adaptive AMM Selling -- curve-aware, using verified real base
        # prices and above_target (see ABOVE_TARGET comment above).
        shed_near_overflow = shed_total_items >= 85  # cap is 100, combined, silent discard on overflow
        for prod in ["EGG", "MILK", "WOOL", "STRAWBERRY", "MELON", "FERTILIZER", "CARROT", "TOMATO"]:
            qty = shed.get(prod, 0)
            if qty <= 0:
                continue
            base_price = BASE_PRICES.get(prod, 10)
            cur_price = market_prices.get(prod, base_price)
            price_ratio = cur_price / base_price if base_price else 1.0

            if day >= 28:
                # Endgame: no days left for price to recover. Confirmed via
                # instrumentation that the trickle throttle below was leaving
                # large unsold balances at game end (e.g. 60 MILK, ~$9.6k,
                # trapped on seed 20) -- any nonzero price beats zero.
                sell_qty = qty
            elif prod == "FERTILIZER":
                # No shop or town-center drain ever removes fertilizer supply
                # (TOWN_CENTER_PRODUCTS excludes it): price can only fall over
                # the season, never recover. Sell all of it immediately.
                sell_qty = qty
            elif prod in GLUT_RESISTANT:
                # above_target 0.20: barely moves even under heavy glut.
                sell_qty = min(qty, 20)
            elif prod in GLUT_PRONE:
                # above_target >= 1.60: each unit sold moves price sharply,
                # and both players dump into the same book (engine:596-597
                # interleaves orders unit by unit). Trickle to preserve
                # realized price and let shop/town-center drain recover it,
                # unless the shed is close to silently discarding overflow.
                if shed_near_overflow:
                    sell_qty = min(qty, 20)
                elif price_ratio >= 0.55:
                    sell_qty = min(qty, 4)
                else:
                    sell_qty = 0
            else:
                # Moderate curve (CARROT, TOMATO): hold for a decent price,
                # otherwise trickle rather than dump.
                if price_ratio >= 0.65:
                    sell_qty = min(qty, 10)
                else:
                    sell_qty = min(qty, 5 if not shed_near_overflow else 20)

            if len(market_orders) < 10 and sell_qty > 0:
                market_orders.append(["SELL", prod, sell_qty])

        # Sell surplus wheat beyond 10 units
        wheat_qty = shed.get("WHEAT", 0)
        if day >= 29 and hour >= 18 and wheat_qty > 0:
            if len(market_orders) < 10:
                market_orders.append(["SELL", "WHEAT", min(50, wheat_qty)])
        elif wheat_qty > 10:
            sell_amt = min(20, wheat_qty - 10)
            if len(market_orders) < 10 and sell_amt > 0:
                market_orders.append(["SELL", "WHEAT", sell_amt])

        # 3. Dynamic Sector Tasks
        nw_wheat_tasks_p1 = []
        nw_wheat_tasks_p2 = []
        for i, (wx, wy) in enumerate(self.nw_wheat):
            t = me["tiles"][wy][wx]
            task_list = nw_wheat_tasks_p1 if i < 5 else nw_wheat_tasks_p2
            if t is None and day < 28:
                task_list.append({"target": (wx, wy), "action": "PLANT_WHEAT", "crop": "WHEAT", "priority": 93})
            elif isinstance(t, dict) and t.get("kind") == "WEED":
                task_list.append({"target": (wx, wy), "action": "DIG", "priority": 30})
            elif isinstance(t, dict) and t.get("kind") == "PLANT":
                if not t.get("watered_today", False):
                    task_list.append({"target": (wx, wy), "action": "WATER", "priority": 95})
                if t.get("yield_units", 0) > 0 and (day - t.get("planted_day", 0)) >= 2:
                    task_list.append({"target": (wx, wy), "action": "HARVEST", "priority": 90})

        ne_tasks = []
        if "NE" in unlocked_quads:
            for sx, sy in self.ne_strawberry:
                t = me["tiles"][sy][sx]
                if t is None:
                    if day < 18:
                        ne_tasks.append({"target": (sx, sy), "action": "PLANT_STRAWBERRY", "crop": "STRAWBERRY", "priority": 95})
                    elif day < 28:
                        ne_tasks.append({"target": (sx, sy), "action": "PLANT_CARROT", "crop": "CARROT", "priority": 95})
                elif isinstance(t, dict) and t.get("kind") == "WEED":
                    ne_tasks.append({"target": (sx, sy), "action": "DIG", "priority": 45})
                elif isinstance(t, dict) and t.get("kind") == "PLANT":
                    crop = t.get("crop")
                    mls = t.get("max_lifespan_step", -1)
                    yields = t.get("yield_units", 0)
                    planted_day = t.get("planted_day", 0)

                    if crop == "STRAWBERRY":
                        if yields > 0:
                            ne_tasks.append({"target": (sx, sy), "action": "HARVEST", "priority": 98})
                        elif mls >= 0:
                            # Expired strawberry plant: dig up so plot can be replanted
                            ne_tasks.append({"target": (sx, sy), "action": "DIG", "priority": 94})
                        elif not t.get("watered_today", False):
                            ne_tasks.append({"target": (sx, sy), "action": "WATER", "priority": 96})
                    elif crop == "CARROT":
                        if yields > 0 and (day - planted_day) >= 2:
                            ne_tasks.append({"target": (sx, sy), "action": "HARVEST", "priority": 98})
                        elif not t.get("watered_today", False):
                            ne_tasks.append({"target": (sx, sy), "action": "WATER", "priority": 96})
                    else:
                        if yields > 0 and (day - planted_day) >= 2:
                            ne_tasks.append({"target": (sx, sy), "action": "HARVEST", "priority": 98})
                        elif not t.get("watered_today", False):
                            ne_tasks.append({"target": (sx, sy), "action": "WATER", "priority": 96})

            for wx, wy in self.ne_wheat:
                t = me["tiles"][wy][wx]
                if t is None and day < 28:
                    ne_tasks.append({"target": (wx, wy), "action": "PLANT_WHEAT", "crop": "WHEAT", "priority": 93})
                elif isinstance(t, dict) and t.get("kind") == "WEED":
                    ne_tasks.append({"target": (wx, wy), "action": "DIG", "priority": 30})
                elif isinstance(t, dict) and t.get("kind") == "PLANT":
                    if not t.get("watered_today", False):
                        ne_tasks.append({"target": (wx, wy), "action": "WATER", "priority": 92})
                    if t.get("yield_units", 0) > 0 and (day - t.get("planted_day", 0)) >= 2:
                        ne_tasks.append({"target": (wx, wy), "action": "HARVEST", "priority": 90})

        sw_tasks = []
        if "SW" in unlocked_quads:
            for mx, my in self.sw_melon:
                t = me["tiles"][my][mx]
                if t is None and day < 16:
                    sw_tasks.append({"target": (mx, my), "action": "PLANT_MELON", "crop": "MELON", "priority": 95})
                elif isinstance(t, dict) and t.get("kind") == "WEED":
                    sw_tasks.append({"target": (mx, my), "action": "DIG", "priority": 45})
                elif isinstance(t, dict) and t.get("kind") == "PLANT":
                    if not t.get("watered_today", False):
                        sw_tasks.append({"target": (mx, my), "action": "WATER", "priority": 95})
                    if t.get("yield_units", 0) > 0 and (day - t.get("planted_day", 0)) >= 10:
                        sw_tasks.append({"target": (mx, my), "action": "HARVEST", "priority": 97})

            for wx, wy in self.sw_wheat:
                t = me["tiles"][wy][wx]
                if t is None and day < 28:
                    sw_tasks.append({"target": (wx, wy), "action": "PLANT_WHEAT", "crop": "WHEAT", "priority": 93})
                elif isinstance(t, dict) and t.get("kind") == "WEED":
                    sw_tasks.append({"target": (wx, wy), "action": "DIG", "priority": 30})
                elif isinstance(t, dict) and t.get("kind") == "PLANT":
                    if not t.get("watered_today", False):
                        sw_tasks.append({"target": (wx, wy), "action": "WATER", "priority": 92})
                    if t.get("yield_units", 0) > 0 and (day - t.get("planted_day", 0)) >= 2:
                        sw_tasks.append({"target": (wx, wy), "action": "HARVEST", "priority": 90})

        all_units = [me["farmer"]] + me.get("hands", [])
        unit_actions = []
        claimed_targets = set()
        is_endgame_flush = (day >= 29 and hour >= 18)

        avail_seeds = dict(private.get("seeds", {}))

        for u_idx, (ux, uy) in enumerate(all_units):
            inv = private["inventories"][u_idx] if u_idx < len(private["inventories"]) else {}
            pos = (ux, uy)
            current_tile = me["tiles"][uy][ux]
            action = ["PASS"]

            carrying_produce = sum(v for k, v in inv.items() if k not in ["COW", "SHEEP", "GOOSE"])
            carrying_animal = "COW" if inv.get("COW", 0) > 0 else ("GOOSE" if inv.get("GOOSE", 0) > 0 else ("SHEEP" if inv.get("SHEEP", 0) > 0 else None))
            wheat_count = inv.get("WHEAT", 0)

            # Assign Drop Tiles
            if u_idx == 0:
                default_drop_tile = (4, 4)
                my_cluster = [(4, 3), (4, 2), (4, 1), (4, 0)]
            elif u_idx == 1:
                default_drop_tile = (4, 4)
                my_cluster = [(3, 4), (3, 3), (3, 2), (3, 1)]
            elif u_idx == 2:
                default_drop_tile = (4, 4)
                my_cluster = [(2, 4), (2, 3), (2, 2)]
            elif u_idx == 3:
                default_drop_tile = (4, 4)
                my_cluster = [(1, 4), (1, 3), (0, 4)]
            elif u_idx in (4, 5):
                default_drop_tile = (4, 4)
                my_cluster = []
            elif u_idx in (6, 7, 8):
                default_drop_tile = (5, 4)
                my_cluster = []
            else:
                default_drop_tile = (4, 5)
                my_cluster = []

            # Endgame Rush
            if is_endgame_flush:
                if pos in SHED_ACCESS_TILES:
                    action = ["DROP"]
                else:
                    action = [get_step_towards(pos, default_drop_tile)]
                unit_actions.append(action)
                continue

            # =========================================================
            # SECTION A: SWEEP CREW (UNITS 0..3) - ANIMAL DEDICATED
            # =========================================================
            if u_idx < 4:
                if isinstance(current_tile, dict) and ("animal" in current_tile):
                    animal_type = current_tile.get("animal")
                    y_units = current_tile.get("yield_units", 0)

                    if not current_tile.get("fed_today", False) and wheat_count > 0:
                        action = ["FEED"]
                    elif not current_tile.get("cared_today", False):
                        action = ["CARE"]
                    elif animal_type == "GOOSE" and y_units >= 2:
                        action = ["HARVEST"]
                    elif (animal_type == "COW" and y_units >= 2) or (animal_type == "SHEEP" and y_units >= 3) or y_units >= 4:
                        action = ["HARVEST"]
                    elif current_tile.get("fertilizer_available", False):
                        action = ["COLLECT_FERTILIZER"]

                if action == ["PASS"] and pos in SHED_ACCESS_TILES:
                    if day < 18 and private["shed"].get("COW", 0) > 0 and not carrying_animal:
                        action = ["PICKUP", "COW", 1]
                    elif day < 18 and private["shed"].get("GOOSE", 0) > 0 and not carrying_animal:
                        action = ["PICKUP", "GOOSE", 1]
                    elif day < 18 and private["shed"].get("SHEEP", 0) > 0 and not carrying_animal:
                        action = ["PICKUP", "SHEEP", 1]
                    elif hour >= 16 and (carrying_produce - wheat_count) > 0:
                        action = ["DROP"]
                    elif wheat_count < 4 and shed_wheat > 0 and day < 30:
                        pickup_amt = min(5 - wheat_count, shed_wheat)
                        if pickup_amt > 0:
                            action = ["PICKUP", "WHEAT", pickup_amt]

                if action == ["PASS"] and carrying_animal:
                    if carrying_animal == "COW":
                        target_coords = self.cow_pastures
                        req_struct = "PASTURE"
                        build_act = "BUILD_PASTURE"
                    elif carrying_animal == "GOOSE":
                        target_coords = self.goose_coops
                        req_struct = "COOP"
                        build_act = "BUILD_COOP"
                    else:
                        target_coords = self.sheep_pastures
                        req_struct = "PASTURE"
                        build_act = "BUILD_PASTURE"

                    target_spot = None
                    for px, py in target_coords:
                        t = me["tiles"][py][px]
                        if isinstance(t, dict) and t.get("kind") == req_struct and "animal" not in t:
                            target_spot = (px, py)
                            break
                        elif t is None:
                            target_spot = (px, py)
                            break

                    if target_spot:
                        if pos == target_spot:
                            t = me["tiles"][uy][ux]
                            if t is None:
                                action = [build_act]
                            elif isinstance(t, dict) and t.get("kind") == req_struct:
                                action = ["PLACE", carrying_animal, 1]
                        else:
                            action = [get_step_towards(pos, target_spot)]

                if action == ["PASS"] and not carrying_animal:
                    if day < 18 and (shed_c > 0 or shed_g > 0 or shed_s > 0) and pos not in SHED_ACCESS_TILES and hour < 14:
                        action = [get_step_towards(pos, default_drop_tile)]
                    else:
                        best_target = None
                        best_score = -1e9

                        for px, py in my_cluster:
                            if (px, py) in claimed_targets:
                                continue
                            t = me["tiles"][py][px]
                            if isinstance(t, dict) and ("animal" in t):
                                is_unfed = (not t.get("fed_today", False))
                                is_uncared = (not t.get("cared_today", False))
                                has_fert = t.get("fertilizer_available", False)
                                has_yield = (t.get("yield_units", 0) >= 2)

                                if (is_unfed and wheat_count > 0) or is_uncared or has_fert or has_yield:
                                    priority = 100 if is_unfed else (90 if is_uncared else 80)
                                    score = priority * 10 - dist(pos, (px, py))
                                    if score > best_score:
                                        best_score = score
                                        best_target = (px, py)

                        if not best_target:
                            for px, py in self.cow_pastures + self.goose_coops:
                                if (px, py) in claimed_targets:
                                    continue
                                t = me["tiles"][py][px]
                                if t is None and total_c + total_g + total_s < 14 and day < 18:
                                    best_target = (px, py)
                                    break
                                elif isinstance(t, dict) and t.get("kind") == "WEED":
                                    best_target = (px, py)
                                    break
                                elif isinstance(t, dict) and ("animal" in t):
                                    is_unfed = (not t.get("fed_today", False))
                                    is_uncared = (not t.get("cared_today", False))
                                    if (is_unfed and wheat_count > 0) or is_uncared:
                                        priority = 95 if is_unfed else 85
                                        score = priority * 10 - dist(pos, (px, py))
                                        if score > best_score:
                                            best_score = score
                                            best_target = (px, py)

                        if best_target:
                            claimed_targets.add(best_target)
                            tx, ty = best_target
                            if pos == best_target:
                                t = me["tiles"][ty][tx]
                                is_coop_tile = (tx, ty) in self.goose_coops
                                if t is None:
                                    action = ["BUILD_COOP" if is_coop_tile else "BUILD_PASTURE"]
                                elif isinstance(t, dict) and t.get("kind") == "WEED":
                                    action = ["DIG"]
                                elif isinstance(t, dict) and ("animal" in t):
                                    if not t.get("fed_today", False) and wheat_count > 0:
                                        action = ["FEED"]
                                    elif not t.get("cared_today", False):
                                        action = ["CARE"]
                                    elif t.get("fertilizer_available", False):
                                        action = ["COLLECT_FERTILIZER"]
                                    elif t.get("yield_units", 0) >= 1:
                                        action = ["HARVEST"]
                            else:
                                action = [get_step_towards(pos, best_target)]
                        else:
                            if (carrying_produce - wheat_count) > 0 and hour >= 16:
                                action = [get_step_towards(pos, default_drop_tile)]
                            elif wheat_count == 0 and shed_wheat > 0 and hour < 14:
                                action = [get_step_towards(pos, default_drop_tile)]
                            else:
                                action = ["PASS"]

            # =========================================================
            # SECTION B: CROP CREWS (UNITS 4..12) - STRICT CROPS
            # =========================================================
            else:
                # Stand-and-Water: If standing on an unwatered plant, immediately water it!
                if isinstance(current_tile, dict) and current_tile.get("kind") == "PLANT" and not current_tile.get("watered_today", False):
                    action = ["WATER"]

                # High-Throughput Batch Drop
                elif pos in SHED_ACCESS_TILES and carrying_produce > 0:
                    action = ["DROP"]

                if action == ["PASS"]:
                    if carrying_produce >= 15 or (carrying_produce > 0 and hour >= 18):
                        action = [get_step_towards(pos, default_drop_tile)]
                    else:
                        sector_tasks = []
                        if u_idx in (4, 5):
                            sector_tasks = nw_wheat_tasks_p1 or nw_wheat_tasks_p2 or ne_tasks or sw_tasks
                        elif u_idx in (6, 7, 8):
                            sector_tasks = ne_tasks or nw_wheat_tasks_p1 or nw_wheat_tasks_p2 or sw_tasks
                        else:
                            sector_tasks = sw_tasks or ne_tasks or nw_wheat_tasks_p1 or nw_wheat_tasks_p2

                        best_task = None
                        best_score = -1e9

                        for t in sector_tasks:
                            target = t["target"]
                            if target in claimed_targets:
                                continue
                            if "crop" in t and avail_seeds.get(t["crop"], 0) <= 0:
                                continue

                            d = dist(pos, target)
                            score = t["priority"] * 10 - d + (500 if d == 0 else 0)
                            if score > best_score:
                                best_score = score
                                best_task = t

                        if best_task:
                            target = best_task["target"]
                            claimed_targets.add(target)
                            tx, ty = target

                            if pos == target:
                                tact = best_task["action"]
                                if tact == "HARVEST":
                                    action = ["HARVEST"]
                                elif tact == "WATER":
                                    action = ["WATER"]
                                elif tact == "PLANT_WHEAT" and avail_seeds.get("WHEAT", 0) > 0:
                                    action = ["PLANT", "WHEAT"]
                                    avail_seeds["WHEAT"] -= 1
                                elif tact == "PLANT_STRAWBERRY" and avail_seeds.get("STRAWBERRY", 0) > 0:
                                    action = ["PLANT", "STRAWBERRY"]
                                    avail_seeds["STRAWBERRY"] -= 1
                                elif tact == "PLANT_MELON" and avail_seeds.get("MELON", 0) > 0:
                                    action = ["PLANT", "MELON"]
                                    avail_seeds["MELON"] -= 1
                                elif tact == "PLANT_CARROT" and avail_seeds.get("CARROT", 0) > 0:
                                    action = ["PLANT", "CARROT"]
                                    avail_seeds["CARROT"] -= 1
                                elif tact == "DIG":
                                    action = ["DIG"]
                            else:
                                action = [get_step_towards(pos, target)]
                        else:
                            if carrying_produce > 0:
                                action = [get_step_towards(pos, default_drop_tile)]
                            else:
                                action = ["PASS"]

            unit_actions.append(action)

        return {
            "farmer": unit_actions[0] if unit_actions else ["PASS"],
            "hands": unit_actions[1:] if len(unit_actions) > 1 else [],
            "market": market_orders[:10],
        }

def make_spatial_dispatcher_agent(params=None, seed: Optional[int] = None, kw_early: Optional[int] = None):
    agent_instance = MaestroFullPortfolioAgent(params=params, seed=seed, kw_early=kw_early)
    return lambda obs: agent_instance(obs)