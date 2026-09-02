import sys
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 42})
env.run(["C:\\Coding\\kaggriculture_architecture\\heuristic_agent6.py", "random"])

for step in env.steps[:60]:
    hands = step[0]["action"].get("hands", [])
    for idx, h in enumerate(hands):
        if h and h[0] in ("PLANT", "HARVEST", "WATER", "DIG"):
            print(f"Step {step[0]['observation']['step']} Worker {idx} {h}")
