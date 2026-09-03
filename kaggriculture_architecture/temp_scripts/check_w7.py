import sys
import collections
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
trace_actions = SOURCE.TRACE_ACTIONS

spawn_pattern = [(4, 4), (5, 4), (4, 5), (5, 5)]
positions = collections.defaultdict(lambda: [4, 4])
tasks = collections.defaultdict(list)

farmer_pos = [4, 4]
hands_pos_offline = []

for step, action in enumerate(trace_actions):
    if step % 24 == 0:
        hands_pos_offline = []
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
            
    market = action.get("market", [])
    for m in market:
        if m and m[0] == "HIRE":
            occupants = {tuple(t): 0 for t in spawn_pattern}
            all_p = [tuple(farmer_pos)] + [tuple(p) for p in hands_pos_offline]
            for p in all_p:
                if p in occupants:
                    occupants[p] += 1
            best = sorted(occupants.items(), key=lambda kv: (kv[1], spawn_pattern.index(kv[0])))
            spawn_pos = list(best[0][0])
            hands_pos_offline.append(spawn_pos)
            i = len(hands_pos_offline) - 1
            positions[i] = list(spawn_pos)
            
    for i in range(len(hands_pos_offline)):
        if i in positions:
            hands_pos_offline[i] = list(positions[i])

print("Tasks for Worker 7 between 165 and 175:")
print([t for t in tasks[7] if t['step'] >= 165 and t['step'] <= 175])
