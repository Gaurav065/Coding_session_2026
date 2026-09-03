import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

content = content.replace(
    "assignments = _DISPATCHER.get_actions(idle_workers, tasks, obstacles)",
    "assignments = {w_id: ['PASS'] for w_id in idle_workers}"
)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
