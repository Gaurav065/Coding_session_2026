import json
import os
from collections import defaultdict

wins_dir = r'C:\Users\GauravPatel\Downloads\aegis_replays\wins'

for f in ['95880670.json', '95882950.json']:
    file_path = os.path.join(wins_dir, f)
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

    print("=" * 80)
    print(f"FORENSIC MATCH REPORT: {f}")
    print(f"Shadow Recon (Seat {my_seat}): {my_score:,.0f}  VS  {opp_name} (Seat {opp_seat}): {opp_score:,.0f}")
    print(f"Result: VICTORY by +{my_score - opp_score:,.0f} coins")
    print(f"Town Shops ({len(shops)}): {shops}")
    print("=" * 80)

    # 1. Shop Unlocks Timeline
    print("\n--- Town Shop Unlock Schedule ---")
    prev_shops = []
    for step_idx, step in enumerate(steps):
        cur_shops = step[0]['observation']['town']['unlocked_shops']
        if len(cur_shops) > len(prev_shops):
            day = step[0]['observation']['day']
            print(f"  Day {day:02d} (Step {step_idx:03d}): + {cur_shops[-1]:18s} (Total: {len(cur_shops)})")
            prev_shops = list(cur_shops)

    # 2. Commodity Sales Breakdown
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
    print()
