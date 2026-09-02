from kaggle_environments import make
import sys
import os

env = make("kaggriculture", debug=True)
states = env.reset()
obs = states[0]["observation"]

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
import submission_phase_f

try:
    action = submission_phase_f.agent(obs)
except Exception as e:
    import traceback
    traceback.print_exc()
