import sys
import re

with open('version_beta/main.py', 'r') as f:
    content = f.read()

# We need to replace the entire build_plan function.
# It starts at 'def build_plan(st):' and ends before 'def wheat_keep(st, plan):'
start_idx = content.find('def build_plan(st):')
end_idx = content.find('def wheat_keep(st, plan):')

if start_idx == -1 or end_idx == -1:
    print('Could not find build_plan or wheat_keep')
    sys.exit(1)

new_build_plan = '''def get_fib_cost(n):
    if n <= 0: return 0.0
    s, a, b = 0.0, 1.0, 1.0
    for _ in range(int(math.ceil(n))):
        s += a
        a, b = b, a + b
    return s

def build_plan(st):
    dl = st.days_left
    rate = town_rates(st)
    scale = reserve_scale(st.day)
    reserve = {}
    head = {}
    for p in PRODUCTS:
        r = max(1, int(P["res_" + p] * scale)) if scale > 0 else 1
        reserve[p] = r
        head[p] = units_sellable(p, st.minv[p], r, 900) + int(rate[p] * dl * P["opp_share"])

    plan = {"reserve": reserve, "head": head, "rate": rate}

    pipeline = dict((p, 0.0) for p in PRODUCTS)
    counts = {"GOOSE": 0, "COW": 0, "SHEEP": 0}
    coops_free = 0
    pastures_free = 0
    empties = []
    weeds = []
    crop_tiles = 0
    crop_counts = {}
    for y in range(st.n):
        row = st.tiles[y]
        for x in range(st.n):
            t = row[x]
            if t is None:
                empties.append((x, y))
                continue
            if t == "LOCKED" or not isinstance(t, dict):
                continue
            k = t.get("kind")
            if k == "WEED":
                weeds.append((x, y))
            elif k == "PLANT":
                crop_tiles += 1
                crop_counts[t["crop"]] = crop_counts.get(t["crop"], 0) + 1
                c = CROPS[t["crop"]]
                if c["ongoing"]:
                    age = st.day - t["planted_day"]
                    done = 0 if age < c["first"] else (age - c["first"]) // c["interval"] + 1
                    pipeline[t["crop"]] += max(0, c["cap"] - done) * 2
                else:
                    pipeline[t["crop"]] += c["cap"]
            elif k in ("COOP", "PASTURE"):
                a = t.get("animal")
                if a is None:
                    if k == "COOP":
                        coops_free += 1
                    else:
                        pastures_free += 1
                else:
                    counts[a] += 1
                    ad = ANIMALS[a]
                    wait = max(0, ad["first"] - (st.day - t["placed_day"]))
                    left = dl - wait
                    nprod = 0 if left < 0 else left // ad["interval"] + 1
                    pipeline[ad["prod"]] += nprod * (1 + ad["interval"])

    plan["empties"] = empties
    plan["weeds"] = weeds
    plan["counts"] = counts
    plan["coops_free"] = coops_free
    plan["pastures_free"] = pastures_free
    animals_now = counts["GOOSE"] + counts["COW"] + counts["SHEEP"]
    plan["animals"] = animals_now
    have = dict((k, counts[k] + st.shed.get(k, 0)) for k in ANIMALS)
    owned = have["GOOSE"] + have["COW"] + have["SHEEP"]

    wheat_price_buy = market_price("WHEAT", st.minv["WHEAT"] - 1)
    feed_reserve = min(2600.0, owned * P["feed_reserve_days"] * wheat_price_buy)
    plan["feed_reserve"] = feed_reserve
    budget = max(0.0, st.money - feed_reserve) * P["invest_frac"]

    # ---- dynamic crop value and MAV --------------------------------------
    cand = []
    feed_need = (owned + dl * 1.5) * dl  # rough estimate
    for crop in CROPS:
        pr = st.prices[crop]
        if crop == "WHEAT":
            pr = max(pr, min(wheat_price_buy, P["max_wheat_price"]))
        r = crop_plan_value(crop, st, pr)
        if r is None: continue
        units, occ, acts, profit = r
        if profit <= 0: continue
        room = head[crop] - pipeline[crop]
        if crop == "WHEAT": room = max(room, feed_need)
        if room < units * 0.5: continue
        
        # MAV = Marginal Action Value (profit per action)
        mav = profit / float(acts)
        cand.append((mav, crop, units, room, profit, occ, acts))
        
    cand.sort(reverse=True, key=lambda z: z[0])
    best_crop_action_val = cand[0][0] if cand else 0.0

    animal_cand = []
    for kind, a in ANIMALS.items():
        per = animal_units(kind, dl)
        if per <= 0: continue
        price = max(st.prices[a["prod"]], reserve[a["prod"]])
        gross = per * price * P["yield_haircut"]
        feed = dl * wheat_price_buy
        net = gross - a["cost"] - feed
        if net <= 0: continue
        
        acts_per_day = 1.0 + (1.0 / a["interval"]) + (1.0 / a["interval"])
        total_acts = dl * acts_per_day
        action_val = net / total_acts
        animal_cand.append((action_val, kind, per, a, net))
        
    animal_cand.sort(reverse=True, key=lambda z: z[0])
    best_animal_action_val = animal_cand[0][0] if animal_cand else 0.0
    
    MAV = max(best_crop_action_val, best_animal_action_val)
    if MAV <= 0: MAV = 10.0

    pending = coops_free + pastures_free + len(weeds)
    current_work = (animals_now * 2.8 + crop_tiles * 1.5 + pending * 1.7 + 10)
    current_hands = current_work / P["work_per_hand"]

    # ---- dynamic land: evaluate ROI of 25 new tiles ----------------------
    nq = len(st.unlocked) - 1
    plan["buy_land"] = False
    if nq < 3 and dl >= 5:
        cost = (1000, 2000, 4000)[nq]
        usable_tiles = len(empties) + len(weeds)
        crowded = usable_tiles <= P["land_slack"] or nq == 0
        if crowded and budget >= cost:
            if cand:
                _, _, _, _, best_profit, best_occ, best_acts = cand[0]
                expected_cycles = max(0.5, dl / float(best_occ))
                marginal_revenue = 25 * best_profit * expected_cycles
                
                added_actions_per_day = 25 * (best_acts / float(best_occ))
                added_hands = added_actions_per_day / P["work_per_hand"]
                
                current_daily_labor_cost = get_fib_cost(current_hands)
                new_daily_labor_cost = get_fib_cost(current_hands + added_hands)
                marginal_labor_cost = (new_daily_labor_cost - current_daily_labor_cost) * dl
                
                if marginal_revenue > marginal_labor_cost + cost:
                    plan["buy_land"] = True
                    budget -= cost
            elif nq == 0:
                plan["buy_land"] = True
                budget -= cost

    # ---- dynamic animal targets ------------------------------------------
    want = dict(have)
    tile_room = len(empties) + coops_free + pastures_free
    total = owned
    if st.day <= P["stop_animals_day"]:
        for action_val, kind, per, a, net in animal_cand:
            added_hands_for_animal = 2.8 / P["work_per_hand"]
            marginal_labor_cost_animal = (get_fib_cost(current_hands + added_hands_for_animal) - get_fib_cost(current_hands)) * dl
            
            # If the animal's net profit over the season doesn't even cover the marginal labor cost, skip it!
            if net < marginal_labor_cost_animal:
                continue

            room = head[a["prod"]] - pipeline[a["prod"]]
            by_market = int(room // max(1, per))
            unit_cost = a["cost"] + dl * wheat_price_buy * 0.45
            by_cash = int(budget // unit_cost)
            
            n = min(by_market, by_cash, tile_room)
            if kind == "GOOSE": n = min(n, P["max_geese"] - have["GOOSE"])
            if n <= 0: continue
            
            want[kind] += n
            budget -= n * a["cost"]
            tile_room -= n
            total += n
            current_hands += n * added_hands_for_animal
    plan["want"] = want

    # ---- structures ------------------------------------------------------
    need_coops = max(0, want["GOOSE"] - counts["GOOSE"] - coops_free)
    need_past = max(0, want["COW"] + want["SHEEP"] - counts["COW"] - counts["SHEEP"] - pastures_free)
    slack = sum(st.shed.get(k, 0) for k in ANIMALS) + 2
    plan["build_coops"] = min(need_coops, slack, len(empties))
    plan["build_pastures"] = min(need_past, slack, max(0, len(empties) - plan["build_coops"]))

    ctr = (st.half - 0.5, st.half - 0.5)
    empties.sort(key=lambda p: abs(p[0] - ctr[0]) + abs(p[1] - ctr[1]))
    nb = plan["build_coops"] + plan["build_pastures"]
    plan["coop_sites"] = set(empties[:plan["build_coops"]])
    plan["pasture_sites"] = set(empties[plan["build_coops"]:nb])

    # ---- dynamic crop planting (space filling) ---------------------------
    free_for_crops = max(0, len(empties) - nb)
    feed_need = (total + want["GOOSE"] + want["COW"] + want["SHEEP"]) * dl
    
    # Re-sort cand by profit/occupancy for space efficiency
    cand_space = [(prof / float(occ), crop, units, room, prof, occ, acts) for mav, crop, units, room, prof, occ, acts in cand]
    cand_space.sort(reverse=True, key=lambda z: z[0])
    
    crop_targets = {}
    left = free_for_crops
    seed_budget = budget

    if total > 0 and dl >= 4 and left > 0:
        need = int(math.ceil(total * P["wheat_tiles_per_animal"])) - crop_counts.get("WHEAT", 0)
        n = max(0, min(need, left, int(seed_budget // CROPS["WHEAT"]["seed"])))
        if n > 0:
            crop_targets["WHEAT"] = n
            seed_budget -= n * CROPS["WHEAT"]["seed"]
            left -= n
            
    for _, crop, units, room, prof, occ, acts in cand_space:
        if left <= 0: break
        if crop in crop_targets: continue
        by_market = int(room // max(1, units)) + 1
        by_cash = int(seed_budget // CROPS[crop]["seed"])
        take = min(left, max(min(by_market, by_cash), st.seeds.get(crop, 0)))
        if take <= 0: continue
        crop_targets[crop] = take
        seed_budget -= max(0, take - st.seeds.get(crop, 0)) * CROPS[crop]["seed"]
        left -= take
        
    for crop, n in st.seeds.items():
        if n > 0 and crop not in crop_targets and left > 0:
            crop_targets[crop] = min(n, left)
            left -= crop_targets[crop]
    plan["crop_targets"] = crop_targets
    plan["plant_sites"] = [p for p in empties if p not in plan["coop_sites"] and p not in plan["pasture_sites"]]

    # ---- dynamic labour budgeting ----------------------------------------
    pending_tasks = plan["build_coops"] + plan["build_pastures"] + len(weeds)
    pending_tasks += sum(crop_targets.values())
    work = (total * 2.8 + crop_tiles * 1.5 + pending_tasks * 1.7 + 10)
    by_work = int(math.ceil(work / P["work_per_hand"]))
    
    hand_cash = max(P["hand_budget"], st.money * P["hand_budget_frac"])
    n, spend, a, b = 0, 0.0, 1, 1
    while True:
        if spend + a > hand_cash:
            break
        # DYNAMIC CAP: Does this hand cost more than the value of the actions they provide?
        if a > MAV * P["work_per_hand"] * 0.85: # 15% safety margin on labor value
            break
        spend += a
        n += 1
        a, b = b, a + b
        
    plan["hands"] = max(0, min(n, by_work)) # No max_hands cap!
    return plan

'''

new_content = content[:start_idx] + new_build_plan + content[end_idx:]

with open('version_beta/main.py', 'w') as f:
    f.write(new_content)

print('Successfully applied dynamic update to beta/main.py')
