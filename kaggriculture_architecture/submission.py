import os
import sys
import base64
import numpy as np
import collections

# --- PHASE F DISPATCHER ---
import numpy as np
from scipy.optimize import linear_sum_assignment
from collections import deque

class PhaseFDispatcher:
    def __init__(self, grid_size=15):
        self.grid_size = grid_size
        
    def _bfs_path(self, start, target, obstacles):
        """
        Find shortest path avoiding obstacles.
        Returns the FIRST step (dx, dy) to take, or None if unreachable/at target.
        """
        if start == target:
            return None
            
        queue = deque([(start[0], start[1], [])])
        visited = {start}
        
        while queue:
            x, y, path = queue.popleft()
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    if (nx, ny) == target:
                        new_path = path + [(dx, dy)]
                        return new_path[0] # Return the first step to take!
                    if (nx, ny) not in visited and (nx, ny) not in obstacles:
                        visited.add((nx, ny))
                        queue.append((nx, ny, path + [(dx, dy)]))
        return None # Unreachable

    def _bfs_distance(self, start, target, obstacles):
        if start == target: return 0
        queue = deque([(start[0], start[1], 0)])
        visited = {start}
        
        while queue:
            x, y, dist = queue.popleft()
            for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
                nx, ny = x + dx, y + dy
                if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                    if (nx, ny) == target:
                        return dist + 1
                    if (nx, ny) not in visited and (nx, ny) not in obstacles:
                        visited.add((nx, ny))
                        queue.append((nx, ny, dist + 1))
        return 999
        
    def get_actions(self, workers, tasks, obstacles):
        """
        workers: dict mapping worker_id -> (x, y)
        tasks: dict mapping task_id -> (x, y, type) where type in ['HARVEST', 'PLANT', 'WATER', 'NONE']
        obstacles: set of (x, y)
        
        Returns dict mapping worker_id -> 'ACTION'
        """
        if not workers or not tasks:
            return {w_id: 'PASS' for w_id in workers}
            
        worker_ids = list(workers.keys())
        task_ids = list(tasks.keys())
        
        cost_matrix = np.zeros((len(worker_ids), len(task_ids)))
        for i, w_id in enumerate(worker_ids):
            for j, t_id in enumerate(task_ids):
                wx, wy = workers[w_id]
                tx, ty, _ = tasks[t_id]
                cost = self._bfs_distance((wx, wy), (tx, ty), obstacles)
                cost_matrix[i, j] = cost
                
        # Hungarian Assignment
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        actions = {}
        for i, j in zip(row_ind, col_ind):
            w_id = worker_ids[i]
            t_id = task_ids[j]
            cost = cost_matrix[i, j]
            
            if cost >= 999:
                actions[w_id] = 'PASS'
                continue
                
            wx, wy = workers[w_id]
            tx, ty, task_type = tasks[t_id]
            
            if (wx, wy) == (tx, ty):
                # Worker is exactly on the task tile! Perform the task.
                actions[w_id] = task_type
            else:
                # Need to move closer
                step = self._bfs_path((wx, wy), (tx, ty), obstacles)
                if step == (0, 1): actions[w_id] = 'NORTH'
                elif step == (0, -1): actions[w_id] = 'SOUTH'
                elif step == (1, 0): actions[w_id] = 'EAST'
                elif step == (-1, 0): actions[w_id] = 'WEST'
                else: actions[w_id] = 'PASS'
                
        # Any unassigned workers pass
        for w_id in worker_ids:
            if w_id not in actions:
                actions[w_id] = 'PASS'
                
        return actions


# --- HRL HEURISTIC AGENT ---
import sys
from pathlib import Path


_DISPATCHER = PhaseFDispatcher(grid_size=10)

def get_seat(obs): return 1 if int(obs.get("player", 0) or 0) == 1 else 0

TARGET_PORTFOLIO = {
    "BUY_TARGETS": {},
    "SELL_RATIOS": {},
    "HIRE_TARGET": 0
}

def heuristic_agent(obs, config=None):
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


# --- RL INFERENCE LOGIC ---
try:
    from stable_baselines3 import PPO
except ImportError:
    import os
    os.system("pip install stable-baselines3")
    from stable_baselines3 import PPO

MODEL_BASE64 = b"PLACEHOLDER_FOR_ZIP"
MODEL = None

def get_macro_obs(obs):
    vec = np.zeros(50, dtype=np.float32)
    if not obs or "farms" not in obs: return vec
    player_idx = obs.get("player", 0)
    farm = obs["farms"][player_idx]
    priv = obs.get("private", {})
    shed = priv.get("shed", {})
    seeds = priv.get("seeds", {})
    market = obs.get("market", {})
    vec[0] = obs.get("step", 0) / 2000.0
    vec[1] = farm.get("money", 0) / 10000.0
    items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "COW", "SHEEP", "GOOSE"]
    for i, item in enumerate(items):
        vec[2 + i] = shed.get(item, 0) / 100.0
        vec[13 + i] = seeds.get(item, 0) / 100.0
        vec[24 + i] = market.get("prices", {}).get(item, 0) / 100.0
    vec[35] = len(farm.get("hands", [])) / 10.0
    return vec

def update_target_portfolio(action):
    buy_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "GOOSE", "COW", "SHEEP"]
    sell_items = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL"]
    
    targets = {}
    for i, item in enumerate(buy_items[:5]): targets[item] = int(action[i] * 50)
    for i, item in enumerate(buy_items[5:]): targets[item] = int(action[i+5] * 20)
    hire_target = max(2, int(action[8] * 10))
    
    ratios = {}
    for i, item in enumerate(sell_items): ratios[item] = float(action[9+i])
        
    TARGET_PORTFOLIO["BUY_TARGETS"] = targets
    TARGET_PORTFOLIO["SELL_RATIOS"] = ratios
    TARGET_PORTFOLIO["HIRE_TARGET"] = hire_target

def agent(obs, config=None):
    global MODEL
    if MODEL is None:
        with open("/tmp/model.zip", "wb") as f:
            f.write(base64.b64decode(MODEL_BASE64))
        MODEL = PPO.load("/tmp/model.zip")
        
    step = obs.get("step", 0)
    if step % 24 == 0:
        macro_obs = get_macro_obs(obs)
        action, _ = MODEL.predict(macro_obs, deterministic=True)
        update_target_portfolio(action)
        
    return heuristic_agent(obs, config)
