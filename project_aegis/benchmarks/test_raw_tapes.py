import json
import sys
sys.path.insert(0, r'C:\Coding')
sys.path.insert(0, r'C:\Users\GauravPatel\Downloads\multi_route_agent_files')

from kaggle_environments import make
from decoded_agent import agent as decoded_agent

tapes = {
    '10c4s_3q': r'C:\Users\GauravPatel\Downloads\multi_route_agent_files\decoded_agent.py',
    'tape_151k': r'C:\Coding\kaggriculture-agent\tape_151k.json',
    'tape_154k_sheep_melon': r'C:\Coding\kaggriculture-agent\tape_154k_sheep_melon.json',
    'tape_165k_straw_cow': r'C:\Coding\kaggriculture-agent\tape_165k_straw_cow.json',
    'tape_134k_balanced': r'C:\Coding\kaggriculture-agent\tape_134k_balanced.json',
    'top_tape_143954': r'C:\Coding\kaggriculture-agent\top_tape_143954.json',
}

loaded_tapes = {}
for k, v in tapes.items():
    if v.endswith('.json'):
        with open(v, 'r', encoding='utf-8') as f:
            loaded_tapes[k] = json.load(f)

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

print("=== EVALUATING RAW TAPES VS STARTER (SEED 100 - Farmers Market + Bakery) ===")
for name, t_data in loaded_tapes.items():
    p_fn = make_tape_player(t_data)
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 100, "runTimeout": 120}, debug=True)
    env.run([p_fn, "starter"])
    p0 = env.steps[-1][0]["reward"]
    p1 = env.steps[-1][1]["reward"]
    status = env.steps[-1][0]["status"]
    print(f"  Tape: {name:<22} -> Reward = ${p0:>8,.0f} | Starter = ${p1:>5,.0f} | Status = {status}")
