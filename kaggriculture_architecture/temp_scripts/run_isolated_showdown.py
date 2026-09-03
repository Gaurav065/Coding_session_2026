from kaggle_environments import make
import sys

def test_agent(agent_path):
    env = make("kaggriculture", debug=True)
    # Play against itself to see its raw score potential
    steps = env.run([agent_path, agent_path])
    return steps[-1][0]["reward"]

try:
    print("Testing Original Tape (Self-Play)...")
    orig_score = test_agent("submission/submission.py")
    
    # We must completely wipe sys.modules to prevent bleeding
    to_delete = [m for m in sys.modules if m.startswith('e7')]
    for m in to_delete:
        del sys.modules[m]
        
    print("Testing Nator Tape (Self-Play)...")
    nator_score = test_agent("submission/submission_nator.py")
    
    print(f"\nRESULTS:")
    print(f"Original Tape Score: {orig_score}")
    print(f"Nator Tape Score:    {nator_score}")
except Exception as e:
    print(f"Match failed: {e}")
    sys.exit(1)
