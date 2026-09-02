from kaggle_environments import make
import sys
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent")
import agent_core

def test_phase_f():
    env = make("kaggriculture", debug=True)
    states = env.reset()
    obs = states[0]["observation"]
    
    for i in range(10):
        action = agent_core.agent(obs)
        opp_action = {"farmer": ["PASS"], "hands": [], "market": []}
        states = env.step([action, opp_action])
        obs = states[0]["observation"]
        print(f"Turn {i} Hands action: {action['hands']}")
        print(f"Turn {i} Farmer action: {action['farmer']}")

test_phase_f()
