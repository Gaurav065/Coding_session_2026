import sys
with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "shed_evac = {" in line:
        skip = True
    if skip and "if idle_workers:" in line and "Process Idle Workers" not in line and "assignments" not in line:
        skip = False
        new_lines.append("    if idle_workers:\n")
        new_lines.append("        assignments = _DISPATCHER.get_actions(idle_workers, tasks, obstacles)\n")
        continue
    if not skip and "assignments = _DISPATCHER.get_actions" not in line:
        new_lines.append(line)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.writelines(new_lines)
