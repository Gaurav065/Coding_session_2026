import json
import numpy as np
import glob
import os

BOARD_SIZE = 10

def get_scalar_obs(obs, agent_idx):
    vec = np.zeros(50, dtype=np.float32)
    farm = obs["farms"][agent_idx]
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

def get_spatial_obs(obs, agent_idx):
    grid = np.zeros((4, BOARD_SIZE, BOARD_SIZE), dtype=np.float32)
    farm = obs["farms"][agent_idx]
    crop_to_idx = {"WHEAT": 1, "CARROT": 2, "TOMATO": 3, "STRAWBERRY": 4, "MELON": 5}
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            tile = farm["tiles"][y][x]
            if tile == "LOCKED":
                grid[3, y, x] = -1
            elif isinstance(tile, dict):
                if tile.get("kind") == "PLANT":
                    crop = tile.get("crop")
                    grid[0, y, x] = crop_to_idx.get(crop, 0)
                    grid[1, y, x] = tile.get("yield_units", 0)
                elif tile.get("kind") == "WEED":
                    grid[3, y, x] = 1
                elif tile.get("kind") in ["COOP", "PASTURE"]:
                    grid[3, y, x] = 2
                    if "animal" in tile:
                        grid[0, y, x] = 6 
                        grid[1, y, x] = tile.get("yield_units", 0)
    fx, fy = farm.get("farmer", [0, 0])
    if 0 <= fx < BOARD_SIZE and 0 <= fy < BOARD_SIZE:
        grid[2, fy, fx] = 1
    for h in farm.get("hands", []):
        hx, hy = h[0], h[1]
        if 0 <= hx < BOARD_SIZE and 0 <= hy < BOARD_SIZE:
            grid[2, hy, hx] = 1
    return grid

def parse_action(market_cmds, prev_shed, num_hands):
    y = np.zeros(17, dtype=np.float32)
    buy_seed_idx = {"WHEAT": 0, "CARROT": 1, "TOMATO": 2, "STRAWBERRY": 3, "MELON": 4}
    buy_anim_idx = {"GOOSE": 5, "COW": 6, "SHEEP": 7}
    sell_idx = {"WHEAT": 9, "CARROT": 10, "TOMATO": 11, "STRAWBERRY": 12, "MELON": 13, "EGG": 14, "MILK": 15, "WOOL": 16}
    hires = 0
    for cmd in market_cmds:
        ctype = cmd[0]
        if ctype == 'HIRE':
            hires += 1
        elif ctype == 'BUY_SEED':
            item, amt = cmd[1], cmd[2]
            if item in buy_seed_idx: y[buy_seed_idx[item]] = min(1.0, amt / 50.0)
        elif ctype == 'BUY_ANIMAL':
            item, amt = cmd[1], cmd[2]
            if item in buy_anim_idx: y[buy_anim_idx[item]] = min(1.0, amt / 20.0)
        elif ctype == 'SELL':
            item, amt = cmd[1], cmd[2]
            if item in sell_idx:
                had = prev_shed.get(item, 0)
                if had > 0:
                    y[sell_idx[item]] = min(1.0, amt / had)
                else:
                    y[sell_idx[item]] = 1.0 
    y[8] = (num_hands + hires) / 10.0
    return y

def parse_replay_folder(folder_path, max_replays=1000):
    X_scalar, X_spatial, Y = [], [], []
    files = glob.glob(f"{folder_path}/*.json")
    print(f"Found {len(files)} JSON files in {folder_path}")
    
    for file in files[:max_replays]:
        try:
            with open(file, 'r', encoding='utf-8') as f:
                replay = json.load(f)
                
            if 'steps' not in replay:
                print(f"Skipping {file} - No 'steps' found (likely metadata or error page)")
                continue
                
            r0 = replay['steps'][-1][0]['reward']
            r1 = replay['steps'][-1][1]['reward']
            if r0 is None or r1 is None: continue
            winner_idx = 0 if r0 > r1 else 1
            
            for step_i in range(1, len(replay['steps'])):
                obs = replay['steps'][step_i-1][winner_idx]['observation']
                action = replay['steps'][step_i][winner_idx].get('action', {})
                market_cmds = []
                if action and isinstance(action, dict) and action.get('market'):
                    market_cmds = action['market']
                    
                if not market_cmds:
                    continue
                    
                prev_shed = obs.get("private", {}).get("shed", {})
                num_hands = len(obs["farms"][winner_idx].get("hands", []))
                
                x_scal = get_scalar_obs(obs, winner_idx)
                x_spat = get_spatial_obs(obs, winner_idx)
                y_act = parse_action(market_cmds, prev_shed, num_hands)
                
                X_scalar.append(x_scal)
                X_spatial.append(x_spat)
                Y.append(y_act)
                
        except Exception as e:
            print(f"Failed to parse {file}: {e}")
            
    return np.array(X_scalar), np.array(X_spatial), np.array(Y)

if __name__ == "__main__":
    print("Testing parser on our_replays...")
    X_scal, X_spat, Y = parse_replay_folder("our_replays")
    print(f"Extracted {len(X_scal)} action frames from top replays.")
    
    if len(X_scal) > 0:
        np.save("X_scalar.npy", X_scal)
        np.save("X_spatial.npy", X_spat)
        np.save("Y_actions.npy", Y)
        print(f"Saved tensors! X_scalar shape: {X_scal.shape}, X_spatial shape: {X_spat.shape}")
