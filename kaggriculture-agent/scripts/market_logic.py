def fib(n):
    if n <= 1: return 1
    a, b = 1, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

def should_buy_land(shadow_price_lambda, steps_left, extra_tiles_unlocked, land_price):
    expected_value = shadow_price_lambda * extra_tiles_unlocked * (steps_left / EPISODE_STEPS)
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
    steps_left = EPISODE_STEPS - step
    
    orders = []
    for item, qty in private.get("shed", {}).items():
        if qty <= 0: continue
        inv0 = market_inv.get(item, MARKET_I0)
        proceeds_now = sell_proceeds(inv0, qty, item)
        
        drain = forecast_shop_drain(item, unlocked_shops, steps_left)
        inv_later = max(MARKET_I0, inv0 - drain)
        proceeds_later = sell_proceeds(inv_later, qty, item)
        
        if proceeds_now >= proceeds_later or step >= EPISODE_STEPS - 24:
            orders.append(["SELL", item, qty])
            
    return orders
