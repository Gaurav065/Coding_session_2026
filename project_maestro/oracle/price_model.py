"""Analytical Price & Valuation Model - Project Maestro (Phase 1)

Exact AMM price formulation, marginal revenue integrals, and per-commodity
economic valuation under dynamic town-shop demand, endogenous wheat feed sourcing,
and concurrent competitor supply.

References:
- kaggriculture.py:11-23 (CROPS, ANIMALS)
- kaggriculture.py:61-74 (_shape function, HINGE_GAIN)
- kaggriculture.py:103-112 (SHOPS)
- kaggriculture.py:114 (TOWN_CENTER_PRODUCTS)
- kaggriculture.py:118 (MAX_SHOP_INSTANCES = 8)
- kaggriculture.py:126-150 (MARKET_PARAMS, MARKET_I0, PRICE_FLOOR)
- kaggriculture.py:195-207 (_refresh_prices exact price computation)
- kaggriculture.py:505 (_inv_take WHEAT feed consumption)
- kaggriculture.py:596-597 (interleaved per-unit market order execution)
- kaggriculture.py:728-750 (_town_consume)
- kaggriculture.py:804-839 (exact animal yield scheduling formula)
"""

import math
from typing import Dict, List, Tuple, Optional

MARKET_I0 = 10000
PRICE_FLOOR = 1
HINGE_GAIN = 8.0

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

SHOPS_MAP = {
    "BAKERY": ["EGG", "WHEAT"],
    "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE": ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE": ["CARROT"],
    "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}


def calculate_exact_animal_yield(animal_type: str, placed_day: int = 0, total_days: int = 30) -> int:
    """Calculate exact lifetime yield using kaggriculture.py:804-839 schedule.
    
    Formula: days_since_first = next_day - placed_day - first_yield_day
    Yields on next_day when days_since_first >= 0 and days_since_first % interval == 0.
    """
    spec = ANIMALS[animal_type]
    first_yield_day = spec["first_yield_day"]
    interval = spec["interval"]
    yield_count = 0
    for next_day in range(1, total_days + 1):
        days_since_first = next_day - placed_day - first_yield_day
        if days_since_first >= 0 and days_since_first % interval == 0:
            yield_count += 1
    return yield_count


def compute_shop_zero_demand_probabilities() -> Dict[str, float]:
    """Compute the exact probability of ZERO town shop demand appearing across all 8 draws.
    
    8 total shop draws with replacement from 8 shop types (kaggriculture.py:103-118, 886-891).
    """
    total_shops = len(SHOPS_MAP) # 8
    probs = {}
    for prod in MARKET_PARAMS:
        supporting_shops = sum(1 for s, prods in SHOPS_MAP.items() if prod in prods)
        non_supporting = total_shops - supporting_shops
        p_zero = (non_supporting / total_shops) ** 8
        probs[prod] = p_zero
    return probs


def shape(func: str, x: float, T: Optional[float] = None) -> float:
    """Exact implementation of kaggriculture.py:61-74."""
    x = max(0.0, float(x))
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


def get_price(product: str, inventory: float) -> int:
    """Calculate instantaneous spot price for a product given current market inventory.
    
    Exact implementation of kaggriculture.py:195-207.
    """
    p = MARKET_PARAMS[product]
    base = float(p["base"])
    i0 = float(p["I0"])
    T = float(p["T"])
    
    if inventory < i0:
        func = p["below_func"]
        target = float(p["below_target"])
        amp = target * base / shape(func, T, T)
        raw_price = base + amp * shape(func, i0 - inventory, T)
    else:
        func = p["above_func"]
        target = float(p["above_target"])
        amp = target * base / shape(func, T, T)
        raw_price = base - amp * shape(func, inventory - i0, T)

    return max(PRICE_FLOOR, int(round(raw_price)))


def calculate_realized_revenue(product: str, quantity: int, start_inventory: float = MARKET_I0) -> Tuple[float, float, float]:
    """Calculate total realized revenue when selling Q units sequentially (kaggriculture.py:596-597)."""
    if quantity <= 0:
        spot = get_price(product, start_inventory)
        return (0.0, float(spot), float(spot))

    total_revenue = 0.0
    cur_inv = start_inventory
    for _ in range(quantity):
        p = get_price(product, cur_inv)
        total_revenue += p
        cur_inv += 1.0

    final_price = get_price(product, cur_inv)
    avg_price = total_revenue / quantity
    return (total_revenue, avg_price, float(final_price))


def calculate_interleaved_revenue(product: str, my_quantity: int, opp_quantity: int, start_inventory: float = MARKET_I0) -> float:
    """Model concurrent interleaved sell flow between two players (kaggriculture.py:596-597)."""
    if my_quantity <= 0:
        return 0.0

    my_rev = 0.0
    cur_inv = start_inventory
    my_rem = my_quantity
    opp_rem = opp_quantity

    while my_rem > 0 or opp_rem > 0:
        if my_rem > 0:
            p = get_price(product, cur_inv)
            my_rev += p
            cur_inv += 1.0
            my_rem -= 1
        if opp_rem > 0:
            cur_inv += 1.0
            opp_rem -= 1

    return my_rev


def evaluate_endogenous_livestock_economics(wheat_market_price: float = 39.4, labor_cost_per_action: float = 1.0) -> Dict[str, Dict]:
    """Evaluate livestock unit economics comparing GROWN wheat vs BOUGHT wheat with tile & labor costs.
    
    References:
    - kaggriculture.py:804-839 schedule yields:
        Placed Day 0: GOOSE = 27, COW = 12, SHEEP = 9.
        Placed Day 1: GOOSE = 26, COW = 11, SHEEP = 8.
    - Feed: 1 wheat per day (GOOSE 27 days, COW 22 days, SHEEP 24 days).
    - Grown Feed cost:
        GOOSE: 7 wheat seeds ($70) + 35 labor actions ($35) = $105 total feed cost.
        COW: 6 wheat seeds ($60) + 30 labor actions ($30) = $90 total feed cost.
        SHEEP: 6 wheat seeds ($60) + 30 labor actions ($30) = $90 total feed cost.
    - Bought Feed cost:
        GOOSE: 27 * $39.4 = $1,063.8
        COW: 22 * $39.4 = $866.8
        SHEEP: 24 * $39.4 = $945.6
    """
    analysis = {}

    # 1. GOOSE / EGG (Day 0 placement -> 27 units yield, 27 feed days)
    egg_yield = calculate_exact_animal_yield("GOOSE", placed_day=0) # 27
    feed_grown_goose = (math.ceil(27 / 4) * 10) + (math.ceil(27 / 4) * 5 * labor_cost_per_action) # $70 seed + $35 labor = $105
    feed_bought_goose = 27 * wheat_market_price
    rev_base_egg, _, _ = calculate_realized_revenue("EGG", egg_yield, start_inventory=MARKET_I0)
    rev_glut_egg, _, _ = calculate_realized_revenue("EGG", egg_yield, start_inventory=MARKET_I0 + 200)

    analysis["GOOSE_EGG"] = {
        "capital_cost": 300,
        "lifetime_units_d0": egg_yield,
        "lifetime_units_d1": calculate_exact_animal_yield("GOOSE", placed_day=1), # 26
        "feed_days": 27,
        "feed_cost_grown": feed_grown_goose,
        "feed_cost_bought": feed_bought_goose,
        "base_rev": rev_base_egg,
        "glut_rev": rev_glut_egg,
        "net_profit_grown_base": rev_base_egg - 300 - feed_grown_goose,
        "net_profit_bought_base": rev_base_egg - 300 - feed_bought_goose,
        "net_profit_grown_glut": rev_glut_egg - 300 - feed_grown_goose,
        "net_profit_bought_glut": rev_glut_egg - 300 - feed_bought_goose,
    }

    # 2. COW / MILK (Day 0 placement -> 12 units yield, 22 feed days)
    milk_yield = calculate_exact_animal_yield("COW", placed_day=0) # 12
    feed_grown_cow = (math.ceil(22 / 4) * 10) + (math.ceil(22 / 4) * 5 * labor_cost_per_action) # $60 seed + $30 labor = $90
    feed_bought_cow = 22 * wheat_market_price
    rev_base_cow, _, _ = calculate_realized_revenue("MILK", milk_yield, start_inventory=MARKET_I0)
    rev_glut_cow, _, _ = calculate_realized_revenue("MILK", milk_yield, start_inventory=MARKET_I0 + 100)

    analysis["COW_MILK"] = {
        "capital_cost": 400,
        "lifetime_units_d0": milk_yield,
        "lifetime_units_d1": calculate_exact_animal_yield("COW", placed_day=1), # 11
        "feed_days": 22,
        "feed_cost_grown": feed_grown_cow,
        "feed_cost_bought": feed_bought_cow,
        "base_rev": rev_base_cow,
        "glut_rev": rev_glut_cow,
        "net_profit_grown_base": rev_base_cow - 400 - feed_grown_cow,
        "net_profit_bought_base": rev_base_cow - 400 - feed_bought_cow,
        "net_profit_grown_glut": rev_glut_cow - 400 - feed_grown_cow,
        "net_profit_bought_glut": rev_glut_cow - 400 - feed_bought_cow,
    }

    # 3. SHEEP / WOOL (Day 0 placement -> 9 units yield, 24 feed days)
    wool_yield = calculate_exact_animal_yield("SHEEP", placed_day=0) # 9
    feed_grown_sheep = (math.ceil(24 / 4) * 10) + (math.ceil(24 / 4) * 5 * labor_cost_per_action) # $60 seed + $30 labor = $90
    feed_bought_sheep = 24 * wheat_market_price
    rev_base_sheep, _, _ = calculate_realized_revenue("WOOL", wool_yield, start_inventory=MARKET_I0)
    rev_glut_sheep, _, _ = calculate_realized_revenue("WOOL", wool_yield, start_inventory=MARKET_I0 + 100)

    analysis["SHEEP_WOOL"] = {
        "capital_cost": 500,
        "lifetime_units_d0": wool_yield,
        "lifetime_units_d1": calculate_exact_animal_yield("SHEEP", placed_day=1), # 8
        "feed_days": 24,
        "feed_cost_grown": feed_grown_sheep,
        "feed_cost_bought": feed_bought_sheep,
        "base_rev": rev_base_sheep,
        "glut_rev": rev_glut_sheep,
        "net_profit_grown_base": rev_base_sheep - 500 - feed_grown_sheep,
        "net_profit_bought_base": rev_base_sheep - 500 - feed_bought_sheep,
        "net_profit_grown_glut": rev_glut_sheep - 500 - feed_grown_sheep,
        "net_profit_bought_glut": rev_glut_sheep - 500 - feed_bought_sheep,
    }

    return analysis


if __name__ == "__main__":
    print("=== EXACT ANIMAL SCHEDULE LIFETIME YIELDS (kaggriculture.py:804-839) ===")
    for animal in ("GOOSE", "COW", "SHEEP"):
        y0 = calculate_exact_animal_yield(animal, placed_day=0)
        y1 = calculate_exact_animal_yield(animal, placed_day=1)
        print(f"{animal:<6}: Placed Day 0 = {y0} units, Placed Day 1 = {y1} units")

    print("\n=== TOWN SHOP ZERO-DEMAND PROBABILITY TABLE (8 draws with replacement) ===")
    probs = compute_shop_zero_demand_probabilities()
    for prod, p_zero in sorted(probs.items(), key=lambda x: x[1]):
        print(f"{prod:<12}: P(zero shop demand) = {p_zero * 100:5.2f}%")

    print("\n=== LIVESTOCK ECONOMICS: GROWN FEED vs BOUGHT FEED ($39.4/WHEAT) ===")
    econ = evaluate_endogenous_livestock_economics()
    for name, stats in econ.items():
        print(f"\n[{name}] Capital=${stats['capital_cost']}, Yield(D0)={stats['lifetime_units_d0']} units, FeedDays={stats['feed_days']}")
        print(f"  Grown Feed Net (Base): +${stats['net_profit_grown_base']:,.1f}  |  Bought Feed Net (Base): ${stats['net_profit_bought_base']:,.1f}")
        print(f"  Grown Feed Net (Glut): +${stats['net_profit_grown_glut']:,.1f}  |  Bought Feed Net (Glut): ${stats['net_profit_bought_glut']:,.1f}")
