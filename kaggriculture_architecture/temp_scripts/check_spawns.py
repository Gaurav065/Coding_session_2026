import sys
import collections
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
trace_actions = SOURCE.TRACE_ACTIONS

spawn_pattern = [(4, 4), (5, 4), (4, 5), (5, 5)]
positions = collections.defaultdict(lambda: [4, 4])
farmer_pos = [4, 4]
hands_pos_offline = []

for step, action in enumerate(trace_actions):
    if step % 24 == 0:
        hands_pos_offline = []
    
    farmer_cmd = action.get("farmer", [])
    if farmer_cmd:
        f_op = farmer_cmd[0]
        if f_op == "NORTH" and farmer_pos[1] > 0: farmer_pos[1] -= 1
        elif f_op == "SOUTH" and farmer_pos[1] < 9: farmer_pos[1] += 1
        elif f_op == "EAST" and farmer_pos[0] < 9: farmer_pos[0] += 1
        elif f_op == "WEST" and farmer_pos[0] > 0: farmer_pos[0] -= 1
        
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
            
    if step == 48:
        print(f"Step 48 spawn positions: {hands_pos_offline}")
