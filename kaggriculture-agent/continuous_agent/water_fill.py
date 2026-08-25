
import numpy as np
import heapq

MARKET_I0 = 10000
PRICE_FLOOR = 1.0

SHAPES = {
    "linear": lambda x: np.maximum(x, 0),
    "sq":     lambda x: np.maximum(x, 0) ** 2,
    "sqrt":   lambda x: np.sqrt(np.maximum(x, 0)),
    "log":    lambda x: np.log1p(np.maximum(x, 0))
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
    """Full two-branch AMM price, matching kaggriculture.py's market_price exactly.
    price_above() used to silently return flat `base` for any inv <= I0 (every SHAPES
    entry maps 0 -> 0), which flattened real below-I0 scarcity pricing to baseline and
    biased the allocator away from under-supplied items -- the opposite of what a
    diversification water-fill is for. Both branches are needed."""
    if inv < I0:
        amp = below_target * base / SHAPES[below_func](T)
        return max(PRICE_FLOOR, base + amp * SHAPES[below_func](I0 - inv))
    amp = above_target * base / SHAPES[above_func](T)
    return max(PRICE_FLOOR, base - amp * SHAPES[above_func](inv - I0))

def water_fill_allocate(items, capacity):
    for name, p in items.items():
        if p["cost"] <= 0:
            # used += cost would never advance with cost <= 0, spinning this loop
            # forever -- fatal for an overnight CMA-ES driver that calls this a lot.
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

    return {n: s["units"] for n, s in state.items()}

# Example test:
if __name__ == "__main__":
    # WARNING: cost=1 for every item below is a PLACEHOLDER, not a real production-cost
    # model -- it makes the allocator rank purely by raw price (a $250 melon and a $25
    # wheat unit cost the same to produce), which is not a meaningful answer. Replace
    # with real farmer-turn/land/feed cost per unit before trusting this for the
    # overnight CMA-ES run. inv0 values below are set away from I0 on purpose (not all
    # exactly at MARKET_I0 as before) so this demo actually exercises the below-I0
    # branch of market_price() rather than masking it, as the previous demo did.
    items = {
        "STRAWBERRY": {**PRODUCTS["STRAWBERRY"], "inv0": MARKET_I0 + 3000, "cost": 1},
        "MELON": {**PRODUCTS["MELON"], "inv0": MARKET_I0 + 0, "cost": 1},
        "MILK": {**PRODUCTS["MILK"], "inv0": MARKET_I0 - 500, "cost": 1},
        "WOOL": {**PRODUCTS["WOOL"], "inv0": MARKET_I0 - 200, "cost": 1},
    }
    alloc = water_fill_allocate(items, 1500)
    print("Optimal 1500-unit distribution:", alloc)

