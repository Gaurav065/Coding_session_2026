import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "    if idle_workers:",
    "    if step == 169: print(f'ENGINE STEP {step}: actions={tape_actions}', file=sys.stderr)\n    if idle_workers:"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
