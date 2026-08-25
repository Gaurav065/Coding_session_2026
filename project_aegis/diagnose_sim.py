import sys
sys.path.insert(0, r'C:\Coding')
from kaggle_environments import make
from project_aegis.main import agent as aegis_agent

env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True)
env.run([aegis_agent, 'starter'])

steps = env.steps
print('=== FINAL OBSERVATION ===')
p0_obs = steps[-1][0]['observation']
print('P0 Money:', p0_obs['farms'][0]['money'])
print('P0 Quads:', p0_obs['farms'][0]['unlocked_quadrants'])
print('P0 Shed:', p0_obs['private']['shed'])
print('Market Prices:', p0_obs['market']['prices'])

print('\n=== DAY BY DAY PROGRESSION ===')
for day in range(0, 30, 2):
    step_idx = day * 24
    obs0 = steps[step_idx][0]['observation']
    farm0 = obs0['farms'][0]
    shed0 = obs0['private']['shed']
    print(f"Day {day:02d} (Step {step_idx:03d}): Money=${farm0['money']:8,.1f} | Quads={farm0['unlocked_quadrants']} | Shed Milk={shed0.get('MILK', 0)}, Wool={shed0.get('WOOL', 0)}, Fert={shed0.get('FERTILIZER', 0)}, Wheat={shed0.get('WHEAT', 0)}")
