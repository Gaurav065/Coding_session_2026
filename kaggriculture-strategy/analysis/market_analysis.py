"""Market economics for Kaggriculture, computed from the shipped env constants.

Answers three questions that drive the whole strategy:
  1. How much money can each product absorb before its price collapses?
  2. How much does the town drain per day (i.e. the free sell rate that keeps
     price pinned at base)?
  3. What is a tile-day actually worth for each crop / animal?

Run:  python analysis/market_analysis.py
"""
import math
import random
from collections import defaultdict

from kaggle_environments.envs.kaggriculture.kaggriculture import (
    ANIMALS, CROPS, MARKET_PARAMS, MARKET_I0, PRODUCTS, SHOPS,
    TOWN_CENTER_PRODUCTS, MAX_SHOP_INSTANCES, market_price,
)

DAYS = 30
TURNS_PER_DAY = 24
SHOP_TICKS_PER_DAY = TURNS_PER_DAY // 4   # townShopSellInterval = 4
SHOP_UNLOCK_INTERVAL = 3


def hr(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


# ---------------------------------------------------------------- 1. glut curves
def sell_curve(item, max_units=1400):
    """Sell `max_units` into a market sitting exactly at I0, no town recovery.

    Returns (revenue_total, marginal_price_list). This is the worst case: a
    single-player dump with zero demand-side recovery.
    """
    inv = MARKET_I0
    revenue = 0
    marginals = []
    for _ in range(max_units):
        p = market_price(item, inv)
        revenue += p
        marginals.append(p)
        if p > 1:          # $1 sales do not add to inventory (price floor stays live)
            inv += 1
    return revenue, marginals


def glut_table():
    hr("1. GLUT CURVES -- dumping into a market at I0, no town recovery")
    print(f"{'item':<11} {'base':>5} {'p@100':>6} {'p@250':>6} {'p@500':>6} "
          f"{'->half':>7} {'->$1':>6} {'rev@peak':>9} {'peak N':>7}")
    summary = {}
    for item in PRODUCTS:
        base = MARKET_PARAMS[item]["base"]
        rev, marg = sell_curve(item)

        def at(n):
            return marg[n] if n < len(marg) else marg[-1]

        half = next((i for i, p in enumerate(marg) if p <= base / 2), None)
        floor = next((i for i, p in enumerate(marg) if p <= 1), None)
        # Revenue-maximising burst size = sell while marginal price is meaningful.
        cum, best_rev, best_n = 0, 0, 0
        for i, p in enumerate(marg):
            cum += p
            if p > 1 and cum > best_rev:
                best_rev, best_n = cum, i + 1
        summary[item] = dict(base=base, half=half, floor=floor,
                             peak_rev=best_rev, peak_n=best_n, marg=marg)
        print(f"{item:<11} {base:>5} {at(100):>6} {at(250):>6} {at(500):>6} "
              f"{str(half):>7} {str(floor):>6} {best_rev:>9,} {best_n:>7}")
    print("\n'->half' = units dumped before price halves.  '->$1' = units to hit the floor.")
    print("'rev@peak' = total cash from dumping up to the last unit worth >$1.")
    return summary


# ------------------------------------------------------------- 2. town demand
def town_demand_expected():
    """Exact expectation of town consumption per product over the season.

    Shops unlock at end of day 2, 5, 8, ... -> active instance count on day d is
    min(8, d // 3). Each instance eats 1 per demanded product per 4 turns
    (6x/day), doubled for single-product shops. Town center eats 1/day of every
    non-fertilizer product.
    """
    instance_days = sum(min(MAX_SHOP_INSTANCES, d // SHOP_UNLOCK_INTERVAL) for d in range(DAYS))
    n_shops = len(SHOPS)
    weight = defaultdict(float)   # expected per-instance units/day
    for shop, products in SHOPS.items():
        mult = 2 if len(products) == 1 else 1
        for p in products:
            weight[p] += (1 / n_shops) * mult * SHOP_TICKS_PER_DAY

    demand = {}
    for p in PRODUCTS:
        shops_part = instance_days * weight[p]
        center_part = DAYS if p in TOWN_CENTER_PRODUCTS else 0
        demand[p] = shops_part + center_part
    return demand, instance_days, weight


def town_table():
    hr("2. TOWN DEMAND -- the free sink that holds price at (or above) base")
    demand, instance_days, weight = town_demand_expected()
    print(f"shop instance-days over the season: {instance_days} "
          f"(8 instances live from day 24 on)\n")
    print(f"{'item':<11} {'base':>5} {'shops':>6} {'E[units/day @ full unlock]':>27} "
          f"{'E[season total]':>16} {'value @ base':>13}")
    for p in PRODUCTS:
        n_shops_with = sum(1 for s, prods in SHOPS.items() if p in prods)
        full_rate = MAX_SHOP_INSTANCES * weight[p] + (1 if p in TOWN_CENTER_PRODUCTS else 0)
        print(f"{p:<11} {MARKET_PARAMS[p]['base']:>5} {n_shops_with:>6} "
              f"{full_rate:>27.1f} {demand[p]:>16.0f} "
              f"{demand[p] * MARKET_PARAMS[p]['base']:>13,.0f}")
    print("\nSelling AT this rate keeps inventory at I0 and price at base forever.")
    print("Selling faster pushes into the glut curve above; slower pushes price UP.")
    return demand


def scarcity_table():
    hr("2b. SCARCITY -- price if NOBODY sells (pure town drain)")
    demand, _, _ = town_demand_expected()
    print(f"{'item':<11} {'base':>5} {'drain@d10':>10} {'p@d10':>7} "
          f"{'drain@d20':>10} {'p@d20':>7} {'drain@d30':>10} {'p@d30':>7}")
    for p in PRODUCTS:
        row = [p, MARKET_PARAMS[p]["base"]]
        _, _, weight = town_demand_expected()
        for upto in (10, 20, 30):
            inst_days = sum(min(MAX_SHOP_INSTANCES, d // SHOP_UNLOCK_INTERVAL) for d in range(upto))
            drained = inst_days * weight[p] + (upto if p in TOWN_CENTER_PRODUCTS else 0)
            row += [drained, market_price(p, int(MARKET_I0 - drained))]
        print(f"{row[0]:<11} {row[1]:>5} {row[2]:>10.0f} {row[3]:>7} "
              f"{row[4]:>10.0f} {row[5]:>7} {row[6]:>10.0f} {row[7]:>7}")
    print("\nWheat is the one staple that gets genuinely EXPENSIVE -- it is the")
    print("animal feedstock AND the most-demanded shop input. Plan feed accordingly.")


# ------------------------------------------------------- 3. per-tile economics
def crop_plan(crop):
    """Minimum-action optimal schedule for one crop cycle (no fertilizer).

    Watering rule: a plant dies after 2 consecutive dry days and starts at
    consecutive_unwatered = 1, so day 0 is mandatory and then every other day
    is enough -- EXCEPT inside the bonus window, where every day adds yield.
    """
    cd = CROPS[crop]
    if not cd["ongoing"]:
        win_start = (cd["max_yield_day"] + 1) // 2
        # yield starts at 1, +1 per watered day in [win_start, max_yield_day],
        # capped at max_yield -> find the earliest day we can bank the cap.
        units, harvest_day = 1, cd["max_yield_day"]
        for age in range(win_start, cd["max_yield_day"] + 1):
            if units >= cd["max_yield"]:
                harvest_day = age
                break
            units += 1
            harvest_day = age
        units = min(units, cd["max_yield"])
        bonus_days = set(range(win_start, harvest_day + 1))
        survival_days = {d for d in range(0, harvest_day + 1) if d % 2 == 0}
        waters = sorted(bonus_days | survival_days | {0})
        actions = 1 + len(waters) + 1               # plant + waters + harvest
        occupancy = harvest_day + 1                 # tile-days consumed
        return dict(units=units, actions=actions, occupancy=occupancy,
                    waters=len(waters), harvests=1, seed=cd["seed"])
    # ongoing: production fires max_yield times, each worth 1 (2 if fertilized)
    last_prod_age = cd["first_yield_day"] + cd["interval"] * (cd["max_yield"] - 1)
    waters = len({0} | {d for d in range(0, last_prod_age + 1) if d % 2 == 0})
    harvests = math.ceil(cd["max_yield"] / cd["max_yield"])  # cap is max_yield held
    harvests = 2                                              # realistic: mid + final
    actions = 1 + waters + harvests
    return dict(units=cd["max_yield"], actions=actions, occupancy=last_prod_age + 1,
                waters=waters, harvests=harvests, seed=cd["seed"])


def crop_table(sell_price):
    hr("3. CROP UNIT ECONOMICS (unfertilized, minimum-action watering)")
    print(f"{'crop':<11} {'seed':>5} {'units':>6} {'occ(d)':>7} {'acts':>5} "
          f"{'$/unit':>7} {'gross':>7} {'$/tile-day':>11} {'$/action':>9}")
    rows = []
    for crop in CROPS:
        pl = crop_plan(crop)
        price = sell_price[crop]
        gross = pl["units"] * price
        net = gross - pl["seed"]
        rows.append((net / pl["occupancy"], crop))
        print(f"{crop:<11} {pl['seed']:>5} {pl['units']:>6} {pl['occupancy']:>7} "
              f"{pl['actions']:>5} {price:>7} {gross:>7,} "
              f"{net / pl['occupancy']:>11.1f} {net / pl['actions']:>9.1f}")
    print("\nActions exclude walking. Add ~1 move per action in practice.")
    return rows


def animal_table(sell_price, fert_price, wheat_cost):
    hr("4. ANIMAL UNIT ECONOMICS (steady state, per tile-day)")
    print("Two feed regimes. 'alternate' = feed every other day: the animal")
    print("survives and still produces its BASE yield (production is not gated")
    print("on fed_today) but banks no CARE bonus. 'daily+care' doubles output.\n")
    print(f"{'animal':<7} {'cost':>5} {'regime':<11} {'prod/day':>9} {'feed/day':>9} "
          f"{'$prod':>7} {'$fert':>7} {'-$feed':>7} {'net/tile-day':>13} {'acts/day':>9}")
    for name, a in ANIMALS.items():
        product = a["product"]
        base_rate = 1 / a["interval"]
        for regime, rate, feed, acts in (
            ("alternate", base_rate, 0.5, 0.5 + 1 + base_rate),           # feed + fert + harvest
            ("daily+care", base_rate * 2, 1.0, 1 + 1 + 1 + base_rate * 2),  # feed+care+fert+harvest
        ):
            prod_val = rate * sell_price[product]
            fert_val = fert_price
            feed_cost = feed * wheat_cost
            net = prod_val + fert_val - feed_cost
            print(f"{name:<7} {a['cost']:>5} {regime:<11} {rate:>9.2f} {feed:>9.2f} "
                  f"{prod_val:>7.0f} {fert_val:>7.0f} {-feed_cost:>7.0f} "
                  f"{net:>13.1f} {acts:>9.2f}")
    print("\nEvery surviving animal yields 1 FERTILIZER/day regardless of feeding.")
    print("Note care-bonus doubling only lands on days the animal is ALSO fed.")


def payback_table(sell_price, fert_price, wheat_cost):
    hr("5. CAPITAL PAYBACK -- when does each purchase repay itself?")
    print(f"{'buy':<14} {'cost':>6} {'first yield':>12} {'net/day':>8} "
          f"{'payback day':>12} {'season net (buy d0)':>20}")
    for name, a in ANIMALS.items():
        rate = 1 / a["interval"] * 2          # daily + care
        net = rate * sell_price[a["product"]] + fert_price - 1.0 * wheat_cost
        first = a["first_yield_day"] + 1      # +1 day to build structure & place
        days_live = max(0, DAYS - 1 - first)
        print(f"{'GOOSE/COW/SHEEP'[:0] + name:<14} {a['cost']:>6} {first:>12} "
              f"{net:>8.0f} {first + a['cost'] / net:>12.1f} "
              f"{days_live * net - a['cost']:>20,.0f}")
    for crop in ("MELON", "STRAWBERRY"):
        pl = crop_plan(crop)
        net = pl["units"] * sell_price[crop] - pl["seed"]
        print(f"{crop:<14} {pl['seed']:>6} {pl['occupancy'] - 1:>12} "
              f"{net / pl['occupancy']:>8.0f} {pl['occupancy']:>12.1f} "
              f"{net * (DAYS // pl['occupancy']):>20,.0f}")
    print(f"\n{'LAND NE':<14} {1000:>6}   unlocks 25 tiles -- pays back if a tile clears "
          f"$40/day for 25 days")
    print(f"{'LAND SW':<14} {2000:>6}   "
          f"{'':>12}")
    print(f"{'LAND SE':<14} {4000:>6}   "
          f"{'':>12}")


def hire_table():
    hr("6. LABOUR -- hiring is absurdly cheap; actions are the real currency")
    fib, a, b = [], 1, 1
    for _ in range(18):
        fib.append(a)
        a, b = b, a + b
    cum = 0
    print(f"{'hands':>6} {'marginal':>9} {'day cost':>9} {'actions/day':>12} "
          f"{'$/action at 30d':>16}")
    for i, f in enumerate(fib, start=1):
        cum += f
        acts = (1 + i) * TURNS_PER_DAY
        print(f"{i:>6} {f:>9} {cum:>9} {acts:>12} {cum / acts:>16.3f}")
    print("\n12 hands = 312 actions/day for $376. 16 hands = 408 actions for $2,583.")
    print("The knee is around 12-14 hands; past that the fib curve bites hard.")


def melon_race():
    hr("7. THE MELON RACE -- why first-to-market wins the biggest single pool")
    rev, marg = sell_curve("MELON", 400)
    for n in (30, 60, 78, 100, 130, 158, 200):
        total = sum(marg[:n])
        print(f"  sell {n:>3} melons first -> ${total:>7,}  (last unit ${marg[n - 1]:>3})")
    print("\n  ...but if the opponent dumps 100 melons BEFORE you:")
    for n in (30, 60, 78):
        total = sum(marg[100:100 + n])
        print(f"  your next {n:>3} melons  -> ${total:>7,}  "
              f"({100 * (1 - total / max(1, sum(marg[:n]))):.0f}% worse)")
    print("\nMELON has ZERO shop demand and only 1/day town-center demand, so the")
    print("pool never refills. Same for FERTILIZER (excluded from town center too).")
    print("These two are strictly first-come-first-served. Everything else recovers.")


def main():
    glut = glut_table()
    demand = town_table()
    scarcity_table()

    # Realistic realised prices: throttled selling holds near base for products
    # with real town demand; melon/fertilizer degrade because nothing refills them.
    realised = {p: MARKET_PARAMS[p]["base"] for p in PRODUCTS}
    realised["MELON"] = 150      # avg over a ~158-unit season take
    realised["FERTILIZER"] = 55  # avg over a ~450-unit season take
    realised["STRAWBERRY"] = 110
    realised["WOOL"] = 190
    realised["MILK"] = 150

    crop_table(realised)
    animal_table(realised, fert_price=realised["FERTILIZER"], wheat_cost=32)
    payback_table(realised, fert_price=realised["FERTILIZER"], wheat_cost=32)
    hire_table()
    melon_race()

    hr("8. SEASON REVENUE CEILING (what a perfect solo season could bank)")
    total = 0
    print(f"{'item':<11} {'town absorbs':>13} {'+ glut headroom':>16} "
          f"{'realistic units':>16} {'$ at realised':>14}")
    for p in PRODUCTS:
        head = glut[p]["half"] if glut[p]["half"] else 0
        units = demand[p] + head * 0.5
        cash = units * realised[p]
        total += cash
        print(f"{p:<11} {demand[p]:>13.0f} {head:>16} {units:>16.0f} {cash:>14,.0f}")
    print(f"\n{'TOTAL':<11} {'':>13} {'':>16} {'':>16} {total:>14,.0f}")
    print("Shared with the opponent, and gated by 100 tiles + labour, so a strong")
    print("agent realistically banks a fraction of this.")


if __name__ == "__main__":
    main()
