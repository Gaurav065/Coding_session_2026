import sys
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 42})
env.run(["C:\\Coding\\kaggriculture_architecture\\heuristic_agent6.py", "random"])

shed_melons = []
for step in env.steps:
    shed = step[0]["observation"].get("private", {}).get("shed", {})
    shed_melons.append(shed.get("MELON", 0))

print(f"Max melons in shed at any time: {max(shed_melons)}")
