import json
import sys

sys.path.insert(0, r'C:\Coding')
from project_aegis.tape_loader import _ACTIONS_10C4S_3Q, _ACTIONS_8C6S_3Q, _ACTIONS_6C12S_4Q_FIRST_YARN, _ACTIONS_6C12S_4Q_SECOND_YARN, _ACTIONS_6C8S_3Q

with open(r'C:\Coding\kaggriculture-agent\tape_151k.json', 'r', encoding='utf-8') as f:
    TAPE_151K = json.load(f)

with open(r'C:\Coding\kaggriculture-agent\tape_165k_straw_cow.json', 'r', encoding='utf-8') as f:
    TAPE_165K = json.load(f)

tapes = {
    '10c4s_3q': _ACTIONS_10C4S_3Q,
    '8c6s_3q': _ACTIONS_8C6S_3Q,
    '6c12s_1st_yarn': _ACTIONS_6C12S_4Q_FIRST_YARN,
    '6c12s_2nd_yarn': _ACTIONS_6C12S_4Q_SECOND_YARN,
    '6c8s_3rd_yarn': _ACTIONS_6C8S_3Q,
    'tape_151k': TAPE_151K,
    'tape_165k': TAPE_165K,
}

print("=== COMPARING DAY 0 (STEPS 0-23) ACROSS ALL TAPES ===")
for step in range(24):
    row = [f"Step {step:02d}"]
    actions = [f"{name}: farmer={t[step].get('farmer', ['PASS'])}" for name, t in tapes.items()]
    # Check if all Aegis tapes match
    aegis_actions = [tapes[k][step].get('farmer', ['PASS']) for k in ['10c4s_3q', '8c6s_3q', '6c12s_1st_yarn', '6c12s_2nd_yarn', '6c8s_3rd_yarn']]
    all_aegis_same = all(a == aegis_actions[0] for a in aegis_actions)
    
    t151_action = TAPE_151K[step].get('farmer', ['PASS'])
    t165_action = TAPE_165K[step].get('farmer', ['PASS'])
    
    print(f"Step {step:02d} | Aegis Base Match: {all_aegis_same!s:<5} (Aegis={aegis_actions[0]}) | 151k={t151_action} | 165k={t165_action}")
