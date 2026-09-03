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
    priv = obs.get("private", {})
    shed = priv.get("shed", {})
    seeds = priv.get("seeds", {})
    hands_pos = farm.get("hands", [])
    step = obs.get("step", 0)
    
    farmer_action = ["PASS"]
    market_action = []
    
    wheat_seeds = seeds.get("WHEAT", 0)
    wheat_product = shed.get("WHEAT", 0)
    
    if wheat_product > 0:
        market_action.append(["SELL", "WHEAT", int(wheat_product)])
        
    if wheat_seeds < 15 and cash >= 10:
        amount = min(5, int(cash / 2))
        market_action.append(["BUY_SEED", "WHEAT", amount])
        cash -= amount * 2
        
    target_hands = min(8, 2 + int(cash / 300))
    hires = 0
    while len(hands_pos) + hires < target_hands and cash >= 10 and len(market_action) < 10:
        market_action.append(["HIRE"])
        cash -= 10
        hires += 1
        
    tasks = []
    obstacles = set()
    avail_seeds = wheat_seeds 
    
    grid = farm.get("tiles", [])
    for y in range(10):
        for x in range(10):
            tile = grid[y][x]
            if tile == "LOCKED": continue
            if isinstance(tile, dict):
                kind = tile.get("kind")
                if kind == "WEED":
                    tasks.append({"x": x, "y": y, "cmd": ["DIG"], "priority": 10})
                elif kind == "CROP":
                    if tile.get("stage") == "MATURE":
                        tasks.append({"x": x, "y": y, "cmd": ["HARVEST"], "priority": 100})
                    elif tile.get("water", 0) == 0:
                        tasks.append({"x": x, "y": y, "cmd": ["WATER"], "priority": 80})
            elif tile is None or tile == "":
                if avail_seeds > 0:
                    dist = abs(x-4) + abs(y-4)
                    tasks.append({"x": x, "y": y, "cmd": ["PLANT"], "priority": 50 - dist})
                    avail_seeds -= 1
                    
    tasks.sort(key=lambda t: t["priority"], reverse=True)
    
    new_hands = []
    assigned_tasks = set()
    
    for i, current_pos in enumerate(hands_pos):
        assigned = False
        for task in tasks:
            task_id = (task["x"], task["y"], task["cmd"][0])
            if task_id not in assigned_tasks:
                target_pos = (task["x"], task["y"])
                if current_pos[0] == target_pos[0] and current_pos[1] == target_pos[1]:
                    new_hands.append(task["cmd"])
                else:
                    d = _DISPATCHER._bfs_path(tuple(current_pos), target_pos, obstacles)
                    if d == (0, 1): new_hands.append(['SOUTH'])
                    elif d == (0, -1): new_hands.append(['NORTH'])
                    elif d == (1, 0): new_hands.append(['EAST'])
                    elif d == (-1, 0): new_hands.append(['WEST'])
                    else: new_hands.append(['PASS'])
                assigned_tasks.add(task_id)
                assigned = True
                break
                
        if not assigned:
            new_hands.append(['PASS'])
            
    return {"farmer": farmer_action, "hands": new_hands, "market": market_action}
