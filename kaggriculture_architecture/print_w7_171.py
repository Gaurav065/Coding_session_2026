import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "    if step == 169: print(f'ENGINE STEP {step}: W0 tasks={_TAPE_TASKS[0]}', file=sys.stderr)",
    "    if step == 171: print(f'ENGINE STEP 171: W7 pos={hands_pos[7] if len(hands_pos) > 7 else \"NONE\"}', file=sys.stderr)"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
