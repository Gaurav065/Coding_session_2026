import sys
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 42})
env.run(["C:\\Coding\\kaggriculture_architecture\\heuristic_agent6.py", "random"])

water_count = 0
harvest_count = 0
for step in env.steps:
    hands = step[0]["action"].get("hands", [])
    for h in hands:
        if h and h[0] == "WATER":
            water_count += 1
        elif h and h[0] == "HARVEST":
            harvest_count += 1

print(f"Water count: {water_count}")
print(f"Harvest count: {harvest_count}")
