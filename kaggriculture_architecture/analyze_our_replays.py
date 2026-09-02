import json
import os
import glob
from collections import defaultdict

replay_dir = r"C:\Coding\kaggriculture_architecture\our_replays"
files = glob.glob(os.path.join(replay_dir, "*.json"))

def analyze_replay(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return None
        
    steps = data.get("steps", [])
    if not steps: return None
    
    # In these replays, one of the players is OUR agent (Phase E / All phase)
    # Actually, we don't know which player is ours unless we check the submission ID in the team list, 
    # but let's just analyze both players and see who won, or print both!
    
    final_step = steps[-1]
    obs = final_step[0]["observation"]
    if "farms" not in obs: return None
    
    money_0 = obs["farms"][0]["money"]
    money_1 = obs["farms"][1]["money"]
    
    stats_0 = {"money": money_0, "hands": 0, "seeds": defaultdict(int), "animals": defaultdict(int)}
    stats_1 = {"money": money_1, "hands": 0, "seeds": defaultdict(int), "animals": defaultdict(int)}
    
    for step in steps:
        obs = step[0]["observation"]
        if "farms" not in obs: continue
        
        for p, stats in zip([0, 1], [stats_0, stats_1]):
            farm = obs["farms"][p]
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
                    
    return {
        "file": os.path.basename(file_path),
        "P0": {"money": money_0, "hands": stats_0["hands"], "seeds": dict(stats_0["seeds"]), "animals": dict(stats_0["animals"])},
        "P1": {"money": money_1, "hands": stats_1["hands"], "seeds": dict(stats_1["seeds"]), "animals": dict(stats_1["animals"])}
    }

results = []
for f in files:
    res = analyze_replay(f)
    if res: results.append(res)
    
print(f"Analyzed {len(results)} replays.")
for r in results:
    print(f"--- {r['file']} ---")
    print(f"P0: Money {r['P0']['money']} | Hands {r['P0']['hands']} | Animals {r['P0']['animals']} | Seeds {r['P0']['seeds']}")
    print(f"P1: Money {r['P1']['money']} | Hands {r['P1']['hands']} | Animals {r['P1']['animals']} | Seeds {r['P1']['seeds']}")
