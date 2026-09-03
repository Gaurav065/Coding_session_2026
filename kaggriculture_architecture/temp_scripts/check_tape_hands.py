import sys
from pathlib import Path
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e706_top10_tapes")
import episode_101408728_seat1

actions = episode_101408728_seat1.TRACE_ACTIONS

tape_hands = 0
for act in actions:
    for h in act.get("hands", []):
        if h and h[0] not in ["PASS", "NORTH", "SOUTH", "EAST", "WEST"]:
            tape_hands += 1

print("Tape intended productive hand actions:", tape_hands)
