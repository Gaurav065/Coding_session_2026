import json
with open(r"C:\Coding\kaggriculture_architecture\sample_obs.json") as f:
    obs = json.load(f)

grid = obs["farms"][0]["tiles"]
empty_tiles = 0
locked_tiles = 0
for y in range(len(grid)):
    for x in range(len(grid[y])):
        t = grid[y][x]
        if t == "LOCKED":
            locked_tiles += 1
        elif isinstance(t, str) and t == "":
            empty_tiles += 1
        elif isinstance(t, dict):
            pass # crop or weed
        else:
            empty_tiles += 1

print(f"Empty: {empty_tiles}, Locked: {locked_tiles}")
