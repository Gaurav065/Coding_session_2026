import json

replay_path = r"C:\Users\GauravPatel\Downloads\104547904.json"
with open(replay_path, "r", encoding="utf-8") as f:
    data = json.load(f)

for idx, step in enumerate(data['steps']):
    if idx == 0: continue
    s0 = step[0].get('status')
    s1 = step[1].get('status')
    if s0 not in ('DONE', 'ACTIVE') or s1 not in ('DONE', 'ACTIVE'):
        print(f"Step {idx}: Status Agent 0: {s0}, Status Agent 1: {s1}")
        print(f"Agent 0 error: {step[0].get('error')}")
        print(f"Agent 1 error: {step[1].get('error')}")
        break
else:
    print("All steps have status DONE or ACTIVE.")
