from kaggle_environments import make
import sys

print("Initializing environment...")
env = make("kaggriculture", debug=True)
print("Starting ultimate tape showdown: Original Tape vs Nator Tape")
# Both have 5 phases applied
p1_agent = "submission/submission.py"
p2_agent = "submission/submission_nator.py"

try:
    steps = env.run([p1_agent, p2_agent])
    print(f"Match completed! Steps: {len(steps)}")
    
    p1_reward = steps[-1][0]["reward"]
    p2_reward = steps[-1][1]["reward"]
    print(f"P1 (Original Tape): {p1_reward}")
    print(f"P2 (Nator Tape):    {p2_reward}")
except Exception as e:
    print(f"Match failed: {e}")
    sys.exit(1)
