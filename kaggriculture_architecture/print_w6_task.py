import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "    if step == 169: print(f'ENGINE STEP 169: W3 task={_TAPE_TASKS.get(3, [{}])[0]}, W4 task={_TAPE_TASKS.get(4, [{}])[0]}', file=sys.stderr)",
    "    if step == 169: print(f'ENGINE STEP 169: W6 task={_TAPE_TASKS.get(6, [{}])[0]}', file=sys.stderr)"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
