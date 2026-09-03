import sys
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 42})
env.run(["C:\\Coding\\kaggriculture_architecture\\heuristic_agent6.py", "random"])

for step in env.steps[6:10]:
    obs = step[0]["observation"]
    farm = obs.get("farms", [])[0]
    grid = farm.get("tiles", [])
    for y in range(10):
        for x in range(10):
            tile = grid[y][x]
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                print(f"Step {obs['step']} Plant at {x},{y}: yield={tile.get('yield_units')}, watered={tile.get('watered_today')}")
