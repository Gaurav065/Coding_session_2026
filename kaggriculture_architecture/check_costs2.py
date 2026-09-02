import json
import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    in_block = False
    for line in f.readlines():
        if "CROPS = {" in line or "ANIMALS = {" in line:
            in_block = True
        if in_block:
            print(line.strip())
            if line.startswith("}"):
                in_block = False
