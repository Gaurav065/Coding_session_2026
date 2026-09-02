import kaggle_environments
import os
path = os.path.join(os.path.dirname(kaggle_environments.__file__), "envs", "kaggriculture", "kaggriculture.py")
with open(path, "r") as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if "def _apply_worker_actions" in line:
            for j in range(i, min(len(lines), i+150)):
                if "COW" in lines[j] or "animal" in lines[j]:
                    print(f"{j}: {lines[j].strip()}")
