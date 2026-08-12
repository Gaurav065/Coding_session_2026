import json
with open("main.py") as f:
    lines = f.readlines()
for i, l in enumerate(lines):
    if '["PLANT"' in l or "['PLANT'" in l:
        print("".join(lines[i-15:i+15]))
        break
