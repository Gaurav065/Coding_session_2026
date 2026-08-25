import json

file_path = r'C:\Users\GauravPatel\Downloads\95971951.json'
with open(file_path, 'r', encoding='utf-8') as fp:
    data = json.load(fp)

steps = data['steps']
my_seat = 0

print("=== DEEP DIAGNOSTIC OF SHADOW RECON ACTIONS IN MATCH 95971951 ===")

# Check all market actions
seed_buys = []
for s_idx, s in enumerate(steps):
    act = s[my_seat].get('action') or {}
    for m in act.get('market', []) or []:
        if isinstance(m, list) and len(m) >= 2 and m[0] == 'BUY_SEED':
            day = s[0]['observation']['day']
            seed_buys.append((s_idx, day, m[1], m[2] if len(m) > 2 else 1))

print(f"\n1. All Seed Buys Across Match ({len(seed_buys)} events):")
for sb in seed_buys:
    print(f"  Step {sb[0]:03d} (Day {sb[1]:02d}): BUY_SEED {sb[2]} {sb[3]}")

# Check farmhand actions and counts on each day
print("\n2. Farmhands and Scavenger Overlay Decisions (Days 3-15):")
for day in range(3, 16):
    step_idx = day * 24
    obs = steps[step_idx][0]['observation']
    farm = obs['farms'][my_seat]
    live_hands = farm.get('hands', []) or []
    act = steps[step_idx][my_seat].get('action') or {}
    tape_hands = act.get('hands', []) or []
    
    print(f"  Day {day:02d} (Step {step_idx:03d}): Live Hands = {len(live_hands)}, Tape Hands = {len(tape_hands)}, Farmer = {act.get('farmer')}")
    if len(tape_hands) > 0:
        print(f"      Tape Hand Actions: {tape_hands}")
