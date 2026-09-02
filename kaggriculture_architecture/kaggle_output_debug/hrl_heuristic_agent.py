import sys
from pathlib import Path
from phase_f_dispatcher import PhaseFDispatcher

_DISPATCHER = PhaseFDispatcher(grid_size=10)

def get_seat(obs): return 1 if int(obs.get("player", 0) or 0) == 1 else 0

TARGET_PORTFOLIO = {
    "BUY_TARGETS": {},
    "SELL_RATIOS": {},
    "HIRE_TARGET": 0
}

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
    
    # 1. Sell items based on SELL_RATIOS
    sell_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]
    for item in sell_items:
        amt = shed.get(item, 0)
        ratio = TARGET_PORTFOLIO["SELL_RATIOS"].get(item, 1.0)
        sell_amt = int(amt * ratio)
        if sell_amt > 0 and len(market_action) < 10:
            market_action.append(["SELL", item, sell_amt])
            
    # 2. Portfolio Management (Buy Assets) based on BUY_TARGETS
    # BUY_TARGETS indicates the *total* we want to hold (seeds + planted + shed)
    # For simplicity, let's just buy if current seeds < target
    # In a full version, we'd count planted crops too.
    for item, target in TARGET_PORTFOLIO["BUY_TARGETS"].items():
        if len(market_action) >= 10: break
        
        current = seeds.get(item, 0)
        if item in ["COW", "SHEEP", "GOOSE"]:
            current = shed.get(item, 0)
            
        cost = 10
        if item == "MELON": cost = 80
        elif item == "WHEAT": cost = 10
        elif item == "CARROT": cost = 20
        elif item == "TOMATO": cost = 50
        elif item == "STRAWBERRY": cost = 100
        elif item == "COW": cost = 400
        elif item == "SHEEP": cost = 500
        elif item == "GOOSE": cost = 300
        
        if current < target and cash >= cost:
            to_buy = min(target - current, int(cash / cost))
            if to_buy > 0:
                cmd = "BUY_ANIMAL" if item in ["COW", "SHEEP", "GOOSE"] else "BUY_SEED"
                market_action.append([cmd, item, to_buy])
                cash -= to_buy * cost
                
    # 4. Hands Management
    target_hands = TARGET_PORTFOLIO.get("HIRE_TARGET", 2)
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
