import json
from kaggle_environments import make

agent_all = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"
seeds = [46, 100]

for seed in seeds:
    env = make("kaggriculture", configuration={"randomSeed": seed})
    steps = env.run([agent_all, "random"])
    
    for i, step in enumerate(steps):
        if step[0]["status"] == "ERROR":
            print(f"Seed {seed} ERROR at step {i}:")
            if "info" in step[0] and step[0]["info"]:
                print(step[0]["info"])
            break
