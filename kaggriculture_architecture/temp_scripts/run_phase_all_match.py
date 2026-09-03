import sys
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 42})
agent_all = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"
agent_orig = r"C:\Coding\kaggriculture_architecture\submission\submission.py"

print("Initializing full match: Phase All (Seat 0) vs Original Phase E (Seat 1)...")
steps = env.run([agent_all, agent_orig])
score0 = steps[-1][0]["reward"]
score1 = steps[-1][1]["reward"]
print(f"Phase All Score (Seat 0): {score0}")
print(f"Original Agent Score (Seat 1): {score1}")
