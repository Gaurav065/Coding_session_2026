import sys
with open(r"C:\Coding\kaggriculture_architecture\debug_output22.txt", "r", encoding="utf-16") as f:
    for line in f:
        if "ENGINE STEP 169:" in line or "ENGINE STEP 170:" in line or "ENGINE STEP 171:" in line or "ENGINE STEP 172:" in line:
            print(line.strip())
