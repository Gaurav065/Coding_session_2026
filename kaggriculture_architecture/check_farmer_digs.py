import sys
from pathlib import Path
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e706_top10_tapes")
import episode_101408728_seat1

actions = episode_101408728_seat1.TRACE_ACTIONS

farmer_digs_per_day = []
current_digs = 0

for step, act in enumerate(actions):
    if step > 0 and step % 24 == 0:
        farmer_digs_per_day.append(current_digs)
        current_digs = 0
        
    farmer_cmd = act.get("farmer", [])
    if farmer_cmd and farmer_cmd[0] == "DIG":
        current_digs += 1

print("Farmer Digs per day:", farmer_digs_per_day)
