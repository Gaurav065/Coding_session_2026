import json
import copy

def fake_get(obj, key, default=None):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return default

def _phantom_supply_injection(obs, seat):
    fake_obs = copy.deepcopy(obs)
    opp_seat = 1 - seat
    farms = fake_get(fake_obs, "farms", [])
    if opp_seat >= len(farms): return fake_obs
    
    opp_farm = farms[opp_seat]
    tiles = fake_get(opp_farm, "tiles", [])
    
    opp_crops = {}
    if isinstance(tiles, list):
        for row in tiles:
            if isinstance(row, list):
                for cell in row:
                    if isinstance(cell, dict) and cell.get("kind") == "PLANT":
                        crop = str(cell.get("crop") or "").upper()
                        if crop:
                            opp_crops[crop] = opp_crops.get(crop, 0) + 1
                            
    market = fake_get(fake_obs, "market", {})
    inventory = fake_get(market, "inventory", {})
    
    for crop, count in opp_crops.items():
        current_inv = int(fake_get(inventory, crop, 0) or 0)
        inventory[crop] = current_inv + count
        
    market["inventory"] = inventory
    fake_obs["market"] = market
    return fake_obs, opp_crops

with open("episode-104530263-replay.json", encoding="utf-8") as f:
    d = json.load(f)
obs = d["steps"][600][0]["observation"]

fake, crops = _phantom_supply_injection(obs, 0)
print("Opponent crops:", crops)
print("Original WHEAT inv:", obs["market"]["inventory"].get("WHEAT", 0))
print("Fake WHEAT inv:", fake["market"]["inventory"]["WHEAT"])
