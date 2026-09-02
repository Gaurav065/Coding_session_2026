import json
import os
import glob
from collections import defaultdict

replay_dir = r"C:\Users\GauravPatel\Downloads\1st september replays"
files = glob.glob(os.path.join(replay_dir, "*.json"))[:10]  # Let's start with 10 for speed

def analyze_replay(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return None
        
    steps = data.get("steps", [])
    if not steps: return None
    
    # Find who won
    final_step = steps[-1]
    obs = final_step[0]["observation"]
    if "farms" not in obs: return None
    
    money_0 = obs["farms"][0]["money"]
    money_1 = obs["farms"][1]["money"]
    
    winner = 0 if money_0 > money_1 else 1
    winner_money = max(money_0, money_1)
    
    # Trace the winner's portfolio over time
    # Specifically, look at day 1, day 10, day 20, day 30 (step 0, 240, 480, 719)
    # Actually let's just track how many hands they hire max, and what seeds/animals they hold max
    
    max_hands = 0
    max_seeds = defaultdict(int)
    max_animals = defaultdict(int)
    
    for step in steps:
        obs = step[0]["observation"]
        if "farms" not in obs: continue
        
        farm = obs["farms"][winner]
        hands = len(farm.get("hands", []))
        if hands > max_hands:
            max_hands = hands
            
        # Get private state
        # In Kaggle replays, private state is in step[player]["observation"]["private"] maybe?
        # Let's check step[winner]["observation"] if "private" is there
        player_obs = step[winner]["observation"]
        if "private" in player_obs:
            seeds = player_obs["private"].get("seeds", {})
            for k, v in seeds.items():
                if v > max_seeds[k]: max_seeds[k] = v
                
            shed = player_obs["private"].get("shed", {})
            for k in ["COW", "SHEEP", "GOOSE"]:
                if shed.get(k, 0) > max_animals[k]: max_animals[k] = shed[k]
                
    return {
        "file": os.path.basename(file_path),
        "money": winner_money,
        "hands": max_hands,
        "seeds": dict(max_seeds),
        "animals": dict(max_animals)
    }

results = []
for f in files:
    res = analyze_replay(f)
    if res: results.append(res)
    
print(f"Analyzed {len(results)} replays.")
for r in results:
    print(f"Winner Money: {r['money']}, Hands: {r['hands']}, Animals: {r['animals']}, Seeds: {r['seeds']}")
