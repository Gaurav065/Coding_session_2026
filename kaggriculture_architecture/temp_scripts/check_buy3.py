import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "BUY_PRODUCT" in line and "shed" in line:
            print(f"Line {i}: {line.strip()}")
            for j in range(i-2, i+5):
                print(f"{j}: {lines[j].strip()}")
