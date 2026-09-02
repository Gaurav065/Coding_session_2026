import json
import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    for i, line in enumerate(f.readlines()):
        if "yield_units" in line:
            print(f"Line {i}: {line.strip()}")
