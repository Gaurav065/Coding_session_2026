import sys
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 42})
env.run(["C:\\Coding\\kaggriculture_architecture\\heuristic_agent6.py", "random"])

melons_sold = 0
for step in env.steps:
    actions = step[0]["action"].get("market", [])
    for a in actions:
        if a[0] == "SELL" and a[1] == "MELON":
            melons_sold += a[2]
            
print(f"Melons sold: {melons_sold}")
print(f"Final money: {env.steps[-1][0]['observation']['farms'][0]['money']}")
print(f"Final reward: {env.steps[-1][0]['reward']}")
