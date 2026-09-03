import json
import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    lines = f.readlines()
    for j in range(445, 470):
        print(lines[j].rstrip('\n'))
