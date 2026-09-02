from kaggle_environments import make
import sys

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\submission")
import submission as orig_agent

env = make("kaggriculture", debug=True)
states = env.reset()
obs = states[0]["observation"]

action_orig = orig_agent.agent(obs)
states = env.step([action_orig, {"farmer": ["PASS"], "hands": [], "market": []}])
obs = states[0]["observation"]
print("Orig Turn 1 Workers:", obs["farms"][0].get("hands", []))

sys.path.pop(0)
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture")
import submission_phase_f

env2 = make("kaggriculture", debug=True)
states = env2.reset()
obs2 = states[0]["observation"]

action_f = submission_phase_f.agent(obs2)
states = env2.step([action_f, {"farmer": ["PASS"], "hands": [], "market": []}])
obs2 = states[0]["observation"]
print("Phase F Turn 1 Workers:", obs2["farms"][0].get("hands", []))
