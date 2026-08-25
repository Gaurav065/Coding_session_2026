import json
import pandas as pd
from collections import defaultdict

file_path = r'C:\Users\GauravPatel\Downloads\95878419.json'
with open(file_path, 'r') as fp:
    data = json.load(fp)

steps = data['steps']
p0_final = steps[-1][0]['reward']
p1_final = steps[-1][1]['reward']

print("="*70)
print(f"MATCH FORENSIC REPORT: 95878419.json (3 PIZZA SHOPS UNLOCKED)")
print(f"Final Outcome: P0 (Aegis) = {p0_final:,.0f} vs P1 (Opponent) = {p1_final:,.0f} | Margin = +{p0_final-p1_final:,.0f}")
print("="*70)

# 1. Shop Unlocks Timeline
print("\n--- 1. TOWN SHOP UNLOCK TIMELINE ---")
shops_timeline = []
prev_shops = []
for step_idx, step in enumerate(steps):
    shops = step[0]['observation']['town']['unlocked_shops']
    if len(shops) > len(prev_shops):
        new_shop = shops[-1]
        day = step[0]['observation']['day']
        hour = step[0]['observation']['hour']
        print(f"Day {day:02d} (Step {step_idx:03d}, Hour {hour:02d}): Unlocked {new_shop:16s} | Total Active Shops: {len(shops)}")
        shops_timeline.append((day, step_idx, new_shop))
        prev_shops = list(shops)

# 2. Production & Sells Tracking
p0_sells = defaultdict(int)
p1_sells = defaultdict(int)
p0_revenue = defaultdict(float)
p1_revenue = defaultdict(float)
p0_crops = defaultdict(int)
p1_crops = defaultdict(int)
p0_animals = defaultdict(int)
p1_animals = defaultdict(int)
p0_fert_collected = 0
p1_fert_collected = 0

prev_p0_money = 3000.0
prev_p1_money = 3000.0

for step_idx, step in enumerate(steps):
    obs0 = step[0]['observation']
    act0 = step[0].get('action') or {}
    act1 = step[1].get('action') or {}
    prices = obs0['market']['prices']
    
    # Farmer & hands actions
    for a in [act0.get('farmer', [])] + (act0.get('hands', []) or []):
        if isinstance(a, list) and len(a) > 0:
            if a[0] == 'PLANT' and len(a) > 1: p0_crops[a[1]] += 1
            elif a[0] in ('BUILD_COOP', 'BUILD_PASTURE'): p0_animals[a[0]] += 1
            elif a[0] == 'COLLECT_FERTILIZER': p0_fert_collected += 1

    for a in [act1.get('farmer', [])] + (act1.get('hands', []) or []):
        if isinstance(a, list) and len(a) > 0:
            if a[0] == 'PLANT' and len(a) > 1: p1_crops[a[1]] += 1
            elif a[0] in ('BUILD_COOP', 'BUILD_PASTURE'): p1_animals[a[0]] += 1
            elif a[0] == 'COLLECT_FERTILIZER': p1_fert_collected += 1

    # Sells & revenue
    for m in act0.get('market', []) or []:
        if isinstance(m, list) and len(m) >= 3 and m[0] == 'SELL':
            item = m[1]
            qty = int(m[2]) if str(m[2]).isdigit() else 1
            p0_sells[item] += qty
            p0_revenue[item] += qty * prices.get(item, 1)

    for m in act1.get('market', []) or []:
        if isinstance(m, list) and len(m) >= 3 and m[0] == 'SELL':
            item = m[1]
            qty = int(m[2]) if str(m[2]).isdigit() else 1
            p1_sells[item] += qty
            p1_revenue[item] += qty * prices.get(item, 1)

print("\n--- 2. COMMODITY EXTRACTION & REALIZATION (P0 vs P1) ---")
all_items = sorted(set(list(p0_sells.keys()) + list(p1_sells.keys())))
print(f"{'Item':12s} | {'P0 Sold':>8s} | {'P0 Avg Price':>12s} | {'P0 Revenue':>12s} | {'P1 Sold':>8s} | {'P1 Avg Price':>12s} | {'P1 Revenue':>12s}")
print("-" * 80)
for item in all_items:
    q0 = p0_sells[item]
    r0 = p0_revenue[item]
    avg0 = (r0 / q0) if q0 > 0 else 0.0

    q1 = p1_sells[item]
    r1 = p1_revenue[item]
    avg1 = (r1 / q1) if q1 > 0 else 0.0
    print(f"{item:12s} | {q0:8d} | ${avg0:11.1f} | ${r0:11.1f} | {q1:8d} | ${avg1:11.1f} | ${r1:11.1f}")

# 3. Market Price Progression Across Days
print("\n--- 3. PRICE EVOLUTION ACROSS DAYS (KEY COMMODITIES) ---")
print(f"{'Day':4s} | {'MILK':>6s} | {'TOMATO':>6s} | {'WHEAT':>6s} | {'WOOL':>6s} | {'STRAWBERRY':>10s} | {'FERTILIZER':>10s} | {'Active Shops'}")
print("-" * 85)
for day in range(0, 30, 2):
    step_idx = day * 24
    obs = steps[step_idx][0]['observation']
    pr = obs['market']['prices']
    active_shops = len(obs['town']['unlocked_shops'])
    print(f"Day {day:02d} | ${pr.get('MILK',0):5d} | ${pr.get('TOMATO',0):5d} | ${pr.get('WHEAT',0):5d} | ${pr.get('WOOL',0):5d} | ${pr.get('STRAWBERRY',0):9d} | ${pr.get('FERTILIZER',0):9d} | {active_shops} shops")
