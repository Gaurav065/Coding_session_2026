from kaggle_environments import make

agent_all = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"
agent_orig = r"C:\Coding\kaggriculture_architecture\submission\submission.py"

env = make("kaggriculture", configuration={"randomSeed": 42}, debug=True)
steps = env.run([agent_all, agent_orig])

actions_1 = [step[1]["action"] for step in steps if step[1]["action"]]
print(f"Agent 1 Actions Count: {len(actions_1)}")
if actions_1:
    print(f"First 5 actions: {actions_1[:5]}")
