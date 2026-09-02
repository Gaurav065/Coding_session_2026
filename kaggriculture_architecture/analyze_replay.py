import json

replay_path = r"C:\Users\GauravPatel\Downloads\104547904.json"
with open(replay_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Replay Version: {data.get('version')}")
print(f"Number of steps: {len(data['steps'])}")

agent_0_total = 0
agent_1_total = 0

for idx, step in enumerate(data['steps']):
    if idx == 0: continue # Initial state
    if idx % 100 == 0 or idx == len(data['steps']) - 1:
        rewards = [s['reward'] for s in step]
        print(f"Step {idx}: Rewards: {rewards}")

# Look specifically for what the agent did in the first 20 turns
print("\nFirst 20 turns actions for both agents:")
for idx in range(1, min(21, len(data['steps']))):
    actions = [s.get('action') for s in data['steps'][idx]]
    # actions[0] is Agent 1, actions[1] is Agent 2
    print(f"Turn {idx}:")
    print(f"  Agent 0 (Seat 0): {actions[0]}")
    print(f"  Agent 1 (Seat 1): {actions[1]}")

