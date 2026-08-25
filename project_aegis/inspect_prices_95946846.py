import json

with open(r'C:\Users\GauravPatel\Downloads\aegis_latest\wins\95946846.json', 'r', encoding='utf-8') as fp:
    d = json.load(fp)

steps = d['steps']

print("--- Turn-by-Turn Inspection of Match 95946846 ---")
for day in range(0, 30, 2):
    step_idx = day * 24
    obs = steps[step_idx][0]['observation']
    prices = obs['market']['prices']
    farm = obs['farms'][0]
    live_hands = len(farm.get('hands', []))
    act = steps[step_idx][0].get('action') or {}
    tape_hands = len(act.get('hands', []))
    
    print(f"Day {day:02d} (Step {step_idx:03d}): Tomato Price = ${prices.get('TOMATO', 60):3d} | Carrot Price = ${prices.get('CARROT', 30):3d} | Live Hands = {live_hands:2d}")
