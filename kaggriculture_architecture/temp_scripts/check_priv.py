import json
with open(r"C:\Coding\kaggriculture_architecture\sample_obs.json") as f:
    obs = json.load(f)
print(obs["private"])
