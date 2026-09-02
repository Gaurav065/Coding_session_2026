import json
with open('sample_obs.json', 'r') as f:
    obs = json.load(f)
    print("Inventories:", obs.get("private", {}).get("inventories", []))
