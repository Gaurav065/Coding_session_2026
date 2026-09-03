import json
import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    for line in f.readlines():
        if "CROPS =" in line or "ANIMALS =" in line:
            print(line.strip())
        elif "{" in line and "seed" in line and "mature" in line:
            print(line.strip())
