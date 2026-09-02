import sys
from collections import deque

def get_seat(obs):
    return 1 if int(obs.get("player", 0) or 0) == 1 else 0

def get_dynamic_action_heuristic(obs, step):
    seat = get_seat(obs)
    farm = obs.get("farms", [])[seat]
    cash = farm.get("money", 0)
    inventory = farm.get("inventory", {})
    hands_pos = farm.get("hands", [])
    
    farmer_action = ["PASS"]
    market_action = []
    
    # --- MACRO MARKET POLICY (Heuristic) ---
    # 1. Hire hands aggressively if we have enough cash
    target_hands = min(12, int(cash / 50)) # Example: Hire up to 12 workers based on cash
    if len(hands_pos) < target_hands and cash >= 10:
        market_action.append(["HIRE"])
        cash -= 10
        
    # 2. Buy seeds
    # Basic logic: always want ~20 seeds of the best available
    wheat_seeds = inventory.get("WHEAT", {}).get("seed", 0)
    if wheat_seeds < 15 and cash >= 10:
        amount = min(5, int(cash / 2))
        if amount > 0:
            market_action.append(["BUY_SEED", "WHEAT", amount])
            cash -= amount * 2
            
    # --- TASK GENERATION (The "What") ---
    grid = farm.get("tiles", [])
    tasks = []
    obstacles = set()
    
    for y in range(10):
        for x in range(10):
            tile = grid[y][x]
            if tile == "LOCKED":
                continue
            if isinstance(tile, dict):
                kind = tile.get("kind")
                if kind == "WEED":
                    tasks.append({"x": x, "y": y, "cmd": ["DIG"], "priority": 1})
                elif kind == "CROP":
                    if tile.get("stage") == "MATURE":
                        tasks.append({"x": x, "y": y, "cmd": ["HARVEST"], "priority": 100})
                    elif tile.get("water", 0) == 0:
                        tasks.append({"x": x, "y": y, "cmd": ["WATER"], "priority": 50})
            else: # empty dirt/grass
                if wheat_seeds > 0:
                    tasks.append({"x": x, "y": y, "cmd": ["PLANT"], "priority": 10})
                    wheat_seeds -= 1
                    
    tasks.sort(key=lambda t: t["priority"], reverse=True)
    
    # --- EXECUTION ENGINE (The "How" - BFS) ---
    # (We will use the same Phase F Dispatcher here, but for now just mock it)
    new_hands = [["PASS"] for _ in hands_pos]
    
    return {
        "farmer": farmer_action,
        "hands": new_hands,
        "market": market_action
    }

