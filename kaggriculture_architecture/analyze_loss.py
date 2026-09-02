import json

replay_path = r"C:\Users\GauravPatel\Downloads\104735474.json"
print(f"Loading {replay_path}...")

with open(replay_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

info = data.get("info", {})
print("Team Names:", info.get("TeamNames"))
print("Episode ID:", info.get("EpisodeId"))

steps = data.get("steps", [])
print(f"Total Steps: {len(steps)}")

# Check statuses and final rewards
last_step = steps[-1]
for i, agent_state in enumerate(last_step):
    print(f"\nAgent {i} Final State:")
    print(f"Status: {agent_state.get('status')}")
    print(f"Reward: {agent_state.get('reward')}")

# Check for errors in any step
for step_idx, step_data in enumerate(steps):
    for i, agent_state in enumerate(step_data):
        if agent_state.get('status') == 'ERROR':
            print(f"Agent {i} crashed at step {step_idx}: {agent_state.get('info')}")

