import json
import sys
import os

sys.path.insert(0, r'C:\Coding')
sys.path.insert(0, r'C:\Users\GauravPatel\Downloads\multi_route_agent_files')

from kaggle_environments import make

# Load all candidate tapes
tapes_config = {
    '1. Baseline 8c6s': r'C:\Coding\kaggriculture-agent\tape_134k_balanced.json',
    '2. Baseline 10c4s': r'C:\Coding\kaggriculture-agent\tape_154k_sheep_melon.json',
    '3. Dual-Melon (151k)': r'C:\Coding\kaggriculture-agent\tape_151k.json',
    '4. Straw-Cow (165k)': r'C:\Coding\kaggriculture-agent\tape_165k_straw_cow.json',
}

loaded_tapes = {}
for k, v in tapes_config.items():
    with open(v, 'r', encoding='utf-8') as f:
        loaded_tapes[k] = json.load(f)

# Also load decoded agent's 10c4s and 8c6s directly
from project_aegis.tape_loader import _ACTIONS_10C4S_3Q, _ACTIONS_8C6S_3Q, _ACTIONS_6C12S_4Q_FIRST_YARN, _ACTIONS_6C12S_4Q_SECOND_YARN, _ACTIONS_6C8S_3Q
loaded_tapes['0. Aegis Base 8c6s'] = _ACTIONS_8C6S_3Q
loaded_tapes['0. Aegis Base 10c4s'] = _ACTIONS_10C4S_3Q
loaded_tapes['0. Aegis Yarn 1st'] = _ACTIONS_6C12S_4Q_FIRST_YARN
loaded_tapes['0. Aegis Yarn 2nd'] = _ACTIONS_6C12S_4Q_SECOND_YARN

def make_tape_player(tape_data):
    def raw_player(obs):
        step = obs.get('step', 0)
        player = obs.get('player', 0)
        farms = obs.get('farms', [])
        live_hands = len(farms[player].get('hands', [])) if len(farms) > player else 0
        if step < len(tape_data):
            act = tape_data[step]
            act_copy = {
                'farmer': list(act.get('farmer', ['PASS'])),
                'hands': list(act.get('hands', []))[:live_hands],
                'market': list(act.get('market', []))[:10]
            }
            while len(act_copy['hands']) < live_hands:
                act_copy['hands'].append(['PASS'])
            return act_copy
        return {'farmer': ['PASS'], 'hands': [['PASS']] * live_hands, 'market': []}
    return raw_player

# Diverse test seeds with distinct shop profiles
test_seeds = [
    (1, "Farmers Mkt x2 + Bakery (Extreme Crop Demand)"),
    (7, "Smoothie + Ice Cream + Pizza (Triple Milk Surge)"),
    (13, "Yarn Store Day 3 (Wool 2x Surge)"),
    (24, "Smoothie + Pizza x2 (Triple Milk Surge)"),
    (55, "Pet Cafe x2 + Farmers Mkt (Carrots 24/day)"),
    (100, "Farmers Mkt + Bakery (Wheat/Egg/Carrot/Melon)"),
    (144, "Bakery + Brunch x2 (Extreme Wheat/Egg/Straw)"),
    (1024, "Bakery x2 + Yarn Day 9 (Wheat + Late Wool)"),
    (65536, "Bakery + Ice Cream x2 (Milk + Straw + Wheat)"),
    (88888, "Pizza + Ice Cream + Farmers Mkt (Milk + Tomato + Straw)"),
]

candidate_names = [
    '0. Aegis Base 8c6s',
    '0. Aegis Base 10c4s',
    '0. Aegis Yarn 1st',
    '3. Dual-Melon (151k)',
    '4. Straw-Cow (165k)',
]

print("=" * 110)
print(f"{'Seed & Shop Profile':<45} | " + " | ".join([f"{cn[:12]:<12}" for cn in candidate_names]))
print("=" * 110)

scores_by_candidate = {cn: [] for cn in candidate_names}

for seed, profile in test_seeds:
    row = [f"Seed {seed:05d}: {profile[:33]:<33}"]
    for cn in candidate_names:
        t_data = loaded_tapes[cn]
        p_fn = make_tape_player(t_data)
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60}, debug=False)
        env.run([p_fn, "starter"])
        reward = env.steps[-1][0]["reward"]
        scores_by_candidate[cn].append(reward)
        row.append(f"${reward:>10,.0f}")
    print(" | ".join(row))

print("=" * 110)
print(f"{'OVERALL AVERAGE SCORE':<45} | " + " | ".join([f"${sum(scores_by_candidate[cn])/len(scores_by_candidate[cn]):>10,.0f}" for cn in candidate_names]))
print(f"{'PEAK SCORE ACHIEVED':<45} | " + " | ".join([f"${max(scores_by_candidate[cn]):>10,.0f}" for cn in candidate_names]))
print("=" * 110)
