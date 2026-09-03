import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "print(f'STEP {step}: Worker 3 is at {hands_pos[3]",
    "print(f'STEP {step}: Worker 2 is at {hands_pos[2]"
)
content = content.replace(
    "action={tape_actions.get(\"w_3\")}', file=sys.stderr)",
    "action={tape_actions.get(\"w_2\")}', file=sys.stderr)"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
