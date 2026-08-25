import json

with open(r'C:\Users\GauravPatel\Downloads\lost_matches_21th_august_multi_route_agent_failiures\95830474.json', 'r') as fp:
    data = json.load(fp)

steps = data['steps']
print("=== DAY PROGRESSION ===")
for i in range(0, len(steps), 24):
    p0_obs = steps[i][0]['observation']
    farm0 = p0_obs['farms'][0]
    farm1 = p0_obs['farms'][1]
    d = p0_obs['day']
    print(f"Day {d:02d} (Step {i:03d}): P0 Money: {farm0['money']:10,.1f}, Quads: {farm0['unlocked_quadrants']} | P1 Money: {farm1['money']:10,.1f}, Quads: {farm1['unlocked_quadrants']}")

print("\n=== BUY_LAND ATTEMPTS P0 ===")
for i, s in enumerate(steps):
    act0 = s[0].get('action', {}) or {}
    m0 = act0.get('market', [])
    for op in m0:
        if isinstance(op, list) and len(op) > 0 and op[0] == 'BUY_LAND':
            f0 = s[0]['observation']['farms'][0]
            print(f"Step {i:03d}: P0 issued BUY_LAND with money=${f0['money']:,.1f}, current quads={f0['unlocked_quadrants']}")

print("\n=== BUY_LAND ATTEMPTS P1 ===")
for i, s in enumerate(steps):
    act1 = s[1].get('action', {}) or {}
    m1 = act1.get('market', [])
    for op in m1:
        if isinstance(op, list) and len(op) > 0 and op[0] == 'BUY_LAND':
            f1 = s[1]['observation']['farms'][1]
            print(f"Step {i:03d}: P1 issued BUY_LAND with money=${f1['money']:,.1f}, current quads={f1['unlocked_quadrants']}")
