import math
def unified_alloc(st, plan, cand, animal_cand, empties, budget, head, pipeline, wheat_price_buy, current_hands, dl, coops_free, pastures_free, owned, have, crop_counts, P, CROPS):
    def get_fib_cost(n):
        return n # dummy
    effective_work_per_hand = 13.0
    
    global_cand = []
    for item in cand:
        mav, crop, units, room, prof, occ, acts = item
        if crop == "WHEAT":
            continue
        global_cand.append((mav, "CROP", item))
        
    if st.day <= P["stop_animals_day"]:
        for item in animal_cand:
            action_val, kind, per, a, net = item
            global_cand.append((action_val, "ANIMAL", item))
            
    global_cand.sort(reverse=True, key=lambda z: z[0])
    
    crop_targets = {}
    want = dict(have)
    tile_room = len(empties) + coops_free + pastures_free
    total = owned
    
    for entry in global_cand:
        if entry[1] == "CROP":
            mav, crop, units, room, prof, occ, acts = entry[2]
            by_market = int(room // max(1, units)) + 1
            by_cash = int(budget // CROPS[crop]["seed"])
            take = min(tile_room, max(min(by_market, by_cash), st.seeds.get(crop, 0)))
            if take <= 0: continue
            crop_targets[crop] = take
            budget -= max(0, take - st.seeds.get(crop, 0)) * CROPS[crop]["seed"]
            tile_room -= take
        elif entry[1] == "ANIMAL":
            action_val, kind, per, a, net = entry[2]
            added_hands_for_animal = 2.8 / effective_work_per_hand
            marginal_labor_cost_animal = (get_fib_cost(current_hands + added_hands_for_animal) - get_fib_cost(current_hands)) * dl
            if net < marginal_labor_cost_animal: continue
            
            room = head[a["prod"]] - pipeline[a["prod"]]
            by_market = int(room // max(1, per))
            unit_cost = a["cost"] + 5 * wheat_price_buy
            by_cash = int(budget // unit_cost)
            
            n = min(by_market, by_cash, tile_room)
            if kind == "GOOSE": n = min(n, P["max_geese"] - have["GOOSE"])
            if kind == "SHEEP": n = min(n, 4 - have["SHEEP"])
            n = min(n, P["max_animals"] - total)
            if n <= 0: continue
            
            want[kind] += n
            budget -= n * a["cost"]
            tile_room -= n
            total += n
            current_hands += n * added_hands_for_animal
            
    if total > 0 and dl >= 4 and tile_room > 0:
        need = int(math.ceil(total * P["wheat_tiles_per_animal"])) - crop_counts.get("WHEAT", 0)
        n = max(0, min(need, tile_room, int(budget // CROPS["WHEAT"]["seed"])))
        if n > 0:
            crop_targets["WHEAT"] = n
            budget -= n * CROPS["WHEAT"]["seed"]
            tile_room -= n
            
    wheat_item = None
    for item in cand:
        if item[1] == "WHEAT":
            wheat_item = item
            break
            
    if wheat_item and tile_room > 0:
        mav, crop, units, room, prof, occ, acts = wheat_item
        by_market = int(room // max(1, units)) + 1
        by_cash = int(budget // CROPS[crop]["seed"])
        take = min(tile_room, max(min(by_market, by_cash), st.seeds.get(crop, 0)))
        if take > 0:
            crop_targets[crop] = crop_targets.get(crop, 0) + take
            budget -= max(0, take - st.seeds.get(crop, 0)) * CROPS[crop]["seed"]
            tile_room -= take
