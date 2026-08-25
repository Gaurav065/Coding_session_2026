import sys
sys.path.insert(0, r'C:\Coding')
sys.path.insert(0, r'C:\Users\GauravPatel\Downloads\multi_route_agent_files')

from kaggle_environments import make
from decoded_agent import agent as decoded_agent
from project_aegis.main import agent as aegis_agent

# Run decoded agent vs starter
env_dec = make('kaggriculture', configuration={'episodeSteps': 720, 'seed': 42}, debug=True)
env_dec.run([decoded_agent, 'starter'])

# Run aegis vs starter
env_aegis = make('kaggriculture', configuration={'episodeSteps': 720, 'seed': 42}, debug=True)
env_aegis.run([aegis_agent, 'starter'])

print(f"Decoded Reward: {env_dec.steps[-1][0]['reward']:,.0f}")
print(f"Aegis Reward:   {env_aegis.steps[-1][0]['reward']:,.0f}")

# Find first step where actions differ
diff_count = 0
for step_idx in range(len(env_dec.steps)):
    act_dec = env_dec.steps[step_idx][0]['action']
    act_aegis = env_aegis.steps[step_idx][0]['action']
    if act_dec != act_aegis:
        print(f"\nDiff at step {step_idx}:")
        print(f"  Decoded: {act_dec}")
        print(f"  Aegis:   {act_aegis}")
        diff_count += 1
        if diff_count >= 5:
            break
