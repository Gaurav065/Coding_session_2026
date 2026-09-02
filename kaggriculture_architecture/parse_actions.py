import json

replay_path = r"C:\Users\GauravPatel\Downloads\104735474.json"
with open(replay_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

steps = data.get("steps", [])

a0_market = {}
a1_market = {}
a0_hands = 0
a1_hands = 0

for step_idx in range(1, len(steps)):
    step = steps[step_idx]
    
    a0_action = step[0].get("action", {})
    a1_action = step[1].get("action", {})
    
    # A0 market
    for m in a0_action.get("market", []):
        cmd = m[0] if isinstance(m, list) else m
        a0_market[cmd] = a0_market.get(cmd, 0) + 1
        
    for m in a1_action.get("market", []):
        cmd = m[0] if isinstance(m, list) else m
        a1_market[cmd] = a1_market.get(cmd, 0) + 1
        
    # Hands counts
    for h in a0_action.get("hands", []):
        if h and h[0] not in ["PASS", "NORTH", "SOUTH", "EAST", "WEST"]:
            a0_hands += 1
            
    for h in a1_action.get("hands", []):
        if h and h[0] not in ["PASS", "NORTH", "SOUTH", "EAST", "WEST"]:
            a1_hands += 1

print("A0 (Us) Market Actions:", a0_market)
print("A0 (Us) Productive Hand Actions:", a0_hands)
print("---")
print("A1 (Opp) Market Actions:", a1_market)
print("A1 (Opp) Productive Hand Actions:", a1_hands)

