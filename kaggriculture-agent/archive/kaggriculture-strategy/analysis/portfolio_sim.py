"""Season cash-flow model: which portfolio of tiles actually banks the most?

Not a game simulator -- it is a deterministic economic model of one player,
using the real price function and the verified production rates. It exists to
answer: how many cows/sheep/geese/melons, when to buy land, and what the
resulting bankroll looks like.

Run:  python analysis/portfolio_sim.py
"""
import itertools
import math
from collections import defaultdict

from kaggle_environments.envs.kaggriculture.kaggriculture import (
    ANIMALS, CROPS, LAND_PRICES, MARKET_I0, MARKET_PARAMS, PRODUCTS, SHOPS,
    TOWN_CENTER_PRODUCTS, MAX_SHOP_INSTANCES, market_price,
)

DAYS, TPD = 30, 24
SHED_CAP = 100

# Verified in verify_mechanics.py: CARE pays base 1 + every bonus banked since
# the last firing, so the steady rate is (1 + interval) / interval per day.
ANIMAL_RATE = {a: (1 + d["interval"]) / d["interval"] for a, d in ANIMALS.items()}
HARVEST_CADENCE = {a: max(1, ANIMALS[a]["max_held"] // (1 + ANIMALS[a]["interval"]))
                   * ANIMALS[a]["interval"] for a in ANIMALS}


def town_rate(day):
    """Expected town consumption per product on `day` (shops + town center)."""
    instances = min(MAX_SHOP_INSTANCES, day // 3)
    rate = defaultdict(float)
    for shop, products in SHOPS.items():
        mult = 2 if len(products) == 1 else 1
        for p in products:
            rate[p] += instances * (1 / len(SHOPS)) * mult * (TPD // 4)
    for p in TOWN_CENTER_PRODUCTS:
        rate[p] += 1
    return rate


def fib_cumsum(n):
    total, a, b = 0, 1, 1
    for _ in range(n):
        total += a
        a, b = b, a + b
    return total


# Products with no shop demand never recover, so their pool is first-come.
NO_RECOVERY = {"MELON", "FERTILIZER"}


class Season:
    def __init__(self, plan, verbose=False):
        self.plan = plan
        self.verbose = verbose
        self.care = plan.get("care", True)
        self.money = 3000.0
        self.inv = {p: MARKET_I0 for p in PRODUCTS}
        self.tiles = 25
        self.land_bought = 0
        self.animals = []          # (kind, placed_day)
        self.melon_tiles = 0
        self.wheat_tiles = 0
        self.straw_tiles = 0
        self.straw_planted = []      # planting day of each strawberry tile
        self.stock = defaultdict(float)
        self.log = []
        self.hire_spend = 0.0
        self.feed_spend = 0.0
        self.seed_spend = 0.0
        self.capital_spend = 0.0
        self.starved = 0
        self.cared_today = 0

    # ---------------------------------------------------------------- market
    def price(self, p):
        return market_price(p, int(round(self.inv[p])))

    def sell(self, p, units, reservation):
        """Sell into the live curve, stopping when the marginal price drops
        below `reservation`. Returns cash raised."""
        cash, sold = 0.0, 0
        while sold < units:
            px = self.price(p)
            if px < reservation:
                break
            cash += px
            sold += 1
            if px > 1:
                self.inv[p] += 1
        self.stock[p] -= sold
        self.money += cash
        return cash, sold

    def buy_wheat(self, units):
        cash, got = 0.0, 0
        while got < units:
            px = market_price("WHEAT", int(round(self.inv["WHEAT"])) - 1)
            if px > self.plan["max_wheat_price"] or self.money < px:
                break
            self.money -= px
            self.inv["WHEAT"] -= 1
            cash += px
            got += 1
        self.feed_spend += cash
        return got

    # ------------------------------------------------------------ investment
    def try_buy_land(self, day):
        while self.land_bought < 3:
            cost = LAND_PRICES[self.land_bought]
            if day < self.plan["land_day"][self.land_bought]:
                return
            if self.money < cost + self.plan["cash_buffer"]:
                return
            self.money -= cost
            self.capital_spend += cost
            self.land_bought += 1
            self.tiles += 25

    def free_tiles(self):
        return (self.tiles - len(self.animals) - self.melon_tiles
                - self.wheat_tiles - self.straw_tiles)

    def try_buy_animals(self, day):
        if day > self.plan["last_animal_day"]:
            return
        counts = defaultdict(int)
        for kind, _ in self.animals:
            counts[kind] += 1
        for kind in self.plan["animal_priority"]:
            target = self.plan["target"][kind]
            while (counts[kind] < target and self.free_tiles() > 0
                   and self.money >= ANIMALS[kind]["cost"] + self.plan["cash_buffer"]):
                self.money -= ANIMALS[kind]["cost"]
                self.capital_spend += ANIMALS[kind]["cost"]
                self.animals.append((kind, day))
                counts[kind] += 1

    def try_plant(self, day):
        # Melon only pays if it can finish: 10 days from planting.
        while (self.melon_tiles < self.plan["target"]["MELON"]
               and self.free_tiles() > 0 and day + 10 <= DAYS - 1
               and self.money >= CROPS["MELON"]["seed"]):
            self.money -= CROPS["MELON"]["seed"]
            self.seed_spend += CROPS["MELON"]["seed"]
            self.melon_tiles += 1
        while (self.wheat_tiles < self.plan["target"]["WHEAT_TILES"]
               and self.free_tiles() > 0 and day + 4 <= DAYS - 1
               and self.money >= CROPS["WHEAT"]["seed"]):
            self.money -= CROPS["WHEAT"]["seed"]
            self.seed_spend += CROPS["WHEAT"]["seed"]
            self.wheat_tiles += 1
        # Strawberry needs 16 days to fire all four scheduled yields.
        while (self.straw_tiles < self.plan["target"]["STRAW"]
               and self.free_tiles() > 0 and day + 16 <= DAYS - 1
               and self.money >= CROPS["STRAWBERRY"]["seed"]):
            self.money -= CROPS["STRAWBERRY"]["seed"]
            self.seed_spend += CROPS["STRAWBERRY"]["seed"]
            self.straw_tiles += 1
            self.straw_planted.append(day)

    # ---------------------------------------------------------------- labour
    def actions_needed(self):
        acts = 0.0
        for kind, _ in self.animals:
            acts += 1 + 1 + 1                                  # feed, care, collect
            acts += 1 / HARVEST_CADENCE[kind]                  # harvest
            acts += 1.2                                        # movement + wheat runs
        acts += self.melon_tiles * 2.1                         # ~1 water/day + move
        acts += self.wheat_tiles * 2.2
        acts += self.straw_tiles * 2.3                         # water + periodic fertilize
        return acts

    def hire(self, day):
        need = self.actions_needed()
        hands = 0
        while hands < 16 and (1 + hands) * TPD < need:
            hands += 1
        cost = fib_cumsum(hands)
        if cost > self.money:
            while hands > 0 and fib_cumsum(hands) > self.money:
                hands -= 1
            cost = fib_cumsum(hands)
        self.money -= cost
        self.hire_spend += cost
        return hands, cost, need

    # ------------------------------------------------------------------ loop
    def run(self, days=None, shared_town=False):
        """`days` + `shared_town` let two Seasons share one market dict: the
        caller drains the town once, then steps each player through that day."""
        for day in (range(DAYS) if days is None else days):
            if not shared_town:
                rate = town_rate(day)
                for p in PRODUCTS:
                    self.inv[p] = max(0, self.inv[p] - rate[p])

            self.try_buy_land(day)
            self.try_buy_animals(day)
            self.try_plant(day)
            hands, hire_cost, need = self.hire(day)

            # ---- feed. CARE requires the animal to be fed that same day, so the
            # care regime costs 1 wheat/animal/day; the base regime survives on
            # every-other-day feeding at 0.5.
            n_animals = len(self.animals)
            feed_per_animal = 1.0 if self.care else 0.5
            self.stock["WHEAT"] += self.wheat_tiles * 0.8
            need_wheat = n_animals * feed_per_animal
            shortfall = max(0, need_wheat - self.stock["WHEAT"])
            got = self.buy_wheat(shortfall)
            available = self.stock["WHEAT"] + got

            # Feed is not optional. Whatever we cannot feed daily drops to the
            # every-other-day survival regime (base rate, no CARE bonus); if we
            # cannot even manage 0.5/animal/day, the hungriest animals escape.
            if n_animals:
                cared = min(n_animals, int(available // 1.0)) if self.care else 0
                rest = n_animals - cared
                used = cared * 1.0 + rest * 0.5
                if used > available:                      # genuine starvation
                    survivors = int(available // 0.5)
                    lost = n_animals - survivors
                    if lost > 0:
                        # cheapest-first culling mirrors what a real agent would allow to go
                        self.animals.sort(key=lambda t: ANIMALS[t[0]]["cost"])
                        self.animals = self.animals[lost:]
                        n_animals = len(self.animals)
                        cared, rest = 0, n_animals
                        used = n_animals * 0.5
                        self.starved += lost
                self.stock["WHEAT"] = max(0, available - used)
                self.cared_today = cared
            else:
                self.stock["WHEAT"] = available
                self.cared_today = 0

            # ---- production (rates verified in verify_mechanics.py)
            cared_left = self.cared_today
            for kind, placed in self.animals:
                a = ANIMALS[kind]
                age = day - placed
                is_cared = cared_left > 0
                if is_cared:
                    cared_left -= 1
                if age >= a["first_yield_day"] and (age - a["first_yield_day"]) % a["interval"] == 0:
                    if is_cared:
                        # base 1 + every bonus banked since the last firing,
                        # clipped by max_held (which is why the first payout is a burst)
                        banked = a["interval"] if age > a["first_yield_day"] else a["first_yield_day"]
                        units = min(a["max_held"], 1 + banked)
                    else:
                        units = 1
                    self.stock[a["product"]] += units
                self.stock["FERTILIZER"] += 1 if age >= 1 else 0
            if day >= 10 and self.melon_tiles:
                if (day - 10) % 11 == 0:
                    self.stock["MELON"] += self.melon_tiles * 6
            # Strawberry fires at ages 10, 12, 14, 16; fertilizer (free from the
            # animals, and worthless on the market once glutted) doubles each to 2.
            for planted in self.straw_planted:
                age = day - planted
                if age in (10, 12, 14, 16):
                    self.stock["STRAWBERRY"] += 2 if len(self.animals) else 1

            # ---- sell
            revenue = 0.0
            endgame = day >= DAYS - 2
            for p in PRODUCTS:
                if self.stock[p] <= 0:
                    continue
                if p == "WHEAT" and not endgame and n_animals:
                    # keep two days of feed in reserve, sell only the surplus
                    reserve = n_animals * 2
                    if self.stock[p] <= reserve:
                        continue
                    sellable = self.stock[p] - reserve
                    cash, _ = self.sell(p, int(sellable),
                                        MARKET_PARAMS[p]["base"] * self.plan["res_recover"])
                    revenue += cash
                    continue
                base = MARKET_PARAMS[p]["base"]
                if endgame:
                    res = 1
                elif p in NO_RECOVERY:
                    res = base * self.plan["res_norecover"]
                else:
                    res = base * self.plan["res_recover"]
                cash, _ = self.sell(p, int(self.stock[p]), res)
                revenue += cash

            # shed overflow: anything unsold above the cap is discarded overnight
            held = sum(v for v in self.stock.values() if v > 0)
            if held > SHED_CAP:
                over = held - SHED_CAP
                for p in sorted(self.stock, key=lambda k: MARKET_PARAMS[k]["base"]):
                    if over <= 0:
                        break
                    drop = min(self.stock[p], over)
                    self.stock[p] -= drop
                    over -= drop

            self.log.append(dict(day=day, money=self.money, revenue=revenue,
                                 animals=n_animals, hands=hands, need=need,
                                 tiles=self.tiles, free=self.free_tiles()))
        return self.money


def make_plan(cows, sheep, geese, melons, wheat_tiles, straw=0, land_day=(0, 8, 12),
              res_recover=0.80, res_norecover=0.12, max_wheat_price=90,
              cash_buffer=150, last_animal_day=22, care=True,
              priority=("SHEEP", "COW", "GOOSE")):
    return dict(target={"COW": cows, "SHEEP": sheep, "GOOSE": geese,
                        "MELON": melons, "WHEAT_TILES": wheat_tiles, "STRAW": straw},
                animal_priority=list(priority), land_day=list(land_day),
                res_recover=res_recover, res_norecover=res_norecover,
                max_wheat_price=max_wheat_price, cash_buffer=cash_buffer,
                last_animal_day=last_animal_day, care=care)


def sweep():
    print("=" * 84)
    print("PORTFOLIO SWEEP -- final bank by tile allocation (single-player model)")
    print("=" * 84)
    results = []
    for cows, sheep, geese, melons, wheat, straw in itertools.product(
            (8, 12, 16), (6, 10, 14), (0, 10, 20), (0, 8, 14), (10, 20, 30), (0, 8, 16)):
        plan = make_plan(cows, sheep, geese, melons, wheat, straw)
        s = Season(plan)
        final = s.run()
        results.append((final, cows, sheep, geese, melons, wheat, straw, s))
    results.sort(reverse=True, key=lambda r: r[0])
    print(f"{'rank':>4} {'final $':>10} {'cow':>4} {'sheep':>6} {'goose':>6} "
          f"{'melon':>6} {'wheat':>6} {'straw':>6} {'hands':>6} {'feed $':>9} {'capital $':>10}")
    for i, (final, c, sh, g, m, w, st, s) in enumerate(results[:12], 1):
        peak = max(r["hands"] for r in s.log)
        print(f"{i:>4} {final:>10,.0f} {c:>4} {sh:>6} {g:>6} {m:>6} {w:>6} {st:>6} "
              f"{peak:>6} {s.feed_spend:>9,.0f} {s.capital_spend:>10,.0f}"
              + ("   STARVED" if s.starved else ""))
    print(f"\n{'':>4} {'worst':>10} " + " ".join(f"{v:>5}" for v in results[-1][1:7]) +
          f"   final ${results[-1][0]:,.0f}")
    return results[0]


def detail(best):
    final, c, sh, g, m, w, st, s = best
    print("\n" + "=" * 84)
    print(f"BEST PLAN DAY BY DAY -- {c} cow / {sh} sheep / {g} goose / "
          f"{m} melon / {w} wheat / {st} strawberry -> ${final:,.0f}")
    print("=" * 84)
    print(f"{'day':>4} {'money':>10} {'revenue':>9} {'animals':>8} {'tiles':>6} "
          f"{'free':>5} {'hands':>6} {'acts needed':>12}")
    for r in s.log:
        print(f"{r['day']:>4} {r['money']:>10,.0f} {r['revenue']:>9,.0f} "
              f"{r['animals']:>8} {r['tiles']:>6} {r['free']:>5} {r['hands']:>6} "
              f"{r['need']:>12.0f}")
    print(f"\nspend: capital ${s.capital_spend:,.0f}  feed ${s.feed_spend:,.0f}  "
          f"seed ${s.seed_spend:,.0f}  hire ${s.hire_spend:,.0f}")
    print("final market prices: " + ", ".join(
        f"{p}=${s.price(p)}" for p in PRODUCTS))


def sensitivity():
    print("\n" + "=" * 84)
    print("SENSITIVITY -- what actually moves the needle")
    print("=" * 84)
    base = make_plan(12, 10, 10, 14, 20, 8)
    ref = Season(base).run()
    print(f"  reference: 12 cow/10 sheep/10 goose/14 melon/20 wheat/8 straw"
          f"  ${ref:>10,.0f}")
    variants = [
        ("no CARE (animals at base rate)", make_plan(12, 10, 10, 14, 20, 8, care=False)),
        ("no melon", make_plan(12, 10, 10, 0, 20, 8)),
        ("no strawberry", make_plan(12, 10, 10, 14, 20, 0)),
        ("no home wheat (buy all feed)", make_plan(12, 10, 10, 14, 0, 8)),
        ("never buy land", make_plan(12, 10, 10, 14, 20, 8, land_day=(99, 99, 99))),
        ("buy only NE (1 extra quadrant)", make_plan(12, 10, 10, 14, 20, 8, land_day=(0, 99, 99))),
        ("dump everything (no reservation)", make_plan(12, 10, 10, 14, 20, 8, res_recover=0.0)),
        ("hold out for 100% of base", make_plan(12, 10, 10, 14, 20, 8, res_recover=1.0)),
        ("reservation 60% of base", make_plan(12, 10, 10, 14, 20, 8, res_recover=0.6)),
        ("goose-first priority", make_plan(12, 10, 10, 14, 20, 8,
                                           priority=("GOOSE", "COW", "SHEEP"))),
        ("all-goose (45 goose, no cow/sheep)", make_plan(0, 0, 45, 14, 20, 8)),
        ("all-crop (no animals)", make_plan(0, 0, 0, 30, 30, 20)),
    ]
    for label, plan in variants:
        val = Season(plan).run()
        print(f"  {label:<36} ${val:>10,.0f}   ({val - ref:+,.0f})")


def refine():
    """Fine-tune the herd against the pools it is actually selling into.

    The coarse sweep left WOOL at $1 (overproduced) and MILK at $222
    (undersupplied), so the sheep:cow ratio is off. Pin it down.
    """
    print("\n" + "=" * 84)
    print("REFINEMENT -- herd size vs pool size, and the sell reservation")
    print("=" * 84)
    print(f"{'cow':>4} {'sheep':>6} {'goose':>6} {'res':>5} {'final $':>10} "
          f"{'end MILK':>9} {'end WOOL':>9} {'end EGG':>8} {'end STRAW':>10}")
    rows = []
    for cows in (12, 16, 20):
        for sheep in (4, 6, 8):
            for geese in (8, 16):
                for res in (0.85, 1.0):
                    plan = make_plan(cows, sheep, geese, 14, 30, 16, res_recover=res)
                    s = Season(plan)
                    final = s.run()
                    rows.append((final, cows, sheep, geese, res, s))
    rows.sort(reverse=True, key=lambda r: r[0])
    for final, c, sh, g, res, s in rows[:14]:
        print(f"{c:>4} {sh:>6} {g:>6} {res:>5.2f} {final:>10,.0f} "
              f"{s.price('MILK'):>9} {s.price('WOOL'):>9} {s.price('EGG'):>8} "
              f"{s.price('STRAWBERRY'):>10}")
    print("\nA product ending near its base price means the herd is correctly")
    print("sized against town demand; ending at $1 means you overbuilt it.")


RECOMMENDED = make_plan(cows=14, sheep=8, geese=8, melons=14, wheat_tiles=30,
                        straw=16, res_recover=0.95)


def duel(plan_a, plan_b):
    """Two farms selling into ONE market -- the pools are shared, so every unit
    the opponent sells is a unit of headroom you no longer have."""
    a, b = Season(plan_a), Season(plan_b)
    b.inv = a.inv                                   # one shared order book
    for day in range(DAYS):
        rate = town_rate(day)
        for p in PRODUCTS:
            a.inv[p] = max(0, a.inv[p] - rate[p])
        # alternate who gets first crack at the price each day, so neither side
        # gets a systematic edge from sim ordering
        first, second = (a, b) if day % 2 == 0 else (b, a)
        first.run(days=[day], shared_town=True)
        second.run(days=[day], shared_town=True)
    return a.money, b.money, a, b


def scoring():
    print("\n" + "=" * 84)
    print("EXPECTED FINAL SCORE (day 29 bank) BY OPPONENT")
    print("=" * 84)

    solo = Season(RECOMMENDED).run()
    print(f"  {'solo (no opponent selling)':<44} ${solo:>10,.0f}")

    opponents = [
        ("vs 'starter' baseline (carrot loop)",
         make_plan(0, 0, 0, 0, 0, 0, land_day=(99, 99, 99))),
        ("vs a competent crop-only agent",
         make_plan(0, 0, 0, 20, 20, 12)),
        ("vs a goose-spam agent",
         make_plan(0, 0, 40, 8, 25, 0)),
        ("vs an equally strong mirror",
         RECOMMENDED),
    ]
    for label, opp in opponents:
        mine, theirs, sa, sb = duel(RECOMMENDED, opp)
        verdict = "WIN" if mine > theirs else ("LOSS" if mine < theirs else "TIE")
        print(f"  {label:<44} ${mine:>10,.0f}   (opp ${theirs:>9,.0f})  {verdict}")

    mine, theirs, sa, sb = duel(RECOMMENDED, RECOMMENDED)
    print(f"\n  Mirror match closing prices: " + ", ".join(
        f"{p}=${sa.price(p)}" for p in
        ("MILK", "WOOL", "STRAWBERRY", "MELON", "EGG", "WHEAT", "FERTILIZER")))
    print("  Contested pools (melon, fertilizer, wool) are what collapse; the")
    print("  deep log-curve pools (egg, wheat) barely move.")


if __name__ == "__main__":
    best = sweep()
    detail(best)
    sensitivity()
    refine()
    scoring()
