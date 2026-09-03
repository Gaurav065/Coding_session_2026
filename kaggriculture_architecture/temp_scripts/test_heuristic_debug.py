import sys
from pathlib import Path
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent")
from phase_f_dispatcher import PhaseFDispatcher

def get_seat(obs): return 1 if int(obs.get("player", 0) or 0) == 1 else 0

_DISPATCHER = PhaseFDispatcher(grid_size=10)

def agent(obs, config=None):
    seat = get_seat(obs)
    farm = obs.get("farms", [])[seat]
    cash = farm.get("money", 0)
    inventory = farm.get("inventory", {})
    hands_pos = farm.get("hands", [])
    step = obs.get("step", 0)
    
    farmer_action = ["PASS"]
    market_action = []
    
    wheat_seeds = inventory.get("WHEAT", {}).get("seed", 0)
    
    if step < 5:
        print(f"Step {step} Cash: {cash} Seeds: {wheat_seeds}")
        
    tasks = []
    obstacles = set()
    avail_seeds = wheat_seeds 
    
    grid = farm.get("tiles", [])
    for y in range(10):
        for x in range(10):
            tile = grid[y][x]
            if tile == "LOCKED": continue
            if isinstance(tile, dict):
                pass
            elif tile is None:
                if avail_seeds > 0:
                    dist = abs(x-4) + abs(y-4)
                    tasks.append({"x": x, "y": y, "cmd": ["PLANT"], "priority": 50 - dist})
                    avail_seeds -= 1
                    
    tasks.sort(key=lambda t: t["priority"], reverse=True)
    
    if step < 5:
        print(f"Tasks: {tasks}")
        
    new_hands = [["PASS"] for _ in hands_pos]
    return {"farmer": farmer_action, "hands": new_hands, "market": market_action}
