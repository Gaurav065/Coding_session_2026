import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    lines = f.readlines()

for i in range(len(lines)):
    if "return {" in lines[i]:
        lines[i] = "    return {\n"

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.writelines(lines)
