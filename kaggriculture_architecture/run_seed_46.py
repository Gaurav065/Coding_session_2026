import time
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 46})
agent_all = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"
agent_orig = r"C:\Coding\kaggriculture_architecture\submission\submission.py"

print("Seed 46 Showdown: Phase All vs Original")
steps = env.run([agent_all, agent_orig])
print(f"Phase All: {steps[-1][0]['reward']}")
print(f"Original: {steps[-1][1]['reward']}")
