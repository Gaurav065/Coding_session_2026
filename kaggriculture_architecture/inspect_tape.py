import sys
from pathlib import Path
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e706_top10_tapes")
import episode_101408728_seat1

actions = episode_101408728_seat1.TRACE_ACTIONS

hire_count = 0
dig_count = 0
plant_count = 0

for act in actions:
    for m in act.get("market", []):
        if m == "HIRE" or (isinstance(m, list) and m[0] == "HIRE"):
            hire_count += 1
    
    for hands in act.get("hands", []):
        if "DIG" in hands:
            dig_count += 1
        if "PLANT" in hands or (isinstance(hands, list) and len(hands) > 0 and hands[0] == "PLANT"):
            plant_count += 1

print(f"Hires: {hire_count}")
print(f"Digs: {dig_count}")
print(f"Plants: {plant_count}")
