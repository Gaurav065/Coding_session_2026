import sys
sys.path.insert(0, r'C:\Coding\project_doppelganger')

from kaggle_environments import make
from main import agent as doppelganger_agent

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1}, debug=True)
env.run([doppelganger_agent, "starter"])

final_p0 = env.steps[-1][0]
print("Final P0 Status:", final_p0['status'])
print("Final P0 Reward:", final_p0['reward'])
if final_p0.get('info'):
    print("Final P0 Info:", final_p0['info'])

# Print last 5 steps
for idx in range(715, 720):
    s = env.steps[idx][0]
    print(f"Step {idx}: Action={s.get('action')} | Money={s['observation']['farms'][0]['money']} | Shed={s['observation']['private']['shed']}")
