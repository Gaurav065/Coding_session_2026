import sys
import re

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

# Add a print statement when a task is expired
content = content.replace(
    "while tape_queue and tape_queue[0][\"step\"] < step:",
    "while tape_queue and tape_queue[0][\"step\"] < step:\n            print(f'MISSED DEADLINE: Worker {i} missed {tape_queue[0]} at step {step} (pos {current_pos})', file=sys.stderr)"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
