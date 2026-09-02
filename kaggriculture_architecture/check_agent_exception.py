import json
import sys

with open(r"C:\Coding\kaggriculture_architecture\sample_obs.json", "r") as f:
    obs = json.load(f)

import submission_phase_all
try:
    action = submission_phase_all.agent(obs)
    print("Action:", action)
except Exception as e:
    import traceback
    traceback.print_exc(file=sys.stdout)
