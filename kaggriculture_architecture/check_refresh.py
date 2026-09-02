import json
import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "def _daily_refresh_plants" in line:
            for j in range(i, i+30):
                print(lines[j].rstrip('\n'))
            break
