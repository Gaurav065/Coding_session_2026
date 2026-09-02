import json
with open(r"C:\Coding\kaggriculture_architecture\debug_output50.txt", "r") as f:
    pass # this file only has stdout

import traceback
from kaggle_environments import make
env = make("kaggriculture", configuration={"randomSeed": 42})
agent_all = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"
agent_orig = r"C:\Coding\kaggriculture_architecture\submission\submission.py"

steps = env.run([agent_all, agent_orig])
for i, step in enumerate(steps):
    for seat in (0, 1):
        if step[seat]["status"] == "ERROR":
            print(f"Step {i} Seat {seat} ERROR! Error log:")
            # In Kaggle Environments, sometimes there's a debug info
            if "info" in step[seat] and step[seat]["info"]:
                print(step[seat]["info"])
            break
    if step[0]["status"] == "ERROR": break
