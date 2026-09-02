import json
import os
import glob
from collections import defaultdict
import statistics

replay_dir = r"C:\Coding\kaggriculture_architecture\our_replays"
files = glob.glob(os.path.join(replay_dir, "episode-*.json"))

OUR_TARGETS = {'CARROT': 2, 'MELON': 12, 'STRAWBERRY': 6, 'TOMATO': 0, 'WHEAT': 7}

def identify_our_agent(p0_seeds, p1_seeds):
    def score(seeds):
        return sum(1 for k, v in OUR_TARGETS.items() if seeds.get(k, 0) == v)
    
    s0 = score(p0_seeds)
    s1 = score(p1_seeds)
    
    if s0 > s1: return 0
    if s1 > s0: return 1
    return 0

results = []

for file_path in files:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        continue
        
    steps = data.get("steps", [])
    if not steps: continue
    
    final_step = steps[-1]
    obs = final_step[0]["observation"]
    if "farms" not in obs: continue
    
    m0 = obs["farms"][0]["money"]
    m1 = obs["farms"][1]["money"]
    
    s0 = {"hands": 0, "seeds": defaultdict(int), "animals": defaultdict(int)}
    s1 = {"hands": 0, "seeds": defaultdict(int), "animals": defaultdict(int)}
    
    for step in steps:
        step_obs = step[0]["observation"]
        if "farms" not in step_obs: continue
        
        for p, stats in zip([0, 1], [s0, s1]):
            farm = step_obs["farms"][p]
            hands = len(farm.get("hands", []))
            if hands > stats["hands"]:
                stats["hands"] = hands
                
            player_obs = step[p]["observation"]
            if "private" in player_obs:
                seeds = player_obs["private"].get("seeds", {})
                for k, v in seeds.items():
                    if v > stats["seeds"][k]: stats["seeds"][k] = v
                    
                shed = player_obs["private"].get("shed", {})
                for k in ["COW", "SHEEP", "GOOSE"]:
                    if shed.get(k, 0) > stats["animals"][k]: stats["animals"][k] = shed[k]
                    
    our_idx = identify_our_agent(s0["seeds"], s1["seeds"])
    opp_idx = 1 - our_idx
    
    our_money = m0 if our_idx == 0 else m1
    opp_money = m1 if our_idx == 0 else m0
    
    our_stats = s0 if our_idx == 0 else s1
    opp_stats = s1 if our_idx == 0 else s0
    
    margin = our_money - opp_money
    
    if margin > 20000:
        cat = "Good Win"
    elif margin > 0:
        cat = "Marginal Win"
    elif margin > -20000:
        cat = "Marginal Loss"
    else:
        cat = "Bad Loss"
        
    results.append({
        "file": os.path.basename(file_path),
        "our_money": our_money,
        "opp_money": opp_money,
        "margin": margin,
        "category": cat,
        "opp_hands": opp_stats["hands"],
        "opp_wheat": opp_stats["seeds"].get("WHEAT", 0),
        "opp_melon": opp_stats["seeds"].get("MELON", 0),
        "opp_strawberry": opp_stats["seeds"].get("STRAWBERRY", 0),
        "opp_carrot": opp_stats["seeds"].get("CARROT", 0),
        "opp_tomato": opp_stats["seeds"].get("TOMATO", 0),
        "opp_cows": opp_stats["animals"].get("COW", 0),
        "opp_sheep": opp_stats["animals"].get("SHEEP", 0)
    })

categories = {"Good Win": [], "Marginal Win": [], "Marginal Loss": [], "Bad Loss": []}
for r in results:
    categories[r["category"]].append(r)

print(f"Total Replays Analyzed: {len(results)}")
print("-" * 50)

for cat in ["Good Win", "Marginal Win", "Marginal Loss", "Bad Loss"]:
    subset = categories[cat]
    count = len(subset)
    print(f"=== {cat} ({count} matches) ===")
    if count == 0: continue
    
    avg_margin = statistics.mean([x["margin"] for x in subset])
    avg_opp_hands = statistics.mean([x["opp_hands"] for x in subset])
    avg_opp_wheat = statistics.mean([x["opp_wheat"] for x in subset])
    avg_opp_melon = statistics.mean([x["opp_melon"] for x in subset])
    avg_opp_straw = statistics.mean([x["opp_strawberry"] for x in subset])
    avg_opp_carrot = statistics.mean([x["opp_carrot"] for x in subset])
    
    print(f"  Avg Margin: {avg_margin:+.0f}")
    print(f"  Opponent Average Profile:")
    print(f"    Hands: {avg_opp_hands:.1f} | Wheat: {avg_opp_wheat:.1f} | Melon: {avg_opp_melon:.1f} | Strawberry: {avg_opp_straw:.1f}")
    
    print(f"  Notable opponents in this category:")
    for r in subset[:3]:
        print(f"    vs Opponent (Scored {r['opp_money']:.0f}): {r['opp_hands']} Hands | {r['opp_wheat']} Wheat, {r['opp_strawberry']} Strawberry, {r['opp_melon']} Melon, {r['opp_carrot']} Carrot")
    print()
