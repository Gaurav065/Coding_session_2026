import json
import os
from collections import defaultdict

def analyze_match(rp_name):
    rf_path = os.path.join(r'C:\Users\GauravPatel\Downloads', rp_name)
    with open(rf_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    steps = data.get("steps", [])
    p0_rew = steps[-1][0].get("reward")
    p1_rew = steps[-1][1].get("reward")
    shops = steps[-1][0].get("observation", {}).get("town", {}).get("unlocked_shops", [])
    
    print(f"\n=======================================================")
    print(f"MATCH: {rp_name} -> P0: ${p0_rew:,.1f} vs P1: ${p1_rew:,.1f} (Diff: {p0_rew - p1_rew:+,.1f})")
    print(f"Town Shops: {shops}")
    
    # Check assets
    f0 = steps[-1][0]['observation']['farms'][0]
    f1 = steps[-1][0]['observation']['farms'][1]
    
    # Check animals & plants
    c0 = sum(1 for a in f0.get('animals', []) if a['type'] == 'COW')
    s0 = sum(1 for a in f0.get('animals', []) if a['type'] == 'SHEEP')
    c1 = sum(1 for a in f1.get('animals', []) if a['type'] == 'COW')
    s1 = sum(1 for a in f1.get('animals', []) if a['type'] == 'SHEEP')
    
    print(f"P0 Assets: {c0} Cows, {s0} Sheep | Money: ${f0.get('money'):,.1f}")
    print(f"P1 Assets: {c1} Cows, {s1} Sheep | Money: ${f1.get('money'):,.1f}")
    
    # Sales breakdown
    sells0 = defaultdict(int)
    sells1 = defaultdict(int)
    for st in steps:
        for p, sdict in [(0, sells0), (1, sells1)]:
            act = st[p].get('action') or {}
            for m in act.get('market', []):
                if m and m[0] == 'SELL':
                    sdict[m[1]] += (m[2] if len(m) > 2 else 1)
    print(f"P0 Sells: {dict(sells0)}")
    print(f"P1 Sells: {dict(sells1)}")

if __name__ == '__main__':
    for rp in ['104060356.json', '104058126.json', '104055879.json']:
        analyze_match(rp)
