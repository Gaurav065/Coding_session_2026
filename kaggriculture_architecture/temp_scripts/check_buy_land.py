import sys
from pathlib import Path
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e706_top10_tapes")
import episode_101408728_seat1

actions = episode_101408728_seat1.TRACE_ACTIONS

buy_land = 0
for act in actions:
    for m in act.get("market", []):
        if m == "BUY_LAND" or (isinstance(m, list) and m[0] == "BUY_LAND"):
            buy_land += 1
print("BUY_LAND count:", buy_land)
