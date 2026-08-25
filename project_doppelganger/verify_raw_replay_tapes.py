import json
import sys
import os

sys.path.insert(0, r'C:\Coding')
from kaggle_environments import make

with open(r'C:\Coding\project_doppelganger\ryo_standard_route_master.json', 'r', encoding='utf-8') as f:
    TAPE_STD = json.load(f)

with open(r'C:\Coding\project_doppelganger\ryo_yarn_route_master.json', 'r', encoding='utf-8') as f:
    TAPE_YARN = json.load(f)

# Also extract the raw actions from the #1 highest scoring match directly
with open(r'C:\Users\GauravPatel\Downloads\top_player\94436066.json', 'r', encoding='utf-8') as f:
    data_157k = json.load(f)
seat_157k = 0 if data_157k['info']['TeamNames'][0] == 'Ryo Hasegawa' else 1
TAPE_157K_RAW = [s[seat_157k].get('action') or {"farmer": ["PASS"], "hands": [], "market": []} for s in data_157k['steps']]

with open(r'C:\Users\GauravPatel\Downloads\top_player\94426282.json', 'r', encoding='utf-8') as f:
    data_168k = json.load(f)
seat_168k = 0 if data_168k['info']['TeamNames'][0] == 'Ryo Hasegawa' else 1
TAPE_168K_RAW = [s[seat_168k].get('action') or {"farmer": ["PASS"], "hands": [], "market": []} for s in data_168k['steps']]

def make_player(tape):
    def player(obs):
        step = obs.get("step", 0)
        p = obs.get("player", 0)
        farms = obs.get("farms", [])
        lh = len(farms[p].get("hands", [])) if len(farms) > p else 0
        if step < len(tape):
            act = tape[step]
            act_c = {
                "farmer": list(act.get("farmer", ["PASS"])),
                "hands": list(act.get("hands", []))[:lh],
                "market": list(act.get("market", []))[:10]
            }
            while len(act_c["hands"]) < lh:
                act_c["hands"].append(["PASS"])
            return act_c
        return {"farmer": ["PASS"], "hands": [["PASS"]]*lh, "market": []}
    return player

print("=== TESTING RAW REPLAY TAPES ON THEIR ORIGINAL SEEDS ===")

# Match 94436066 seed test
p_157 = make_player(TAPE_157K_RAW)
env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 94436066, "runTimeout": 60})
env.run([p_157, "starter"])
print(f"Match 94436066 Replay Tape vs Starter: ${env.steps[-1][0]['reward']:,.0f}")

# Match 94426282 seed test
p_168 = make_player(TAPE_168K_RAW)
env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 94426282, "runTimeout": 60})
env.run([p_168, "starter"])
print(f"Match 94426282 Replay Tape vs Starter: ${env.steps[-1][0]['reward']:,.0f}")

print("\n=== TESTING MASTER EXTRACTED TAPES ACROSS MULTIPLE SEEDS ===")
for seed in [1, 7, 13, 24, 42, 100, 144, 2024]:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60})
    env.run([p_157, "starter"])
    print(f"Seed {seed:5d} | Std Tape Score: ${env.steps[-1][0]['reward']:>8,.0f} | Status: {env.steps[-1][0]['status']}")
