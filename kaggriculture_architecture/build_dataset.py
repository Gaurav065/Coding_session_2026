import json
import os
import glob
import numpy as np

# 1. Define paths to all replays
paths = [
    r"C:\Users\GauravPatel\Downloads\1st september replays\*.json",
    r"C:\Coding\kaggriculture\data\*.json",
    r"C:\Coding\kaggriculture\*.json",
    r"C:\Coding\kaggriculture_architecture\our_replays\*.json"
]

files = []
for p in paths:
    files.extend(glob.glob(p))
files = list(set(files)) # Remove duplicates

print(f"Found {len(files)} total JSON replays to process.")

def extract_macro_targets(obs_dict, player_idx):
    farm = obs_dict["farms"][player_idx]
    priv = obs_dict.get("private", {})
    shed = priv.get("shed", {})
    seeds = priv.get("seeds", {})
    
    planted = {"WHEAT": 0, "CARROT": 0, "TOMATO": 0, "STRAWBERRY": 0, "MELON": 0}
    for row in farm.get("tiles", []):
        for tile in row:
            if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                crop = tile.get("crop")
                if crop in planted: planted[crop] += 1
                    
    targets = {
        "WHEAT": planted["WHEAT"] + seeds.get("WHEAT", 0),
        "CARROT": planted["CARROT"] + seeds.get("CARROT", 0),
        "TOMATO": planted["TOMATO"] + seeds.get("TOMATO", 0),
        "STRAWBERRY": planted["STRAWBERRY"] + seeds.get("STRAWBERRY", 0),
        "MELON": planted["MELON"] + seeds.get("MELON", 0),
        "GOOSE": shed.get("GOOSE", 0),
        "COW": shed.get("COW", 0),
        "SHEEP": shed.get("SHEEP", 0),
        "HIRE": len(farm.get("hands", []))
    }
    return targets

def get_observation_vector(obs, player_idx):
    vec = np.zeros(50, dtype=np.float32)
    farm = obs["farms"][player_idx]
    priv = obs.get("private", {})
    shed = priv.get("shed", {})
    seeds = priv.get("seeds", {})
    market = obs.get("market", {})
    
    vec[0] = obs.get("step", 0) / 2000.0
    vec[1] = farm.get("money", 0) / 10000.0
    
    items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "COW", "SHEEP", "GOOSE"]
    for i, item in enumerate(items):
        vec[2 + i] = shed.get(item, 0) / 100.0
        vec[13 + i] = seeds.get(item, 0) / 100.0
        prices = market.get("prices", {})
        vec[24 + i] = prices.get(item, 0) / 100.0
        
    vec[35] = len(farm.get("hands", [])) / 10.0
    return vec

X_data = []
Y_data = []
processed = 0
skipped = 0

for f in files:
    try:
        with open(f, "r", encoding="utf-8") as tmp:
            data = json.load(tmp)
            
        final_obs = data["steps"][-1][0]["observation"]
        if "farms" not in final_obs: continue
        
        m0 = final_obs["farms"][0]["money"]
        m1 = final_obs["farms"][1]["money"]
        
        # Only clone if the winner made over $100k, guaranteeing high-quality grandmaster data
        if max(m0, m1) < 100000:
            skipped += 1
            continue
            
        winner_idx = 0 if m0 > m1 else 1
        
        for step_data in data["steps"]:
            obs = step_data[0]["observation"]
            step_num = obs.get("step", 0)
            if step_num % 24 == 0:
                vec = get_observation_vector(obs, winner_idx)
                targets = extract_macro_targets(obs, winner_idx)
                
                y_vec = np.zeros(17, dtype=np.float32)
                y_vec[0] = targets["WHEAT"] / 50.0
                y_vec[1] = targets["CARROT"] / 50.0
                y_vec[2] = targets["TOMATO"] / 50.0
                y_vec[3] = targets["STRAWBERRY"] / 50.0
                y_vec[4] = targets["MELON"] / 50.0
                y_vec[5] = targets["GOOSE"] / 20.0
                y_vec[6] = targets["COW"] / 20.0
                y_vec[7] = targets["SHEEP"] / 20.0
                y_vec[8] = targets["HIRE"] / 10.0
                for i in range(9, 17): y_vec[i] = 1.0 
                
                X_data.append(vec)
                Y_data.append(y_vec)
        processed += 1
    except Exception as e:
        skipped += 1

print(f"Successfully processed {processed} high-ELO replays (Skipped {skipped} low-score replays).")
print(f"Extracted {len(X_data)} macro-steps of training data.")

X_np = np.array(X_data, dtype=np.float32)
Y_np = np.array(Y_data, dtype=np.float32)

np.save("X_data.npy", X_np)
np.save("Y_data.npy", Y_np)
print("Saved X_data.npy and Y_data.npy")
