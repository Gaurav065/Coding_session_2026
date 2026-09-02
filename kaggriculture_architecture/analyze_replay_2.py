import json

replay_path = r"C:\Users\GauravPatel\Downloads\104060356.json"
with open(replay_path, "r", encoding="utf-8") as f:
    data = json.load(f)

print(f"Replay Version: {data.get('version')}")
print(f"Number of steps: {len(data['steps'])}")

print(f"Final rewards: {[s['reward'] for s in data['steps'][-1]]}")
