import json
from kaggle_environments import make

agent_all = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"
env = make("kaggriculture", configuration={"randomSeed": 46})
steps = env.run([agent_all, "random"])
print(f"Seed 46: Final Score = {steps[-1][0]['reward']}")
print(f"Status: {steps[-1][0]['status']}")
if "info" in steps[-1][0]:
    print(f"Info: {steps[-1][0]['info']}")
