import json

replay_path = r"C:\Users\GauravPatel\Downloads\104735474.json"
with open(replay_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

steps = data.get("steps", [])

for i in range(0, 720, 100):
    obs = steps[i][0].get('observation', {})
    if 'players' in obs:
        p0 = obs['players'][0]
        p1 = obs['players'][1]
        print(f"Step {i:3d}: A0 {p0['money']:.1f} (cash) | A1 {p1['money']:.1f} (cash)")
