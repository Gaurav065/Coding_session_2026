import json
with open(r"C:\Coding\kaggriculture_architecture\sample_obs.json") as f:
    obs = json.load(f)

grid = obs["farms"][0]["tiles"]
types = set()
for y in range(len(grid)):
    for x in range(len(grid[y])):
        t = grid[y][x]
        if isinstance(t, str):
            types.add(t)
        else:
            types.add("dict:" + t.get("kind", ""))
print(types)
