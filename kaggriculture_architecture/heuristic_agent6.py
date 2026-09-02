import sys
from pathlib import Path
sys.path.insert(0, r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent")
from phase_f_dispatcher import PhaseFDispatcher

_DISPATCHER = PhaseFDispatcher(grid_size=10)

def get_seat(obs): return 1 if int(obs.get("player", 0) or 0) == 1 else 0

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
    
    # 1. Sell everything we can
    sell_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]
    for item in sell_items:
        amt = shed.get(item, 0)
        if amt > 0 and len(market_action) < 10:
            market_action.append(["SELL", item, int(amt)])
            
    # 2. Portfolio Management (Buy Assets) - Initial Setup
    cows = shed.get("COW", 0)
    sheep = shed.get("SHEEP", 0)
    melon_seeds = seeds.get("MELON", 0)
    wheat_seeds = seeds.get("WHEAT", 0)
    
    if step < 24 and len(market_action) < 10:
        if melon_seeds < 12 and cash >= 80 and len(market_action) < 10:
            amt = min(12 - melon_seeds, int(cash / 80))
            if amt > 0:
                market_action.append(["BUY_SEED", "MELON", amt])
                cash -= amt * 80
                melon_seeds += amt
        elif wheat_seeds < 10 and cash >= 10 and len(market_action) < 10:
            amt = min(10 - wheat_seeds, int(cash / 10))
            if amt > 0:
                market_action.append(["BUY_SEED", "WHEAT", amt])
                cash -= amt * 10
                wheat_seeds += amt

    # Late game seed buying
    if step >= 24 and len(market_action) < 10:
        if cash > 300 and melon_seeds < 5 and len(market_action) < 10:
            market_action.append(["BUY_SEED", "MELON", 2])
            cash -= 160
        if cash > 100 and wheat_seeds < 5 and len(market_action) < 10:
            market_action.append(["BUY_SEED", "WHEAT", 5])
            cash -= 50

    # 4. Hands Management
    target_hands = min(10, max(2, int(cash / 15)))
    hires = 0
    while len(hands_pos) + hires < target_hands and cash >= 10 and len(market_action) < 10:
        market_action.append(["HIRE"])
        cash -= 10
        hires += 1
        
    # 5. Task Generation
    tasks = []
    obstacles = set()
    avail_seeds = {k: v for k, v in seeds.items() if v > 0}
    
    seed_priority = {"MELON": 60, "STRAWBERRY": 55, "TOMATO": 50, "CARROT": 45, "WHEAT": 40}
    
    grid = farm.get("tiles", [])
    for y in range(10):
        for x in range(10):
            tile = grid[y][x]
            if tile == "LOCKED": continue
            if isinstance(tile, dict):
                kind = tile.get("kind")
                if kind == "WEED":
                    tasks.append({"x": x, "y": y, "cmd": ["DIG"], "priority": 10})
                elif kind == "PLANT":
                    crop_name = tile.get("crop", "")
                    # Determine first yield day
                    fy = 10
                    if crop_name in ("WHEAT", "CARROT"): fy = 2
                    elif crop_name == "TOMATO": fy = 8
                    elif crop_name == "STRAWBERRY": fy = 10
                    elif crop_name == "MELON": fy = 10
                    
                    day = step // 24
                    planted_day = tile.get("planted_day", day)
                    is_mature = (day - planted_day >= fy)
                    
                    if is_mature and tile.get("yield_units", 0) > 0:
                        tasks.append({"x": x, "y": y, "cmd": ["HARVEST"], "priority": 100})
                    elif not tile.get("watered_today", False):
                        tasks.append({"x": x, "y": y, "cmd": ["WATER"], "priority": 80})
            elif tile is None or tile == "":
                best_seed = None
                best_prio = -1
                for s, count in avail_seeds.items():
                    if count > 0 and seed_priority.get(s, 0) > best_prio:
                        best_seed = s
                        best_prio = seed_priority.get(s, 0)
                if best_seed:
                    dist = abs(x-4) + abs(y-4)
                    tasks.append({"x": x, "y": y, "cmd": ["PLANT", best_seed], "priority": best_prio - (dist * 0.1)})
                    avail_seeds[best_seed] -= 1
                    
    tasks.sort(key=lambda t: t["priority"], reverse=True)
    
    new_hands = []
    assigned_tasks = set()
    
    for i, current_pos in enumerate(hands_pos):
        assigned = False
        for task in tasks:
            task_id = (task["x"], task["y"], tuple(task["cmd"]))
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
