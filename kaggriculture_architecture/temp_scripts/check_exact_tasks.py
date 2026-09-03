import sys
import collections
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
trace_actions = SOURCE.TRACE_ACTIONS

positions = collections.defaultdict(lambda: [4, 4])
tasks = collections.defaultdict(list)

farmer_pos = [4, 4]

for step, action in enumerate(trace_actions):
    if step % 24 == 0:
        farmer_pos = [4, 4]
        
    farmer_cmd = action.get("farmer", [])
    if farmer_cmd:
        f_op = farmer_cmd[0]
        if f_op == "NORTH" and farmer_pos[1] > 0: farmer_pos[1] -= 1
        elif f_op == "SOUTH" and farmer_pos[1] < 9: farmer_pos[1] += 1
        elif f_op == "EAST" and farmer_pos[0] < 9: farmer_pos[0] += 1
        elif f_op == "WEST" and farmer_pos[0] > 0: farmer_pos[0] -= 1
        
    hands = action.get("hands", [])
    for i, cmd in enumerate(hands):
        if not cmd: continue
        op = cmd[0]
        if op == "NORTH" and positions[i][1] > 0: positions[i][1] -= 1
        elif op == "SOUTH" and positions[i][1] < 9: positions[i][1] += 1
        elif op == "EAST" and positions[i][0] < 9: positions[i][0] += 1
        elif op == "WEST" and positions[i][0] > 0: positions[i][0] -= 1
        elif op in ["NORTH", "SOUTH", "EAST", "WEST", "PASS"]: pass
        else:
            tasks[i].append({
                "step": step,
                "x": positions[i][0],
                "y": positions[i][1],
                "command": cmd
            })
            
print("W0 tasks in agent_core:")
for t in tasks[0]:
    if 160 <= t["step"] <= 200:
        print(t)
