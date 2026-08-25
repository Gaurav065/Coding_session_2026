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
    steps_left = EPISODE_STEPS - step
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
