import json
import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    in_block = False
    for line in f.readlines():
        if "MARKET_PARAMS =" in line:
            in_block = True
        if in_block:
            print(line.rstrip())
            if line.startswith("}"):
                in_block = False
