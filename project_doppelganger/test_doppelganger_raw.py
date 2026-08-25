import json
import sys
import os

sys.path.insert(0, r'C:\Coding')
from kaggle_environments import make

with open(r'C:\Coding\project_doppelganger\ryo_consensus_cows_2_sheep_2_quads_2.json', 'r', encoding='utf-8') as f:
    TAPE_ROUTE_1 = json.load(f)

with open(r'C:\Coding\project_doppelganger\ryo_consensus_cows_3_sheep_3_quads_1.json', 'r', encoding='utf-8') as f:
    TAPE_ROUTE_2 = json.load(f)

def ryo_doppelganger_agent(obs):
    step = obs.get("step", 0)
    player = obs.get("player", 0)
    farms = obs.get("farms", [])
    live_hands = len(farms[player].get("hands", [])) if len(farms) > player else 0
    
    # Route Selection
    shops = (obs.get("town") or {}).get("unlocked_shops", []) or []
    if len(shops) >= 1 and shops[:1] == ["YARN_STORE"]:
        active_tape = TAPE_ROUTE_2
    else:
        active_tape = TAPE_ROUTE_1
        
    if step < len(active_tape):
        act = active_tape[step]
        act_copy = {
            "farmer": list(act.get("farmer", ["PASS"])),
            "hands": list(act.get("hands", []))[:live_hands],
            "market": list(act.get("market", []))[:10]
        }
        while len(act_copy["hands"]) < live_hands:
            act_copy["hands"].append(["PASS"])
        return act_copy
    return {"farmer": ["PASS"], "hands": [["PASS"]] * live_hands, "market": []}

test_seeds = [1, 7, 13, 24, 42, 55, 100, 144, 2024, 65536]

print("=" * 80)
print("TESTING RYO HASEGAWA DOPPELGANGER AGENT VS STARTER & RANDOM")
print("=" * 80)

scores_starter = []
scores_random = []

for seed in test_seeds:
    # Vs Starter
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60}, debug=False)
    env.run([ryo_doppelganger_agent, "starter"])
    p0 = env.steps[-1][0]["reward"]
    p1 = env.steps[-1][1]["reward"]
    status = env.steps[-1][0]["status"]
    scores_starter.append(p0)
    print(f"Seed {seed:05d} vs Starter: Doppelganger = ${p0:>8,.0f} | Starter = ${p1:>5,.0f} | Status = {status}")

print(f"\nDoppelganger Average vs Starter: ${sum(scores_starter)/len(scores_starter):,.0f} (Peak: ${max(scores_starter):,.0f})")

for seed in test_seeds[:5]:
    # Vs Random
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60}, debug=False)
    env.run([ryo_doppelganger_agent, "random"])
    p0 = env.steps[-1][0]["reward"]
    p1 = env.steps[-1][1]["reward"]
    scores_random.append(p0)
    print(f"Seed {seed:05d} vs Random:  Doppelganger = ${p0:>8,.0f} | Random  = ${p1:>5,.0f}")

print(f"\nDoppelganger Average vs Random:  ${sum(scores_random)/len(scores_random):,.0f}")
