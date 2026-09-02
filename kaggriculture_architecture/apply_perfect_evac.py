import sys
import re

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

# Add worker_margins dict
content = content.replace("    idle_workers = {}\n    tape_actions = {}", "    idle_workers = {}\n    tape_actions = {}\n    worker_margins = {}")

# Save margin
content = content.replace("                margin = (target_step - step) - dist", "                margin = (target_step - step) - dist\n                worker_margins[w_id] = margin")

# Default margin for idle
content = content.replace("        else:\n            action = None\n            \n        if action is not None:", "        else:\n            action = None\n            worker_margins[w_id] = 999\n            \n        if action is not None:")

# Replace evac logic
evac_logic = """    # We must evacuate anyone on a shed tile if there's a HIRE today, UNLESS they are executing a task right now!
    if has_hire:
        for i, current_pos in enumerate(hands_pos):
            w_id = f"w_{i}"
            hx, hy = current_pos[0], current_pos[1]
            if (hx, hy) in shed_evac:
                # Are they executing a task THIS step?
                executing_now = False
                if w_id in tape_actions:
                    act = tape_actions[w_id]
                    if act and act[0] not in ["PASS", "NORTH", "SOUTH", "EAST", "WEST"]:
                        executing_now = True
                
                if not executing_now:
                    # Evacuate them!
                    tape_actions[w_id] = shed_evac[(hx, hy)]
                    if w_id in idle_workers:
                        del idle_workers[w_id]"""

new_evac = """    if has_hire:
        for i, current_pos in enumerate(hands_pos):
            w_id = f"w_{i}"
            hx, hy = current_pos[0], current_pos[1]
            if (hx, hy) in shed_evac:
                if worker_margins.get(w_id, 999) > 0:
                    tape_actions[w_id] = shed_evac[(hx, hy)]
                    if w_id in idle_workers:
                        del idle_workers[w_id]"""
                        
content = content.replace(evac_logic, new_evac)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
