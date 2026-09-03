import json
import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "def _apply_unit_action(" in line:
            for j in range(i, i+25):
                print(lines[j].rstrip('\n'))
            break
