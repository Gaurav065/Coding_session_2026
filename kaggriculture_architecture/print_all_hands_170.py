import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "    if step == 170: print(f'ENGINE STEP 170: Worker 7 spawned at {hands_pos[7] if len(hands_pos) > 7 else \"NONE\"}', file=sys.stderr)",
    "    if step == 170: print(f'ENGINE STEP 170: hands={hands_pos}, farmer={farmer_pos}', file=sys.stderr)"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
