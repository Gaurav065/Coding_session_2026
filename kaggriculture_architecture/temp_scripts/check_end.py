import json
import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "def _apply_worker_actions(" in line:
            for j in range(i, len(lines)):
                if "return" in lines[j] and not "    " in lines[j]:
                    pass # Keep going, end of function is where it goes back in indentation
                if "def" in lines[j] and j > i:
                    break
                print(lines[j].rstrip('\n'))
            break
