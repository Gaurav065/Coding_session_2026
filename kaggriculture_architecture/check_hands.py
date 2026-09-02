import sys
with open(r"C:\Users\GauravPatel\AppData\Local\Programs\Python\Python313\Lib\site-packages\kaggle_environments\envs\kaggriculture\kaggriculture.py", "r") as f:
    lines = f.readlines()
for i, line in enumerate(lines):
    if 'farm["hands"] = []' in line or "farm['hands'] = []" in line:
        for j in range(i-5, i+6):
            print(lines[j].rstrip())
        break
