import sys
from pathlib import Path
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e706_top10_tapes")
import episode_101408728_seat1

actions = episode_101408728_seat1.TRACE_ACTIONS

all_hands_actions = set()
all_market_actions = set()
for act in actions:
    for h in act.get("hands", []):
        if h: all_hands_actions.add(h[0])
    for m in act.get("market", []):
        if m: 
            if isinstance(m, list): all_market_actions.add(m[0])
            else: all_market_actions.add(m)

print("Hands actions:", all_hands_actions)
print("Market actions:", all_market_actions)
