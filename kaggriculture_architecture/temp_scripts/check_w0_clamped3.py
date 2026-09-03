import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
import collections

trace = SOURCE.TRACE_ACTIONS
w0_tasks = []
w0_pos = [4, 4]
for s, act in enumerate(trace):
    if s % 24 == 0:
        w0_pos = [4,4]
    hands = act.get("hands", [])
    if len(hands) > 0:
        op = hands[0][0]
        if op == "NORTH": w0_pos[1] = max(0, w0_pos[1]-1)
        elif op == "SOUTH": w0_pos[1] = min(9, w0_pos[1]+1)
        elif op == "EAST": w0_pos[0] = min(9, w0_pos[0]+1)
        elif op == "WEST": w0_pos[0] = max(0, w0_pos[0]-1)
        elif op not in ["PASS"]:
            w0_tasks.append((s, tuple(w0_pos), hands[0]))

print("W0 Tasks around Step 170:")
for t in w0_tasks:
    if 160 <= t[0] <= 200:
        print(t)
