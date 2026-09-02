import sys
from pathlib import Path
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e706_top10_tapes")
import episode_101408728_seat1

actions = episode_101408728_seat1.TRACE_ACTIONS

hires_per_day = []
current_hires = 0

for step, act in enumerate(actions):
    if step > 0 and step % 24 == 0:
        hires_per_day.append(current_hires)
        current_hires = 0
        
    for m in act.get("market", []):
        if m == "HIRE" or (isinstance(m, list) and m[0] == "HIRE"):
            current_hires += 1

print("Hires per day:", hires_per_day)
