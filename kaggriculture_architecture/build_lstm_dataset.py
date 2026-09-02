import json
import glob
import numpy as np
import os

paths = [
    r"C:\Users\GauravPatel\Downloads\1st september replays\*.json",
    r"C:\Coding\kaggriculture\data\*.json",
    r"C:\Coding\kaggriculture\*.json",
    r"C:\Coding\kaggriculture_architecture\our_replays\*.json"
]
files = []
for p in paths: files.extend(glob.glob(p))
files = list(set(files))

X_seqs = []
Y_seqs = []

print(f"Extracting LSTM Sequences from {len(files)} files...")

for f in files:
    try:
        with open(f, "r", encoding="utf-8") as tmp:
            data = json.load(tmp)
            
        final_obs = data["steps"][-1][0]["observation"]
        if "farms" not in final_obs: continue
        
        m0 = final_obs["farms"][0]["money"]
        m1 = final_obs["farms"][1]["money"]
        
        winner_money = max(m0, m1)
        if winner_money < 100000: continue
            
        winner_idx = 0 if m0 > m1 else 1
        
        # A game is 720 steps. We want 1 observation per day (30 days).
        x_game = []
        y_game = []
        
        for day in range(30):
            step = day * 24
            if step >= len(data["steps"]): break
            
            obs = data["steps"][step][0]["observation"]
            farm = obs.get("farms", [{}, {}])[winner_idx]
            priv = obs.get("private", [{}, {}])[winner_idx] if "private" in obs and isinstance(obs["private"], list) else obs.get("private", {})
            shed = priv.get("shed", {})
            seeds = priv.get("seeds", {})
            market = obs.get("market", {})
            prices = market.get("prices", {})
            
            vec = np.zeros(50, dtype=np.float32)
            vec[0] = step / 2000.0
            vec[1] = farm.get("money", 0) / 10000.0
            
            items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "COW", "SHEEP", "GOOSE"]
            for i, item in enumerate(items):
                vec[2 + i] = shed.get(item, 0) / 100.0
                vec[13 + i] = seeds.get(item, 0) / 100.0
                vec[24 + i] = prices.get(item, 0) / 100.0
                
            vec[35] = len(farm.get("hands", [])) / 10.0
            
            # Y labels (Target portfolio shifted by 2 days so it buys early)
            target_step = min(step + 48, len(data["steps"]) - 1)
            t_obs = data["steps"][target_step][0]["observation"]
            t_farm = t_obs.get("farms", [{}, {}])[winner_idx]
            t_priv = t_obs.get("private", [{}, {}])[winner_idx] if "private" in t_obs and isinstance(t_obs["private"], list) else t_obs.get("private", {})
            t_shed = t_priv.get("shed", {})
            t_seeds = t_priv.get("seeds", {})
            
            y_vec = np.zeros(9, dtype=np.float32)
            y_vec[0] = (t_shed.get("WHEAT", 0) + t_seeds.get("WHEAT", 0)) / 50.0
            y_vec[1] = (t_shed.get("CARROT", 0) + t_seeds.get("CARROT", 0)) / 50.0
            y_vec[2] = (t_shed.get("TOMATO", 0) + t_seeds.get("TOMATO", 0)) / 50.0
            y_vec[3] = (t_shed.get("STRAWBERRY", 0) + t_seeds.get("STRAWBERRY", 0)) / 50.0
            y_vec[4] = (t_shed.get("MELON", 0) + t_seeds.get("MELON", 0)) / 50.0
            y_vec[5] = (t_shed.get("GOOSE", 0) + t_seeds.get("GOOSE", 0)) / 20.0
            y_vec[6] = (t_shed.get("COW", 0) + t_seeds.get("COW", 0)) / 20.0
            y_vec[7] = (t_shed.get("SHEEP", 0) + t_seeds.get("SHEEP", 0)) / 20.0
            y_vec[8] = len(t_farm.get("hands", [])) / 10.0
            
            x_game.append(vec)
            y_game.append(y_vec)
            
        if len(x_game) == 30:
            X_seqs.append(np.array(x_game))
            Y_seqs.append(np.array(y_game))
            
    except Exception as e:
        continue

X_data = np.stack(X_seqs)
Y_data = np.stack(Y_seqs)

print(f"Extracted {X_data.shape[0]} full-game sequences!")
print(f"X shape: {X_data.shape} | Y shape: {Y_data.shape}")

np.save(r"C:\Coding\kaggriculture_architecture\X_seq.npy", X_data)
np.save(r"C:\Coding\kaggriculture_architecture\Y_seq.npy", Y_data)
print("Saved X_seq.npy and Y_seq.npy")
