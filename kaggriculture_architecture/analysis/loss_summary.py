import json
import os
from collections import defaultdict

def print_summary(rf_path):
    with open(rf_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    steps = data.get("steps", [])
    final = steps[-1]
    p0_rew = final[0].get("reward")
    p1_rew = final[1].get("reward")
    print(f"\nReplay: {os.path.basename(rf_path)}")
    print(f"Outcome: P0 = ${p0_rew:,.1f} vs P1 = ${p1_rew:,.1f} (Delta: {p0_rew - p1_rew:+,.1f})")
    
    # Check shop unlocks
    shops = steps[-1][0].get("observation", {}).get("town", {}).get("unlocked_shops", [])
    print(f"Shops: {shops}")

    # Check animal setups
    for p in [0, 1]:
        animals = defaultdict(int)
        seeds = defaultdict(int)
        sells = defaultdict(int)
        for st in steps:
            act = st[p].get("action") or {}
            for m in act.get("market", []):
                if not m: continue
                if m[0] == "BUY_ANIMAL": animals[m[1]] += (m[2] if len(m) > 2 else 1)
                elif m[0] == "BUY_SEED": seeds[m[1]] += (m[2] if len(m) > 2 else 1)
                elif m[0] == "SELL": sells[m[1]] += (m[2] if len(m) > 2 else 1)
        print(f"P{p}: Animals={dict(animals)} Seeds={dict(seeds)} Sells={dict(sells)}")

if __name__ == '__main__':
    downloads = r'C:\Users\GauravPatel\Downloads'
    for rp in ['104060356.json', '104058126.json', '104055879.json']:
        p = os.path.join(downloads, rp)
        if os.path.exists(p):
            print_summary(p)
