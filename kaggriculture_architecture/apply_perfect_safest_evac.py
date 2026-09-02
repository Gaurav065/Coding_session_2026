import sys

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "r") as f:
    content = f.read()

evac_logic = """    if has_hire:
        for i, current_pos in enumerate(hands_pos):
            w_id = f"w_{i}"
            hx, hy = current_pos[0], current_pos[1]
            if (hx, hy) in shed_evac:
                margin = worker_margins.get(w_id, 999)
                dist = worker_dists.get(w_id, 0)
                # Only evacuate if completely idle OR waiting exactly at its target with spare time
                if margin > 2 or (dist == 0 and margin > 0):
                    tape_actions[w_id] = shed_evac[(hx, hy)]
                    if w_id in idle_workers:
                        del idle_workers[w_id]"""

new_evac = """    if has_hire:
        for i, current_pos in enumerate(hands_pos):
            w_id = f"w_{i}"
            hx, hy = current_pos[0], current_pos[1]
            if (hx, hy) in shed_evac:
                executing_now = False
                if w_id in tape_actions:
                    act = tape_actions[w_id]
                    if act and act[0] not in ["PASS", "NORTH", "SOUTH", "EAST", "WEST"]:
                        executing_now = True
                
                if not executing_now:
                    margin = worker_margins.get(w_id, 999)
                    dist = worker_dists.get(w_id, 0)
                    if margin > 2 or (dist == 0 and margin > 0):
                        tape_actions[w_id] = shed_evac[(hx, hy)]
                        if w_id in idle_workers:
                            del idle_workers[w_id]"""

content = content.replace(evac_logic, new_evac)

with open(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py", "w") as f:
    f.write(content)
