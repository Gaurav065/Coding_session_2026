import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

import re

# Remove the broken print statement we added earlier
content = re.sub(r"    if step == 169: print\(f'ENGINE STEP \{step\}: actions=\{new_hands\}', file=sys\.stderr\)\n", "", content)

# Inject the smart shed evac
smart_evac = """    has_hire = any(m and m[0] == "HIRE" for m in market_action)
    
    shed_evac = {
        (4, 4): ["NORTH"],
        (5, 4): ["NORTH"],
        (4, 5): ["SOUTH"],
        (5, 5): ["SOUTH"]
    }
    
    if idle_workers and has_hire:
        for w_id in list(idle_workers.keys()):
            hx, hy = idle_workers[w_id]
            if (hx, hy) in shed_evac:
                tape_actions[w_id] = shed_evac[(hx, hy)]
                del idle_workers[w_id]
                
    if idle_workers:"""

content = content.replace("    if idle_workers:\n        assignments = _DISPATCHER.get_actions(idle_workers, tasks, obstacles)", 
"""    has_hire = any(m and m[0] == "HIRE" for m in market_action)
    
    shed_evac = {
        (4, 4): ["NORTH"],
        (5, 4): ["NORTH"],
        (4, 5): ["SOUTH"],
        (5, 5): ["SOUTH"]
    }
    
    if idle_workers and has_hire:
        for w_id in list(idle_workers.keys()):
            hx, hy = idle_workers[w_id]
            if (hx, hy) in shed_evac:
                tape_actions[w_id] = shed_evac[(hx, hy)]
                del idle_workers[w_id]
                
    if idle_workers:
        assignments = _DISPATCHER.get_actions(idle_workers, tasks, obstacles)""")

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
