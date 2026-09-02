from kaggle_environments import make
import sys

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\submission")
import submission as orig_agent

env = make("kaggriculture", debug=True)
states = env.reset()
obs = states[0]["observation"]

action_orig = orig_agent.agent(obs)
print("Orig Turn 0 exact action:", action_orig)

sys.path.pop(0)
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
import submission_phase_f

env = make("kaggriculture", debug=True)
states = env.reset()
obs = states[0]["observation"]

action_f = submission_phase_f.agent(obs)
print("Phase F Turn 0 exact action:", action_f)
