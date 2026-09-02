import sys
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 42})
env.run(["C:\\Coding\\kaggriculture_architecture\\heuristic_agent6.py", "random"])

score1 = env.steps[-1][0]["reward"]
score2 = env.steps[-1][1]["reward"]

print(f"Heuristic Agent 6 Score: {score1}")
print(f"Random Agent Score: {score2}")
