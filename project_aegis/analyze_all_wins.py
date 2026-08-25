import json
import os
from collections import defaultdict

wins_dir = r'C:\Users\GauravPatel\Downloads\aegis_replays\wins'
files = [f for f in os.listdir(wins_dir) if f.endswith('.json')]

print("=" * 80)
print(f"AEGIS WINS REPLAY ANALYSIS ({len(files)} MATCHES)")
print("=" * 80)

for f in sorted(files):
    file_path = os.path.join(wins_dir, f)
    with open(file_path, 'r', encoding='utf-8') as fp:
        data = json.load(fp)

    steps = data['steps']
    p0_final = steps[-1][0]['reward']
    p1_final = steps[-1][1]['reward']
    winner = "P0 (Aegis)" if p0_final > p1_final else "P1 (Opponent)"
    margin = abs(p0_final - p1_final)
    shops = steps[-1][0]['observation']['town']['unlocked_shops']
    
    print(f"\n>>> MATCH ID: {f} | Final: P0={p0_final:,.0f} vs P1={p1_final:,.0f} | Winner: {winner} (+{margin:,.0f})")
    print(f"    Unlocked Shops ({len(shops)}): {shops}")

    # Track sales & revenues
    p0_sells = defaultdict(int)
    p1_sells = defaultdict(int)
    p0_revenue = defaultdict(float)
    p1_revenue = defaultdict(float)

    for step_idx, step in enumerate(steps):
        obs0 = step[0]['observation']
        act0 = step[0].get('action') or {}
        act1 = step[1].get('action') or {}
        prices = obs0['market']['prices']

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

    print(f"    {'Item':12s} | {'P0 Sold':>8s} | {'P0 Avg P':>10s} | {'P0 Rev':>11s} | {'P1 Sold':>8s} | {'P1 Avg P':>10s} | {'P1 Rev':>11s}")
    print("    " + "-" * 72)
    all_items = sorted(set(list(p0_sells.keys()) + list(p1_sells.keys())))
    for item in all_items:
        q0 = p0_sells[item]
        r0 = p0_revenue[item]
        avg0 = (r0 / q0) if q0 > 0 else 0.0

        q1 = p1_sells[item]
        r1 = p1_revenue[item]
        avg1 = (r1 / q1) if q1 > 0 else 0.0
        print(f"    {item:12s} | {q0:8d} | ${avg0:9.1f} | ${r0:10.1f} | {q1:8d} | ${avg1:9.1f} | ${r1:10.1f}")
