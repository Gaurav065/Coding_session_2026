import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent")
from agents.e749a_niklita_consensus_network import SOURCE
import collections

def build_tape_tasks():
    positions = collections.defaultdict(lambda: [4, 4])
    tasks = collections.defaultdict(list)
    
    for step, action in enumerate(SOURCE.TRACE_ACTIONS):
        hands = action.get("hands", [])
        for i, cmd in enumerate(hands):
            if not cmd: continue
            op = cmd[0]
            if op == "NORTH": positions[i][1] = (positions[i][1] + 1) % 10
            elif op == "SOUTH": positions[i][1] = (positions[i][1] - 1) % 10
            elif op == "EAST": positions[i][0] = (positions[i][0] + 1) % 10
            elif op == "WEST": positions[i][0] = (positions[i][0] - 1) % 10
            elif op == "PASS": pass
            else:
                tasks[i].append({
                    "step": step,
                    "x": positions[i][0],
                    "y": positions[i][1],
                    "command": cmd
                })
    return dict(tasks)

tape_tasks = build_tape_tasks()
for w in range(5):
    print(f"Worker {w} has {len(tape_tasks.get(w, []))} tasks. First task: {tape_tasks.get(w, [])[0] if tape_tasks.get(w) else 'None'}")
