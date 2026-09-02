import sys
import json
import traceback

def test_hands_override():
    # Import the original submission agent
    sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\submission")
    import submission as orig
    
    from kaggle_environments import make
    env = make("kaggriculture", debug=True)
    obs = env.reset()[0]["observation"]
    
    try:
        # Turn 1
        action = orig.agent(obs)
        print("Turn 1 Original Action:", action)
        
        # Override hands
        action["hands"] = []
        obs, reward, done, info = env.step([action, action])
        
        # Turn 2
        obs0 = obs[0]["observation"]
        action2 = orig.agent(obs0)
        print("Turn 2 Original Action:", action2)
        
        print("Success! Original agent did not crash when hands were overridden.")
    except Exception as e:
        print("Crash!")
        traceback.print_exc()

test_hands_override()
