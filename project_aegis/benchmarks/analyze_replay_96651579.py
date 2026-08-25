import json
import os
from collections import defaultdict

replay_path = r'C:\Users\GauravPatel\Downloads\aegis_v4\wins\96651579.json'

with open(replay_path, 'r', encoding='utf-8') as f:
    replay = json.load(f)

info = replay.get('info', {})
teams = info.get('TeamNames', ['P0', 'P1'])
steps = replay['steps']

# Final rewards
p0_reward = steps[-1][0]['reward']
p1_reward = steps[-1][1]['reward']

aegis_seat = 0 if 'Shadow' in teams[0] or 'Aegis' in teams[0] else (1 if 'Shadow' in teams[1] or 'Aegis' in teams[1] else 0)
opp_seat = 1 - aegis_seat

aegis_name = teams[aegis_seat]
opp_name = teams[opp_seat]

aegis_score = steps[-1][aegis_seat]['reward']
opp_score = steps[-1][opp_seat]['reward']
margin = aegis_score - opp_score

print("=" * 80)
print(f"FORENSIC MATCH ANALYSIS: {os.path.basename(replay_path)}")
print("=" * 80)
print(f"Aegis Team:     {aegis_name} (Seat {aegis_seat}) -> ${aegis_score:,.0f}")
print(f"Opponent Team:  {opp_name} (Seat {opp_seat}) -> ${opp_score:,.0f}")
print(f"Victory Margin: +${margin:,.0f}")

# Unlocked shops
final_obs = steps[-1][0]['observation']
shops = final_obs.get('town', {}).get('unlocked_shops', [])
print(f"\nTown Shops Rolled ({len(shops)}): {shops}")

# Track infrastructure
final_aegis_farm = final_obs['farms'][aegis_seat]
final_opp_farm = final_obs['farms'][opp_seat]

print(f"\nInfrastructure Comparison:")
print(f"  Aegis Unlocked Quadrants:    {final_aegis_farm.get('unlocked_quadrants', [])}")
print(f"  Opponent Unlocked Quads:     {final_opp_farm.get('unlocked_quadrants', [])}")

# Animal count
aegis_animals = defaultdict(int)
for row in final_aegis_farm.get('tiles', []):
    for t in row or []:
        if isinstance(t, dict) and t.get('animal'):
            aegis_animals[t['animal']] += 1

opp_animals = defaultdict(int)
for row in final_opp_farm.get('tiles', []):
    for t in row or []:
        if isinstance(t, dict) and t.get('animal'):
            opp_animals[t['animal']] += 1

print(f"  Aegis Animals:               {dict(aegis_animals)}")
print(f"  Opponent Animals:            {dict(opp_animals)}")

# Analyze fulfilled sales and market revenue (capped at 100/order)
aegis_sales = defaultdict(int)
aegis_rev = defaultdict(float)
opp_sales = defaultdict(int)
opp_rev = defaultdict(float)

# Track crop harvests
aegis_harvests = defaultdict(int)
opp_harvests = defaultdict(int)

for s_idx, s in enumerate(steps):
    obs = s[0]['observation']
    prices = obs.get('market', {}).get('prices', {})
    
    # Check actions
    a_act = s[aegis_seat].get('action') or {}
    o_act = s[opp_seat].get('action') or {}
    
    # Aegis sells
    for m in a_act.get('market', []) or []:
        if isinstance(m, list) and len(m) >= 3 and m[0] == 'SELL':
            item = m[1]
            qty = min(int(m[2]) if str(m[2]).isdigit() else 1, 100)
            p = prices.get(item, 1)
            aegis_sales[item] += qty
            aegis_rev[item] += qty * p

    # Opponent sells
    for m in o_act.get('market', []) or []:
        if isinstance(m, list) and len(m) >= 3 and m[0] == 'SELL':
            item = m[1]
            qty = min(int(m[2]) if str(m[2]).isdigit() else 1, 100)
            p = prices.get(item, 1)
            opp_sales[item] += qty
            opp_rev[item] += qty * p

print("\n" + "-" * 80)
print(f"{'PRODUCT':<15} | {'AEGIS QTY':<10} | {'AEGIS REV':<12} | {'OPP QTY':<10} | {'OPP REV':<12} | {'DIFF REV':<12}")
print("-" * 80)

all_items = sorted(list(set(list(aegis_sales.keys()) + list(opp_sales.keys()))))
for item in all_items:
    aq = aegis_sales[item]
    ar = aegis_rev[item]
    oq = opp_sales[item]
    opr = opp_rev[item]
    diff = ar - opr
    print(f"{item:<15} | {aq:<10} | ${ar:>10,.0f} | {oq:<10} | ${opr:>10,.0f} | {diff:>+11,.0f}")

print("-" * 80)
print(f"{'TOTALS':<15} | {sum(aegis_sales.values()):<10} | ${sum(aegis_rev.values()):>10,.0f} | {sum(opp_sales.values()):<10} | ${sum(opp_rev.values()):>10,.0f} | {sum(aegis_rev.values())-sum(opp_rev.values()):>+11,.0f}")
print("=" * 80)
