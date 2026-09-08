import os
import json
import zipfile
import numpy as np
import subprocess
import pandas as pd
import gc

BOARD_SIZE = 10
CHUNK_SIZE = 50000 # Save every 50k frames to prevent RAM crash

# Fixed vocabulary for scalar features
ITEMS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "COW", "SHEEP", "GOOSE", "FERTILIZER"]
SHOPS = ["BAKERY", "BRUNCH_SPOT", "ICE_CREAM_SHOP", "PET_CAFE", "PIZZA_SHOP", "SMOOTHIE_SHOP", "FARMERS_MARKET", "YARN_STORE"]
CROP_TO_IDX = {"WHEAT": 1, "CARROT": 2, "TOMATO": 3, "STRAWBERRY": 4, "MELON": 5}
ANIM_TO_IDX = {"GOOSE": 1, "COW": 2, "SHEEP": 3}

def get_scalar_obs(obs, agent_idx):
    vec = np.zeros(100, dtype=np.float32)
    farm = obs["farms"][agent_idx]
    priv = obs.get("private", {})
    shed = priv.get("shed", {})
    seeds = priv.get("seeds", {})
    market = obs.get("market", {})
    
    vec[0] = obs.get("step", 0) / 720.0  # Normalized to true game length
    vec[1] = farm.get("money", 0) / 10000.0
    vec[2] = farm.get("hires_today", 0)
    vec[3] = len(farm.get("hands", []))
    
    idx = 4
    for item in ITEMS:
        vec[idx] = shed.get(item, 0) / 100.0; idx += 1
        vec[idx] = seeds.get(item, 0) / 100.0; idx += 1
        vec[idx] = market.get("prices", {}).get(item, 0) / 100.0; idx += 1
        vec[idx] = market.get("inventory", {}).get(item, 0) / 10000.0; idx += 1
        
    town = obs.get("town", {}).get("unlocked_shops", [])
    for shop in town:
        if shop in SHOPS:
            vec[idx + SHOPS.index(shop)] += 1.0
            
    return vec

def get_spatial_obs(obs, agent_idx):
    # 20 channels for lossless state representation
    # Using float16 to save 50% RAM
    grid = np.zeros((20, BOARD_SIZE, BOARD_SIZE), dtype=np.float16)
    farm = obs["farms"][agent_idx]
    day = obs.get("day", 0)
    
    # Farmer and hands
    fx, fy = farm.get("farmer", [0, 0])
    grid[0, fy, fx] = 1
    for hx, hy in farm.get("hands", []):
        grid[1, hy, hx] += 1
        
    # Shed
    for sy in [4, 5]:
        for sx in [4, 5]:
            grid[2, sy, sx] = 1
            
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            t = farm["tiles"][y][x]
            if t == "LOCKED": 
                grid[3, y, x] = 1
            elif isinstance(t, dict):
                kind = t.get("kind")
                if kind == "WEED":
                    grid[4, y, x] = 1
                elif kind == "PLANT":
                    grid[5, y, x] = CROP_TO_IDX.get(t.get("crop"), 0)
                    grid[6, y, x] = day - t.get("planted_day", day)
                    grid[7, y, x] = 1 if t.get("watered_today") else 0
                    grid[8, y, x] = t.get("consecutive_unwatered", 0)
                    grid[9, y, x] = t.get("yield_units", 0)
                    fert = t.get("fertilized_until_day", -1)
                    grid[10, y, x] = max(0, fert - day) if fert != -1 else 0
                elif kind in ["COOP", "PASTURE"]:
                    grid[11, y, x] = 1 if kind == "COOP" else 0
                    grid[12, y, x] = 1 if kind == "PASTURE" else 0
                    anim = t.get("animal")
                    if anim:
                        grid[13, y, x] = ANIM_TO_IDX.get(anim, 0)
                        grid[14, y, x] = 1 if t.get("fed_today") else 0
                        grid[15, y, x] = 1 if t.get("cared_today") else 0
                        grid[16, y, x] = t.get("yield_units", 0)
                        grid[17, y, x] = t.get("consecutive_unfed", 0)
                        grid[18, y, x] = 1 if t.get("fertilizer_available") else 0
                        grid[19, y, x] = t.get("pending_care_bonus", 0)
    return grid

def parse_macro_action(market_cmds, prev_shed, num_hands):
    y = np.zeros(20, dtype=np.float32)
    buy_seed_idx = {"WHEAT": 0, "CARROT": 1, "TOMATO": 2, "STRAWBERRY": 3, "MELON": 4}
    buy_anim_idx = {"GOOSE": 5, "COW": 6, "SHEEP": 7}
    sell_idx = {k: 8+i for i, k in enumerate(["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"])}
    hires = 0
    buy_land = 0
    for cmd in market_cmds:
        ctype = cmd[0]
        if ctype == 'HIRE':
            hires += 1
        elif ctype == 'BUY_LAND':
            buy_land += 1
        elif ctype == 'BUY_SEED':
            item, amt = cmd[1], cmd[2]
            if item in buy_seed_idx: y[buy_seed_idx[item]] = amt
        elif ctype == 'BUY_ANIMAL':
            item, amt = cmd[1], cmd[2]
            if item in buy_anim_idx: y[buy_anim_idx[item]] = amt
        elif ctype == 'SELL':
            item, amt = cmd[1], cmd[2]
            if item in sell_idx:
                had = prev_shed.get(item, 0)
                if had > 0:
                    y[sell_idx[item]] = min(1.0, amt / float(had)) # Sell ratio
    y[18] = hires
    y[19] = buy_land
    return y

def load_elite_teams():
    df = pd.read_csv("kaggriculture-publicleaderboard.csv")
    elite = df[df["Score"] >= 1900]["TeamName"].unique()
    print(f"Loaded {len(elite)} Elite Teams (>= 1900 Elo).")
    return set(elite)

def build_dataset():
    elite_teams = load_elite_teams()
    manifest = pd.read_csv("manifest.csv")
    
    # Filter for datasets that actually have top scores >= 1900
    manifest = manifest[manifest["top_avg_score"] >= 1900]
    print(f"Found {len(manifest)} datasets containing Elite teams.")
    
    chunk_idx = 0
    X_scalar, X_spatial, Y_macro, Y_micro = [], [], [], []
    
    def save_chunk():
        nonlocal chunk_idx, X_scalar, X_spatial, Y_macro, Y_micro
        if len(X_scalar) == 0: return
        print(f"Saving chunk {chunk_idx} with {len(X_scalar)} frames...")
        np.savez_compressed(
            f"data/elite_1900_chunk_{chunk_idx}.npz", 
            scalar=np.array(X_scalar, dtype=np.float32),
            spatial=np.array(X_spatial, dtype=np.float16),
            macro=np.array(Y_macro, dtype=np.float32),
            micro=np.array(Y_micro) # Array of JSON strings
        )
        chunk_idx += 1
        X_scalar, X_spatial, Y_macro, Y_micro = [], [], [], []
        gc.collect()

    os.makedirs("data", exist_ok=True)

    for _, row in manifest.iterrows():
        slug = row["daily_dataset_slug"]
        slug_full = f"kaggle/{slug}"
        zip_name = f"{slug}.zip"
        
        print(f"\nProcessing {slug}...")
        try:
            if not os.path.exists(zip_name):
                subprocess.run(["kaggle", "datasets", "download", "-d", slug_full], check=True)
            
            with zipfile.ZipFile(zip_name, 'r') as z:
                files = [f for f in z.namelist() if f.endswith('.json')]
                for file in files:
                    try:
                        with z.open(file) as f:
                            replay = json.load(f)
                            
                        if "info" not in replay or "TeamNames" not in replay["info"]: continue
                        teams = replay["info"]["TeamNames"]
                        
                        elite_idxs = []
                        if teams[0] in elite_teams: elite_idxs.append(0)
                        if teams[1] in elite_teams: elite_idxs.append(1)
                        if not elite_idxs: continue
                        
                        for step_i in range(1, len(replay['steps'])):
                            for idx in elite_idxs:
                                obs = replay['steps'][step_i-1][idx]['observation']
                                action = replay['steps'][step_i][idx].get('action', {})
                                
                                market_cmds = action.get('market', []) if isinstance(action, dict) else []
                                
                                prev_shed = obs.get("private", {}).get("shed", {})
                                num_hands = len(obs["farms"][idx].get("hands", []))
                                
                                x_scal = get_scalar_obs(obs, idx)
                                x_spat = get_spatial_obs(obs, idx)
                                y_mac = parse_macro_action(market_cmds, prev_shed, num_hands)
                                y_mic = json.dumps(action) # Lossless micro preservation
                                
                                X_scalar.append(x_scal)
                                X_spatial.append(x_spat)
                                Y_macro.append(y_mac)
                                Y_micro.append(y_mic)
                                
                                if len(X_scalar) >= CHUNK_SIZE:
                                    save_chunk()
                    except Exception as e:
                        pass # Skip corrupted JSONs
            
            # Clean up the 20GB zip to save disk space
            os.remove(zip_name)
        except Exception as e:
            print(f"Failed to process dataset {slug}: {e}")
            if os.path.exists(zip_name): os.remove(zip_name)
            
    # Save any remaining frames
    save_chunk()
    print("\nDataset generation completed successfully!")

if __name__ == '__main__':
    build_dataset()
