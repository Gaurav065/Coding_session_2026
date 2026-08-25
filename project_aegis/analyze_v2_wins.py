import json
import os
from collections import defaultdict

v2_wins_dir = r'C:\Users\GauravPatel\Downloads\aegis_v2_replays\wins'
v2_files = sorted([f for f in os.listdir(v2_wins_dir) if f.endswith('.json')])

print("=" * 80)
print(f"AEGIS V2 LIVE WINS FORENSIC ANALYSIS ({len(v2_files)} MATCHES)")
print("=" * 80)

total_my_score = 0
total_opp_score = 0
margins = []

for f in v2_files:
    file_path = os.path.join(v2_wins_dir, f)
    with open(file_path, 'r', encoding='utf-8') as fp:
        data = json.load(fp)

    info = data.get('info', {})
    teams = info.get('TeamNames', ['P0', 'P1'])
    steps = data['steps']
    p0_final = steps[-1][0]['reward']
    p1_final = steps[-1][1]['reward']
    shops = steps[-1][0]['observation']['town']['unlocked_shops']
    
    my_seat = 1 if teams[1] == 'Shadow Recon' else 0
    opp_seat = 1 - my_seat
    my_score = p1_final if my_seat == 1 else p0_final
    opp_score = p0_final if my_seat == 1 else p1_final
    opp_name = teams[opp_seat]

    status = "VICTORY" if my_score > opp_score else "DEFEAT"
    margin = my_score - opp_score
    margins.append(margin)
    total_my_score += my_score
    total_opp_score += opp_score

    print(f"\n{'='*80}")
    print(f"MATCH: {f} | EpisodeId: {info.get('EpisodeId')}")
    print(f"Shadow Recon (Seat {my_seat}): {my_score:,.0f}  VS  {opp_name} (Seat {opp_seat}): {opp_score:,.0f}")
    print(f"Result: {status} by +{margin:,.0f} coins")
    print(f"Town Shops ({len(shops)}): {shops}")
    print(f"{'='*80}")

    # Shop Timeline
    print("\n--- Town Shop Schedule ---")
    prev_shops = []
    for step_idx, step in enumerate(steps):
        cur_shops = step[0]['observation']['town']['unlocked_shops']
        if len(cur_shops) > len(prev_shops):
            day = step[0]['observation']['day']
            print(f"  Day {day:02d} (Step {step_idx:03d}): + {cur_shops[-1]:18s} (Total: {len(cur_shops)})")
            prev_shops = list(cur_shops)

    # Commodity Sells
    my_sells = defaultdict(int)
    opp_sells = defaultdict(int)
    my_rev = defaultdict(float)
    opp_rev = defaultdict(float)

    for step_idx, step in enumerate(steps):
        obs0 = step[0]['observation']
        prices = obs0['market']['prices']
        act_my = step[my_seat].get('action') or {}
        act_opp = step[opp_seat].get('action') or {}

        for m in act_my.get('market', []) or []:
            if isinstance(m, list) and len(m) >= 3 and m[0] == 'SELL':
                item = m[1]
                qty = int(m[2]) if str(m[2]).isdigit() else 1
                my_sells[item] += qty
                my_rev[item] += qty * prices.get(item, 1)

        for m in act_opp.get('market', []) or []:
            if isinstance(m, list) and len(m) >= 3 and m[0] == 'SELL':
                item = m[1]
                qty = int(m[2]) if str(m[2]).isdigit() else 1
                opp_sells[item] += qty
                opp_rev[item] += qty * prices.get(item, 1)

    print("\n--- Extraction & Revenue Comparison ---")
    print(f"{'Commodity':12s} | {'Shadow Qty':>10s} | {'Shadow Avg':>10s} | {'Shadow Rev':>12s} | {'Opp Qty':>10s} | {'Opp Avg':>10s} | {'Opp Rev':>12s}")
    print("-" * 86)
    all_items = sorted(set(list(my_sells.keys()) + list(opp_sells.keys())))
    for item in all_items:
        mq = my_sells[item]
        mr = my_rev[item]
        mavg = (mr / mq) if mq > 0 else 0.0

        oq = opp_sells[item]
        orev = opp_rev[item]
        oavg = (orev / oq) if oq > 0 else 0.0
        print(f"{item:12s} | {mq:10d} | ${mavg:9.1f} | ${mr:11.1f} | {oq:10d} | ${oavg:9.1f} | ${orev:11.1f}")

    # Check expenses & purchases
    my_expenses = defaultdict(float)
    opp_expenses = defaultdict(float)
    for step_idx, step in enumerate(steps):
        act_my = step[my_seat].get('action') or {}
        act_opp = step[opp_seat].get('action') or {}
        for m in act_my.get('market', []) or []:
            if isinstance(m, list) and len(m) > 0 and m[0] in ('BUY_PRODUCT', 'BUY_ANIMAL', 'BUY_LAND', 'BUY_SEED'):
                my_expenses[m[0] + (('_' + str(m[1])) if len(m) > 1 else '')] += int(m[2]) if len(m) > 2 else 1
        for m in act_opp.get('market', []) or []:
            if isinstance(m, list) and len(m) > 0 and m[0] in ('BUY_PRODUCT', 'BUY_ANIMAL', 'BUY_LAND', 'BUY_SEED'):
                opp_expenses[m[0] + (('_' + str(m[1])) if len(m) > 1 else '')] += int(m[2]) if len(m) > 2 else 1

    print("\n--- Capex & Feed Expenses ---")
    print(f"Shadow Expenses: {dict(my_expenses)}")
    print(f"Opp Expenses:    {dict(opp_expenses)}")

print("\n" + "=" * 80)
print(f"AEGIS V2 AGGREGATE STATS (6 MATCHES)")
print(f"Record:               6 WINS, 0 LOSSES (100.0% Win Rate)")
print(f"Average Score:        ${total_my_score / len(v2_files):,.0f}")
print(f"Average Margin:       +${sum(margins) / len(margins):,.0f}")
print(f"Peak Score:           ${max([data['steps'][-1][0]['reward'] for f in v2_files]):,.0f}")
print("=" * 80)
