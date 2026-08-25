
# Kaggriculture Architecture V4 Review

Claude, following your phenomenal architectural audit, we have completely scrapped the "Town Shop 1.5x Premium" hallucination and the Poisson-Binomial DP Replanner. 
We have now implemented the true AMM Water-Filling strategy and the exact AMM marginal price heuristic you proposed.

We have two new files. Before we run our CMA-ES macro generation overnight and package this into a final Kaggle submission, we need you to review these two scripts for any fatal mathematical or game-engine logic bugs.

## 1. water_fill.py
This script calculates the optimal production volume targets using the AMM above-branch formulas directly extracted from the `kaggriculture.py` engine.

```python
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

def price_above(inv, base, I0, T, above_target, shape_name):
    amp = above_target * base / SHAPES[shape_name](T)
    return max(PRICE_FLOOR, base - amp * SHAPES[shape_name](max(inv - I0, 0)))

def water_fill_allocate(items, capacity):
    heap, state, used = [], {}, 0.0
    for name, p in items.items():
        state[name] = {"inv": p["inv0"], "units": 0}
        price0 = price_above(p["inv0"], p["base"], p["I0"], p["T"], p["above_target"], p["above_func"])
        heapq.heappush(heap, (-price0 / p["cost"], name))
    
    while heap and used < capacity:
        neg_mp, name = heapq.heappop(heap)
        p, cost = items[name], items[name]["cost"]
        if used + cost > capacity: continue
            
        price = price_above(state[name]["inv"], p["base"], p["I0"], p["T"], p["above_target"], p["above_func"])
        state[name]["units"] += 1
        used += cost
        
        if price > 1.0: state[name]["inv"] += 1
            
        next_price = price_above(state[name]["inv"], p["base"], p["I0"], p["T"], p["above_target"], p["above_func"])
        heapq.heappush(heap, (-next_price / cost, name))
        
    return {n: s["units"] for n, s in state.items()}
```

## 2. draft_main_v4.py
This is the new live online agent. It runs the precomputed tape, but its Replanner now scores front-running using the `sell_proceeds` function and checks the exact expected Town Shop drain to see if it should wait for scarcity.

[Please review the functions `sell_proceeds()`, `forecast_shop_drain()`, and `compute_score()` in the agent code to ensure they correctly represent the mechanics.]

Please provide your review, highlighting any edge cases we missed (e.g. integer math vs floats in the AMM curve) before we package this up!

