import time
from kaggle_environments import make

agent_all = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"

seeds = [42, 46, 100]
print("Testing Phase All Agent across multiple seeds:")

for seed in seeds:
    env = make("kaggriculture", configuration={"randomSeed": seed})
    # Run against a simple pass agent for speed, or against itself
    # Actually, running against itself is best to test solo score without interference,
    # or against 'random' to test robustness. Let's run against 'random'.
    steps = env.run([agent_all, "random"])
    score = steps[-1][0]["reward"]
    print(f"Seed {seed}: Score = {score}")
