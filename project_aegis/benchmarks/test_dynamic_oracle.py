import json
import sys

sys.path.insert(0, r'C:\Coding')
sys.path.insert(0, r'C:\Users\GauravPatel\Downloads\multi_route_agent_files')

from kaggle_environments import make

with open(r'C:\Coding\kaggriculture-agent\tape_151k.json', 'r', encoding='utf-8') as f:
    TAPE_151K = json.load(f)

with open(r'C:\Coding\kaggriculture-agent\tape_165k_straw_cow.json', 'r', encoding='utf-8') as f:
    TAPE_165K = json.load(f)

from project_aegis.tape_loader import _ACTIONS_10C4S_3Q, _ACTIONS_8C6S_3Q, _ACTIONS_6C12S_4Q_FIRST_YARN, _ACTIONS_6C12S_4Q_SECOND_YARN, _ACTIONS_6C8S_3Q

def dynamic_oracle_route(obs):
    shops = (obs.get("town") or {}).get("unlocked_shops", []) or []
    # 1. Yarn Store -> Yarn Routes
    if len(shops) >= 1 and shops[:1] == ["YARN_STORE"]:
        return _ACTIONS_6C12S_4Q_FIRST_YARN, "6c12s_yarn_1st"
    if len(shops) >= 2 and "YARN_STORE" in shops[:2]:
        return _ACTIONS_6C12S_4Q_SECOND_YARN, "6c12s_yarn_2nd"
    if len(shops) >= 3 and "YARN_STORE" in shops[:3]:
        return _ACTIONS_6C8S_3Q, "6c8s_yarn_3rd"
    
    # 2. Agro / Crop Scarcity Surge: Bakery / Brunch / Farmers Market
    if {"BAKERY", "BRUNCH_SPOT", "FARMERS_MARKET"}.intersection(shops[:2]):
        # If double Bakery/Brunch -> 151k Dual Melon, else Straw-Cow
        if shops.count("BAKERY") + shops.count("BRUNCH_SPOT") >= 2:
            return TAPE_151K, "151k_dual_melon_agro"
        return TAPE_165K, "165k_straw_cow_agro"
    
    # 3. True Milk Support
    if {"PIZZA_SHOP", "ICE_CREAM_SHOP", "SMOOTHIE_SHOP"}.intersection(shops[:2]):
        return _ACTIONS_10C4S_3Q, "10c4s_milk"
    
    # 4. Default balanced
    return _ACTIONS_8C6S_3Q, "8c6s_balanced"

def dynamic_agent(obs):
    step = obs.get('step', 0)
    player = obs.get('player', 0)
    farms = obs.get('farms', [])
    live_hands = len(farms[player].get('hands', [])) if len(farms) > player else 0
    tape, route_name = dynamic_oracle_route(obs)
    
    if step < len(tape):
        act = tape[step]
        act_copy = {
            'farmer': list(act.get('farmer', ['PASS'])),
            'hands': list(act.get('hands', []))[:live_hands],
            'market': list(act.get('market', []))[:10]
        }
        while len(act_copy['hands']) < live_hands:
            act_copy['hands'].append(['PASS'])
        return act_copy
    return {'farmer': ['PASS'], 'hands': [['PASS']] * live_hands, 'market': []}

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

print("=" * 90)
print("EVALUATING DYNAMIC 4-PATH ORACLE ROUTER ACROSS ALL 10 SEEDS")
print("=" * 90)

scores = []
for seed, profile in test_seeds:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60}, debug=False)
    env.run([dynamic_agent, "starter"])
    reward = env.steps[-1][0]["reward"]
    # get chosen route name
    obs = env.steps[-1][0]["observation"]
    _, route_name = dynamic_oracle_route(obs)
    scores.append(reward)
    print(f"Seed {seed:05d} | Route: {route_name:<22} | Score = ${reward:>8,.0f} | {profile[:35]}")

print("=" * 90)
print(f"DYNAMIC ORACLE AVERAGE REWARD: ${sum(scores)/len(scores):,.0f}")
print(f"DYNAMIC ORACLE PEAK REWARD:    ${max(scores):,.0f}")
print(f"DYNAMIC ORACLE MIN REWARD:     ${min(scores):,.0f}")
print("=" * 90)
