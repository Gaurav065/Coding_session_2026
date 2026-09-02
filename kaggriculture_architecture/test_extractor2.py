import sys
from collections import defaultdict
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE

def extract_tape_tasks(trace_actions, grid_size=10):
    positions = defaultdict(lambda: [4, 4])
    tasks = []
    
    for step, action in enumerate(trace_actions):
        hands = action.get("hands", [])
        for i, cmd in enumerate(hands):
            if not cmd:
                continue
            
            op = cmd[0]
            if op == "NORTH": positions[i][1] = (positions[i][1] + 1) % grid_size
            elif op == "SOUTH": positions[i][1] = (positions[i][1] - 1) % grid_size
            elif op == "EAST": positions[i][0] = (positions[i][0] + 1) % grid_size
            elif op == "WEST": positions[i][0] = (positions[i][0] - 1) % grid_size
            elif op == "PASS":
                pass
            else:
                tasks.append({
                    "step": step,
                    "worker": i,
                    "x": positions[i][0],
                    "y": positions[i][1],
                    "command": cmd
                })
    return tasks

tasks = extract_tape_tasks(SOURCE.TRACE_ACTIONS)
print(f"Extracted {len(tasks)} tasks. Total workers observed: {max(t['worker'] for t in tasks)+1}")
print("First 15 tasks:")
for t in tasks[:15]:
    print(t)
