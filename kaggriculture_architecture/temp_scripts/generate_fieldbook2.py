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
for p in paths: files.extend(glob.glob(p))
files = list(set(files))

best_tapes = {}

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
        
        shops_day0 = set(data["steps"][0][0]["observation"]["town"]["unlocked_shops"])
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
                    else: sequence.append(None)
                else: sequence.append(None)
            return tuple(sequence)

        shop_sig = (winner_idx,) + extract_shops() # ADD WINNER IDX TO SIGNATURE
        
        if shop_sig not in best_tapes or winner_money > best_tapes[shop_sig]["money"]:
            actions = []
            for t in range(1, len(data["steps"])):
                act = data["steps"][t][winner_idx].get("action", {})
                actions.append(act)
            while len(actions) < 720:
                actions.append({"farmer": ["PASS"], "hands": [], "market": []})
                
            best_tapes[shop_sig] = {"money": winner_money, "file": f, "actions": actions}
    except: continue

out_path = r"C:\Coding\kaggriculture_architecture\fieldbook_routes.py"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("ROUTES = {\n")
    route_id = 0
    sig_map = {}
    for sig, meta in best_tapes.items():
        sig_map[sig] = route_id
        f.write(f"    {route_id}: {meta['actions']},  # Score: ${meta['money']:.0f} | Sig: {sig} | File: {os.path.basename(meta['file'])}\n")
        route_id += 1
    f.write("}\n\nROUTE_MAP = {\n")
    for sig, rid in sig_map.items(): f.write(f"    {sig}: {rid},\n")
    f.write("}\n")

print(f"Generated fieldbook_routes.py with {len(best_tapes)} master tapes!")
