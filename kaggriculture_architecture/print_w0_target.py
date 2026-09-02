import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "    if step == 169: print(f'ENGINE STEP {step}: actions={tape_actions}', file=sys.stderr)",
    "    if step == 169: print(f'ENGINE STEP {step}: W0 target={_TAPE_TASKS[0][0] if len(_TAPE_TASKS[0]) > 0 else \"NONE\"}', file=sys.stderr)"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
