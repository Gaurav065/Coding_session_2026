import sys
sys.path.insert(0, r'C:\Coding')

import main as aegis_agent
from project_aegis.benchmarks.synthetic_multiwave_opponent import synthetic_multiwave_opponent
from kaggle_environments import make

# Run Seed 1 with Non-Colliding Scavenger (DIG + FERTILIZER + WATER + HARVEST only)
env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 1}, debug=True)

# Temporarily disable PLANT in scavenger overlay
orig_scavenger = aegis_agent.scavenger_farmhand_overlay

def safe_scavenger(action, obs):
    # Only allow DIG, COLLECT_FERTILIZER, WATER, HARVEST (No PLANT on unknown empty tiles)
    act = orig_scavenger(action, obs)
    for h in act.get("hands", []):
        if len(h) > 0 and h[0] == "PLANT":
            h[0] = "PASS"
            if len(h) > 1: h.pop()
    return act

aegis_agent.scavenger_farmhand_overlay = safe_scavenger

env.run([aegis_agent.agent, synthetic_multiwave_opponent])

farm0 = env.steps[-1][0]['observation']['farms'][0]
score = env.steps[-1][0]['reward']
print(f"Seed 1 with Safe Non-Colliding Scavenger:")
print(f"  Score: ${score:,.0f}")
print(f"  Cows Placed: {sum(1 for row in farm0['tiles'] for t in row if isinstance(t, dict) and t.get('animal') == 'COW')}")
print(f"  Sheep Placed: {sum(1 for row in farm0['tiles'] for t in row if isinstance(t, dict) and t.get('animal') == 'SHEEP')}")
