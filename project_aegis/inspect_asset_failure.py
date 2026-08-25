import sys
sys.path.insert(0, r'C:\Coding')

import main as aegis_agent
from project_aegis.benchmarks.synthetic_multiwave_opponent import synthetic_multiwave_opponent
from kaggle_environments import make

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1}, debug=True)
env.run([aegis_agent.agent, synthetic_multiwave_opponent])

# Analyze tile map and animals placed
farm0 = env.steps[-1][0]['observation']['farms'][0]
tiles = farm0['tiles']
cows = 0
sheep = 0
strawberries = 0
melons = 0
for row in tiles:
    for t in row:
        if isinstance(t, dict):
            if t.get('animal') == 'COW':
                cows += 1
            elif t.get('animal') == 'SHEEP':
                sheep += 1
            elif t.get('crop') == 'STRAWBERRY':
                strawberries += 1
            elif t.get('crop') == 'MELON':
                melons += 1

print(f"End-of-Game Asset Inventory (Seed 1 with Feature ON):")
print(f"  Cows Placed:         {cows}")
print(f"  Sheep Placed:        {sheep}")
print(f"  Strawberries Active: {strawberries}")
print(f"  Melons Active:       {melons}")
print(f"  Final Money:         ${farm0['money']:,.0f}")
