import json

replay_path = r"C:\Users\GauravPatel\Downloads\104735474.json"
with open(replay_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

steps = data.get("steps", [])
# Look at step 1 or 2 for stdout/stderr
for step_idx in range(1, 10):
    for i, agent_state in enumerate(steps[step_idx]):
        if "stdout" in agent_state:
            print(f"Step {step_idx}, Agent {i} stdout length: {len(agent_state['stdout'])}")
        if "stderr" in agent_state:
            print(f"Step {step_idx}, Agent {i} stderr length: {len(agent_state['stderr'])}")

