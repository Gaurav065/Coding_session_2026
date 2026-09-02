import sys
with open(r"C:\Coding\kaggriculture_architecture\debug_output29.txt", "r", encoding="utf-16") as f:
    for line in f:
        if "ENGINE STEP" in line:
            print(line.strip())
