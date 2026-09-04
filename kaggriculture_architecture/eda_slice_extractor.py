import json
import glob
import pandas as pd
import numpy as np
import os

def extract_eda_metrics(folder_path, output_csv="eda_metrics.csv"):
    print(f"Scanning {folder_path} for replays...")
    files = glob.glob(f"{folder_path}/*.json")
    print(f"Found {len(files)} replays to process.")
    
    records = []
    
    for file_idx, file in enumerate(files):
        if "kernel" in file or "obs" in file: continue # Skip metadata files
        
        try:
            with open(file, 'r', encoding='utf-8') as f:
                replay = json.load(f)
            if 'steps' not in replay: continue
            
            steps = replay['steps']
            # We want to sample at the boundaries of the 3-day windows:
            # Days: 0, 3, 6, 9, 12, 15, 18, 21, 24, 27, 30
            # Steps: 0, 72, 144, 216, 288, 360, 432, 504, 576, 648, 719
            
            sample_steps = [0, 72, 144, 216, 288, 360, 432, 504, 576, 648, min(719, len(steps)-1)]
            
            for slice_idx, step_num in enumerate(sample_steps):
                if step_num >= len(steps): continue
                
                step_data = steps[step_num]
                
                # Determine which player won (who is the Grandmaster?)
                # To be safe, we extract metrics for both players, or just Player 0 if we assume they are top agents
                for player_id in [0, 1]:
                    obs = step_data[player_id].get("observation", {})
                    if "farms" not in obs: continue
                    
                    farm = obs["farms"][player_id]
                    money = farm.get("money", 0)
                    hands = len(farm.get("hands", []))
                    
                    # Farm Size (count unlocked tiles)
                    grid = farm.get("tiles", [])
                    unlocked_tiles = 0
                    planted_crops = 0
                    animals = 0
                    
                    for r in range(10):
                        for c in range(10):
                            if r < len(grid) and c < len(grid[r]):
                                tile = grid[r][c]
                                if tile != "LOCKED":
                                    unlocked_tiles += 1
                                    if isinstance(tile, dict):
                                        if tile.get("kind") == "PLANT": planted_crops += 1
                                        if "animal" in tile: animals += 1
                    
                    # Inventory
                    priv = obs.get("private", {})
                    shed_items = sum(priv.get("shed", {}).values())
                    seed_items = sum(priv.get("seeds", {}).values())
                    
                    # Calculate Net Worth (Approximate based on market prices at this step)
                    market = obs.get("market", {}).get("prices", {})
                    net_worth = money
                    for item, count in priv.get("shed", {}).items():
                        net_worth += count * market.get(item, 0)
                    
                    records.append({
                        "Replay_ID": os.path.basename(file),
                        "Player_ID": player_id,
                        "Day": slice_idx * 3,
                        "Step": step_num,
                        "Liquid_Cash": money,
                        "Net_Worth": net_worth,
                        "Hands_Hired": hands,
                        "Farm_Size": unlocked_tiles,
                        "Planted_Crops": planted_crops,
                        "Animals": animals,
                        "Shed_Inventory": shed_items,
                        "Seed_Inventory": seed_items
                    })
                    
        except Exception as e:
            print(f"Error processing {file}: {e}")
            
        if (file_idx + 1) % 50 == 0:
            print(f"Processed {file_idx + 1}/{len(files)} replays...")

    df = pd.DataFrame(records)
    df.to_csv(output_csv, index=False)
    print(f"\nExtracted {len(df)} sliced states.")
    print(f"Saved EDA metrics to {output_csv}!")

if __name__ == "__main__":
    # Adjust this path if running on the 3050 Node!
    extract_eda_metrics("our_replays", "eda_metrics.csv")
