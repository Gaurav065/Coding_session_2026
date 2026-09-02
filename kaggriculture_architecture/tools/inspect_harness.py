import os

for path in [
    r'C:\Coding\kaggriculture\harness\vs_top.py',
    r'C:\Coding\kaggriculture\harness\canary_final.py',
    r'C:\Coding\kaggriculture\harness\spar.py'
]:
    if os.path.exists(path):
        print(f"\n=== {os.path.basename(path)} ===")
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        print("".join(lines[:40]))
