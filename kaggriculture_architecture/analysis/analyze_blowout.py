import os
import json
from collections import defaultdict

def analyze_blowout(rf_path):
    with open(rf_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    steps = data.get("steps", [])
    print(f"File: {os.path.basename(rf_path)}")
    print(f"Final: P0={steps[-1][0].get('reward')} P1={steps[-1][1].get('reward')}")
    
    # Check early days differences
    for t in range(0, 24*5, 24):
        day = t // 24
        s0 = steps[t][0]['observation']
        s1 = steps[t][1]['observation']
        f0 = s0['farms'][0]
        f1 = s0['farms'][1]
        print(f"Day {day} (Turn {t}):")
        print(f"  P0: Money={f0['money']}, Hands={len(f0['hands'])}, Unlocked={f0['unlocked_quadrants']}")
        print(f"  P1: Money={f1['money']}, Hands={len(f1['hands'])}, Unlocked={f1['unlocked_quadrants']}")

    # Check cumulative seeds, animals, sales
    p0_sells = defaultdict(int)
    p1_sells = defaultdict(int)
    for t, st in enumerate(steps):
        for p, sdict in [(0, p0_sells), (1, p1_sells)]:
            act = st[p].get('action') or {}
            for m in act.get('market', []):
                if m and m[0] == 'SELL':
                    sdict[m[1]] += m[2] if len(m) > 2 else 1

    print("\nTotal Sells across the entire match:")
    print("P0 Sells:", dict(p0_sells))
    print("P1 Sells:", dict(p1_sells))

if __name__ == '__main__':
    analyze_blowout(r'C:\Users\GauravPatel\Downloads\new_data_replays_31st_aug\103848464.json')
