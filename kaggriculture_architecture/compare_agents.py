from kaggle_environments import make

agent_all = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"
agent_orig = r"C:\Coding\kaggriculture_architecture\submission\submission.py"

print("--- SEED 42 COMPARISON ---")

env1 = make("kaggriculture", configuration={"randomSeed": 42})
steps1 = env1.run([agent_orig, "random"])
print(f"Original Agent (Tape) Score: {steps1[-1][0]['reward']}")

env2 = make("kaggriculture", configuration={"randomSeed": 42})
steps2 = env2.run([agent_all, "random"])
print(f"Phase All (Dynamic) Score: {steps2[-1][0]['reward']}")

