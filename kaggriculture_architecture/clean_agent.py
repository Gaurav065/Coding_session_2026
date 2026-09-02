import sys
import re

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace("    if idle_workers: print(f'ENGINE STEP {step}: W0 tasks={_TAPE_TASKS[0]}', file=sys.stderr)\n", "")

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
