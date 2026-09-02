import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

import re
content = re.sub(r"    shed_evac = \{[\s\S]*?if idle_workers:\n        # First, force any idle worker on a shed tile to step off it to avoid blocking spawns\n        for w_id in list\(idle_workers\.keys\(\)\):\n            hx, hy = idle_workers\[w_id\]\n            if \(hx, hy\) in shed_evac:\n                tape_actions\[w_id\] = shed_evac\[\(hx, hy\)\]\n                del idle_workers\[w_id\]\n                \n        if idle_workers:\n            assignments = _DISPATCHER\.get_actions\(idle_workers, tasks, obstacles\)", "    if idle_workers:\n        assignments = _DISPATCHER.get_actions(idle_workers, tasks, obstacles)", content)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
