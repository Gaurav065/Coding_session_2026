import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
trace = SOURCE.TRACE_ACTIONS
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
    if 166 <= s <= 170 and len(hands) > 6:
        print(f"Step {s}: W6 pos at start={w6_pos}, cmd={hands[6]}")
