import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
import collections

trace = SOURCE.TRACE_ACTIONS
w6_tasks = []
w6_pos = [4, 4]
for s, act in enumerate(trace):
    if s % 24 == 0:
        w6_pos = [4,4]
    hands = act.get("hands", [])
    if len(hands) > 6:
        op = hands[6][0]
        if op == "NORTH": w6_pos[1] = max(0, w6_pos[1]-1)
        elif op == "SOUTH": w6_pos[1] = min(9, w6_pos[1]+1)
        elif op == "EAST": w6_pos[0] = min(9, w6_pos[0]+1)
        elif op == "WEST": w6_pos[0] = max(0, w6_pos[0]-1)
        elif op not in ["PASS"]:
            w6_tasks.append((s, tuple(w6_pos), hands[6]))

print("W6 Tasks around Step 170:")
for t in w6_tasks:
    if 160 <= t[0] <= 180:
        print(t)
