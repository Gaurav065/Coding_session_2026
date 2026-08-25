import json

with open(r'C:\Users\GauravPatel\Downloads\aegis_v2_replays\losses\95935419.json', 'r', encoding='utf-8') as fp:
    d = json.load(fp)

steps = d['steps']

# Let's inspect what happened on each day
print("=== DAY-BY-DAY COMPARISON (Match 95935419) ===")
print(f"{'Day':4s} | {'Shadow Bank':>12s} | {'Opp Bank':>12s} | {'Shadow Sells':40s} | {'Opp Sells':40s}")
print("-" * 115)

for day in range(30):
    start_step = day * 24
    end_step = min((day + 1) * 24, len(steps))
    
    shadow_sells = []
    opp_sells = []
    
    for s in range(start_step, end_step):
        a1 = steps[s][1].get('action') or {}
        a0 = steps[s][0].get('action') or {}
        
        for m in a1.get('market', []) or []:
            if isinstance(m, list) and len(m) >= 2 and m[0] == 'SELL':
                shadow_sells.append(f"{m[1]}:{m[2] if len(m)>2 else 1}")
        for m in a0.get('market', []) or []:
            if isinstance(m, list) and len(m) >= 2 and m[0] == 'SELL':
                opp_sells.append(f"{m[1]}:{m[2] if len(m)>2 else 1}")
                
    m1 = steps[end_step-1][0]['observation']['farms'][1]['money']
    m0 = steps[end_step-1][0]['observation']['farms'][0]['money']
    
    s1_str = ", ".join(shadow_sells[:4]) + (f" (+{len(shadow_sells)-4} more)" if len(shadow_sells) > 4 else "")
    s0_str = ", ".join(opp_sells[:4]) + (f" (+{len(opp_sells)-4} more)" if len(opp_sells) > 4 else "")
    
    print(f"D{day:02d}  | ${m1:11,.0f} | ${m0:11,.0f} | {s1_str:40s} | {s0_str:40s}")
