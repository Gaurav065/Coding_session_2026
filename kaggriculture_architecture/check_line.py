import sys
with open(r"C:\Coding\kaggriculture_architecture\debug_output32.txt", "r", encoding="utf-16") as f:
    for line in f:
        if "MISSED DEADLINE:" in line:
            print(line.strip())
            break
