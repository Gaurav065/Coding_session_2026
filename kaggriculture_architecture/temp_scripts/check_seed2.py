import json

replay_path = r"C:\Users\GauravPatel\Downloads\104735474.json"
with open(replay_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("Config:", data.get('configuration', {}))
