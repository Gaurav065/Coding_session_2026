import sys
import re

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "return {",
    "print(f'STEP {step}: Worker 3 is at {hands_pos[3] if len(hands_pos) > 3 else \"NONE\"}, action={tape_actions.get(\"w_3\")}', file=sys.stderr)\n    return {"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
