import json
import sys
import os

sys.path.insert(0, r'C:\Coding')
from kaggle_environments import make

with open(r'C:\Coding\kaggriculture-agent\tape_165k_straw_cow.json', 'r', encoding='utf-8') as f:
    TAPE_TOP_AGRO = json.load(f)

with open(r'C:\Coding\kaggriculture-agent\tape_151k.json', 'r', encoding='utf-8') as f:
    TAPE_TOP_MELON = json.load(f)

def top_opponent_player(obs):
    step = obs.get("step", 0)
    p = obs.get("player", 0)
    farms = obs.get("farms", [])
    lh = len(farms[p].get("hands", [])) if len(farms) > p else 0
    
    # Check shop roll
    shops = (obs.get("town") or {}).get("unlocked_shops", []) or []
    if shops.count("BAKERY") + shops.count("BRUNCH_SPOT") >= 2:
        tape = TAPE_TOP_MELON
    else:
        tape = TAPE_TOP_AGRO
        
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

test_seeds = [1, 7, 13, 24, 42, 55, 100, 144, 2024, 65536]

print("=" * 85)
print("BENCHMARKING TOP OPPONENT DOPPELGANGER AGENT (10 SEEDS VS STARTER)")
print("=" * 85)

scores = []
margins = []

for seed in test_seeds:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60})
    env.run([top_opponent_player, "starter"])
    p0 = env.steps[-1][0]["reward"]
    p1 = env.steps[-1][1]["reward"]
    status = env.steps[-1][0]["status"]
    scores.append(p0)
    margins.append(p0 - p1)
    print(f"Seed {seed:05d} | Doppelganger = ${p0:>8,.0f} | Starter = ${p1:>5,.0f} | Margin = +${p0-p1:>8,.0f} | {status}")

print("=" * 85)
print(f"TOP OPPONENT DOPPELGANGER AVERAGE: ${sum(scores)/len(scores):>10,.0f}")
print(f"TOP OPPONENT DOPPELGANGER PEAK:    ${max(scores):>10,.0f}")
print(f"TOP OPPONENT DOPPELGANGER MIN:     ${min(scores):>10,.0f}")
print("=" * 85)
