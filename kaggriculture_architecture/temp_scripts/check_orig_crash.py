from kaggle_environments import make
import json

agent_all = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"
agent_orig = r"C:\Coding\kaggriculture_architecture\submission\submission.py"

env = make("kaggriculture", configuration={"randomSeed": 42}, debug=True)
steps = env.run([agent_all, agent_orig])

for i, step in enumerate(steps):
    for agent_idx in [0, 1]:
        if step[agent_idx]["status"] == "ERROR":
            print(f"Agent {agent_idx} ERROR at step {i}:")
            print(step[agent_idx]["info"])
            
print(f"Final Score Agent 0 (All): {steps[-1][0]['reward']}")
print(f"Final Score Agent 1 (Orig): {steps[-1][1]['reward']}")
