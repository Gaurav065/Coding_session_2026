from kaggle_environments import make
import sys

print("Initializing environment...")
env = make("kaggriculture", debug=True)
print("Starting match between Phase E agent vs Phase E agent...")
# We use the compiled submission
agent_path = "submission/submission.py"

try:
    steps = env.run([agent_path, agent_path])
    print(f"Match completed! Steps: {len(steps)}")
    
    p1_reward = steps[-1][0]["reward"]
    p2_reward = steps[-1][1]["reward"]
    print(f"P1 (Phase E): {p1_reward}")
    print(f"P2 (Phase E): {p2_reward}")
except Exception as e:
    print(f"Match failed: {e}")
    sys.exit(1)
