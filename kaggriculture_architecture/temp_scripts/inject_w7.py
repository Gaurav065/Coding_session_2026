import sys
import re

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "return {",
    "if step == 169 or step == 170: print(f'ENGINE STEP {step}: Worker 7 is at {hands_pos[7] if len(hands_pos) > 7 else \"NONE\"}', file=sys.stderr)\n    return {"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
