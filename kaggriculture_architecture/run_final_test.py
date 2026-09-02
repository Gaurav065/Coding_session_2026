import time
from kaggle_environments import make

agent_all = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"
agent_orig = r"C:\Coding\kaggriculture_architecture\submission\submission.py"

seeds = [42, 46, 123]
print("Testing Phase All vs Original Agent across seeds:")
print("-" * 50)

for seed in seeds:
    env = make("kaggriculture", configuration={"randomSeed": seed})
    steps = env.run([agent_all, agent_orig])
    score_all = steps[-1][0]["reward"]
    score_orig = steps[-1][1]["reward"]
    print(f"Seed {seed}: Phase All (Dynamic) = {score_all} | Original (Static) = {score_orig}")
