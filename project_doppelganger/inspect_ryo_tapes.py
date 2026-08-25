import json
import os

files = {
    'Route_1_NonYarn': r'C:\Coding\project_doppelganger\ryo_consensus_cows_2_sheep_2_quads_2.json',
    'Route_2_Yarn': r'C:\Coding\project_doppelganger\ryo_consensus_cows_3_sheep_3_quads_1.json',
}

for name, path in files.items():
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=" * 80)
    print(f"FORENSIC TEARDOWN OF RYO HASEGAWA {name} (Length: {len(data)})")
    print("=" * 80)
    
    buys = {}
    land_buys = []
    hires = [0] * 30
    sells = {}
    plants = {}
    
    for step, item in enumerate(data):
        day = step // 24
        hour = step % 24
        
        # Check farmer and hands plants
        f_act = item.get("farmer", [])
        if f_act and f_act[0] == "PLANT" and len(f_act) >= 2:
            plants[f_act[1]] = plants.get(f_act[1], 0) + 1
        for h in item.get("hands", []):
            if h and h[0] == "PLANT" and len(h) >= 2:
                plants[h[1]] = plants.get(h[1], 0) + 1
                
        # Market orders
        for o in item.get("market", []):
            if not isinstance(o, list) or len(o) == 0:
                continue
            cmd = o[0]
            if cmd == "HIRE":
                hires[day] += 1
            elif cmd == "BUY_LAND":
                land_buys.append(step)
            elif cmd in ("BUY_SEED", "BUY_ANIMAL", "BUY_PRODUCT"):
                key = f"{cmd}_{o[1]}" if len(o) >= 2 else cmd
                qty = o[2] if len(o) >= 3 else 1
                buys[key] = buys.get(key, 0) + qty
            elif cmd == "SELL":
                item_name = o[1] if len(o) >= 2 else "UNKNOWN"
                qty = o[2] if len(o) >= 3 else 1
                sells[item_name] = sells.get(item_name, 0) + qty
                
    print(f"Total Buys:  {buys}")
    print(f"Total Plants: {plants}")
    print(f"Total Sells:  {sells}")
    print(f"Land Buys at Steps: {land_buys}")
    print(f"Daily Hires Profile: {hires}")
