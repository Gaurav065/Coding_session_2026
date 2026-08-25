import json
from collections import defaultdict

file_path = r'C:\Users\GauravPatel\Downloads\aegis_replays\losses\95894332.json'
with open(file_path, 'r', encoding='utf-8') as fp:
    data = json.load(fp)

steps = data['steps']
my_seat = 1
opp_seat = 0

my_expenses = defaultdict(float)
opp_expenses = defaultdict(float)
my_hires = 0
opp_hires = 0

for step_idx, step in enumerate(steps):
    act_my = step[my_seat].get('action') or {}
    act_opp = step[opp_seat].get('action') or {}

    # Check hires
    for m in act_my.get('market', []) or []:
        if isinstance(m, list) and len(m) > 0:
            if m[0] == 'HIRE':
                my_hires += 1
            elif m[0] == 'BUY_PRODUCT':
                my_expenses['BUY_PRODUCT_' + str(m[1])] += int(m[2]) * 25 # approximate/tracked
            elif m[0] == 'BUY_SEED':
                my_expenses['BUY_SEED_' + str(m[1])] += 1
            elif m[0] == 'BUY_ANIMAL':
                my_expenses['BUY_ANIMAL_' + str(m[1])] += int(m[2]) if len(m) > 2 else 1
            elif m[0] == 'BUY_LAND':
                my_expenses['BUY_LAND'] += 1

    for m in act_opp.get('market', []) or []:
        if isinstance(m, list) and len(m) > 0:
            if m[0] == 'HIRE':
                opp_hires += 1
            elif m[0] == 'BUY_PRODUCT':
                opp_expenses['BUY_PRODUCT_' + str(m[1])] += int(m[2]) * 25
            elif m[0] == 'BUY_SEED':
                opp_expenses['BUY_SEED_' + str(m[1])] += 1
            elif m[0] == 'BUY_ANIMAL':
                opp_expenses['BUY_ANIMAL_' + str(m[1])] += int(m[2]) if len(m) > 2 else 1
            elif m[0] == 'BUY_LAND':
                opp_expenses['BUY_LAND'] += 1

print("--- EXPENSES BREAKDOWN ---")
print(f"Shadow Hires Count: {my_hires} | Opp Hires Count: {opp_hires}")
print("Shadow Expenses:", dict(my_expenses))
print("Opponent Expenses:", dict(opp_expenses))

# Check terminal shed & inventories
final_obs = steps[-1][0]['observation']
print("\n--- FINAL STATE ---")
print("Shadow Money:", steps[-1][my_seat]['reward'])
print("Opponent Money:", steps[-1][opp_seat]['reward'])

# Trace money delta step by step in the last 50 steps (Days 28-30)
print("\n--- LAST 50 STEPS MONEY TRACE ---")
for s in range(670, 720, 5):
    m_my = steps[s][my_seat]['observation']['farms'][my_seat]['money']
    m_opp = steps[s][opp_seat]['observation']['farms'][opp_seat]['money']
    print(f"Step {s:03d}: Shadow Money=${m_my:8.0f} | Opp Money=${m_opp:8.0f} | Margin={m_my - m_opp:8.0f}")
