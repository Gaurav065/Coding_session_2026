import json
import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    for line in f.readlines():
        if "_drop_inventories_to_shed" in line:
            print(line.strip())
