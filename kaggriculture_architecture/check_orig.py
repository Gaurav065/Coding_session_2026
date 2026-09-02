from kaggle_environments import make
import sys

sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\submission")
import submission as orig_agent

env = make("kaggriculture", debug=True)
states = env.reset()
obs = states[0]["observation"]

for i in range(10):
    action = orig_agent.agent(obs)
    opp_action = {"farmer": ["PASS"], "hands": [], "market": []}
    states = env.step([action, opp_action])
    obs = states[0]["observation"]
    
    print(f"Turn {i} orig action:")
    print(f"  Farmer: {action.get('farmer')}")
    print(f"  Hands:  {action.get('hands')}")
