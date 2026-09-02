import json
import glob
import os

paths = [
    r"C:\Users\GauravPatel\Downloads\1st september replays\*.json",
    r"C:\Coding\kaggriculture\data\*.json",
    r"C:\Coding\kaggriculture\*.json",
    r"C:\Coding\kaggriculture_architecture\our_replays\*.json"
]

files = []
for p in paths:
    files.extend(glob.glob(p))
files = list(set(files))

# Store the best replay for each shop sequence signature
best_tapes = {}

print("Scanning replays to build the ultimate Fieldbook...")

for f in files:
    try:
        with open(f, "r", encoding="utf-8") as tmp:
            data = json.load(tmp)
            
        final_obs = data["steps"][-1][0]["observation"]
        if "farms" not in final_obs: continue
        
        m0 = final_obs["farms"][0]["money"]
        m1 = final_obs["farms"][1]["money"]
        
        # Only consider high ELO wins
        winner_money = max(m0, m1)
        if winner_money < 100000:
            continue
            
        winner_idx = 0 if m0 > m1 else 1
        
        # Extract the shop sequence
        # Shops unlock on Steps 72 (Day 3), 144 (Day 6), 216 (Day 9), 288 (Day 12)
        shops_day0 = set(data["steps"][0][0]["observation"]["town"]["unlocked_shops"])
        shop1, shop2, shop3, shop4 = None, None, None, None
        
        def get_new_shop(step):
            if step >= len(data["steps"]): return None
            obs = data["steps"][step][0]["observation"]
            if "town" not in obs: return None
            current_shops = set(obs["town"]["unlocked_shops"])
            new_shops = list(current_shops - shops_day0)
            # Find the chronologically newest one by comparing to previous steps if needed,
            # but usually it's just the newly added one. Let's just track the sequence of additions.
            return new_shops
            
        def extract_shops():
            sequence = []
            seen = set(data["steps"][0][0]["observation"]["town"]["unlocked_shops"])
            for step in [72, 144, 216, 288]:
                if step < len(data["steps"]):
                    obs = data["steps"][step][0]["observation"]
                    current = set(obs.get("town", {}).get("unlocked_shops", []))
                    new_stuff = list(current - seen)
                    if new_stuff:
                        sequence.append(new_stuff[0])
                        seen.update(new_stuff)
                    else:
                        sequence.append(None)
                else:
                    sequence.append(None)
            return tuple(sequence)

        shop_sig = extract_shops()
        
        # If this is the best score for this shop signature, save it!
        if shop_sig not in best_tapes or winner_money > best_tapes[shop_sig]["money"]:
            
            # Extract exactly the actions the winner took
            # Note: The action for step t is located in data["steps"][t+1][winner_idx]["action"]
            actions = []
            for t in range(1, len(data["steps"])):
                act = data["steps"][t][winner_idx].get("action", {})
                actions.append(act)
                
            # Pad to 720 if the game ended early
            while len(actions) < 720:
                actions.append({"farmer": ["PASS"], "hands": [], "market": []})
                
            best_tapes[shop_sig] = {
                "money": winner_money,
                "file": f,
                "actions": actions
            }
            
    except Exception as e:
        continue

print(f"Found {len(best_tapes)} unique Shop Signatures.")

# Generate the python file
out_path = r"C:\Coding\kaggriculture_architecture\fieldbook_routes.py"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("ROUTES = {\n")
    route_id = 0
    # Also write a mapping from signature to route_id
    sig_map = {}
    
    for sig, meta in best_tapes.items():
        sig_map[sig] = route_id
        f.write(f"    {route_id}: {meta['actions']},  # Score: ${meta['money']:.0f} | Sig: {sig} | File: {os.path.basename(meta['file'])}\n")
        route_id += 1
        
    f.write("}\n\n")
    
    f.write("ROUTE_MAP = {\n")
    for sig, rid in sig_map.items():
        f.write(f"    {sig}: {rid},\n")
    f.write("}\n")

print(f"Successfully generated fieldbook_routes.py with {len(best_tapes)} master tapes!")
