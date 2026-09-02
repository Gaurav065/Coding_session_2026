import sys
import json
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 42})
env.run(["C:\\Coding\\kaggriculture_architecture\\heuristic_agent6.py", "random"])

obs = env.steps[0][0]["observation"]
with open("step0_obs.json", "w") as f:
    json.dump(obs, f)
