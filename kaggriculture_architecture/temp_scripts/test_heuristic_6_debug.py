import sys
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 42})
env.run(["C:\\Coding\\kaggriculture_architecture\\heuristic_agent6.py", "random"])

for i in range(10):
    print(f"Step {i}:")
    print(env.steps[i][0]["action"])
    
print(f"Heuristic Agent 6 Score: {env.steps[-1][0]['reward']}")
