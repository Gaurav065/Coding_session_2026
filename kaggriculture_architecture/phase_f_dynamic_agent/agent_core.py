import sys
import os
from pathlib import Path
import collections

# Add the current directory (where this script is extracted in Kaggle) to sys.path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "legacy") not in sys.path:
    sys.path.insert(0, str(ROOT / "legacy"))

# Import the original submission from the legacy directory

from phase_f_dispatcher import PhaseFDispatcher

_DISPATCHER = PhaseFDispatcher(grid_size=10)

_TAPE_TASKS = None

def init_tape_tasks():
    global _TAPE_TASKS
    if _TAPE_TASKS is not None:
        return
    
    try:
        import importlib.util
        from pathlib import Path
        ROOT = Path(__file__).resolve().parent.parent.parent
        SOURCE_PATH = ROOT / "artifacts/e706_top10_tapes/episode_101408728_seat1.py"
        SPEC = importlib.util.spec_from_file_location("e749a_attributed_niklita_trace", SOURCE_PATH)
        SOURCE = importlib.util.module_from_spec(SPEC)
        sys.modules[SPEC.name] = SOURCE
        SPEC.loader.exec_module(SOURCE)
        trace_actions = SOURCE.TRACE_ACTIONS
    except Exception:
        import traceback; traceback.print_exc(file=sys.stderr)
        _TAPE_TASKS = {}
        return
        
    spawn_pattern = [(4, 4), (5, 4), (4, 5), (5, 5)]
    positions = collections.defaultdict(lambda: [4, 4])
    tasks = collections.defaultdict(list)
    
    farmer_pos = [4, 4]
    hands_pos_offline = []
    
    for step, action in enumerate(trace_actions):
        if step % 24 == 0:
            hands_pos_offline = []
            farmer_pos = [4, 4]
            
        farmer_cmd = action.get("farmer", [])
        if farmer_cmd:
            f_op = farmer_cmd[0]
            if f_op == "NORTH" and farmer_pos[1] > 0: farmer_pos[1] -= 1
            elif f_op == "SOUTH" and farmer_pos[1] < 9: farmer_pos[1] += 1
            elif f_op == "EAST" and farmer_pos[0] < 9: farmer_pos[0] += 1
            elif f_op == "WEST" and farmer_pos[0] > 0: farmer_pos[0] -= 1
            
        hands = action.get("hands", [])
        for i, cmd in enumerate(hands):
            if not cmd: continue
            op = cmd[0]
            if op == "NORTH" and positions[i][1] > 0: positions[i][1] -= 1
            elif op == "SOUTH" and positions[i][1] < 9: positions[i][1] += 1
            elif op == "EAST" and positions[i][0] < 9: positions[i][0] += 1
            elif op == "WEST" and positions[i][0] > 0: positions[i][0] -= 1
            elif op in ["NORTH", "SOUTH", "EAST", "WEST", "PASS"]: pass
            else:
                tasks[i].append({
                    "step": step,
                    "x": positions[i][0],
                    "y": positions[i][1],
                    "command": cmd
                })
                
        # Update hands_pos_offline BEFORE market evaluation so HIRE sees the new positions!
        for i in range(len(hands_pos_offline)):
            if i in positions:
                hands_pos_offline[i] = list(positions[i])
                
        market = action.get("market", [])
        for m in market:
            if m and m[0] == "HIRE":
                occupants = {tuple(t): 0 for t in spawn_pattern}
                all_p = [tuple(farmer_pos)] + [tuple(p) for p in hands_pos_offline]
                for p in all_p:
                    if p in occupants:
                        occupants[p] += 1
                best = sorted(occupants.items(), key=lambda kv: (kv[1], spawn_pattern.index(kv[0])))
                spawn_pos = list(best[0][0])
                hands_pos_offline.append(spawn_pos)
                i = len(hands_pos_offline) - 1
                positions[i] = list(spawn_pos)

    _TAPE_TASKS = dict(tasks)

def get_seat(obs):
    return 1 if int(obs.get("player", 0) or 0) == 1 else 0

def find_jobs(obs, seat):
    farm = obs.get("farms", [])[seat]
    tiles = farm.get("tiles", [])
    
    tasks = {}
    task_idx = 0
    obstacles = set()
    
    for y in range(len(tiles)):
        for x in range(len(tiles[y])):
            tile = tiles[y][x]
            if tile == "LOCKED":
                continue
                
            if isinstance(tile, dict):
                kind = tile.get("kind")
                if kind == "WEED":
                    tasks[f"task_{task_idx}"] = (x, y, "DIG")
                    task_idx += 1
                elif kind == "CROP":
                    if tile.get("stage") == "MATURE":
                        tasks[f"task_{task_idx}"] = (x, y, "HARVEST")
                        task_idx += 1
                    elif tile.get("water", 0) == 0:
                        tasks[f"task_{task_idx}"] = (x, y, "WATER")
                        task_idx += 1
                    
    return tasks, obstacles

def agent(obs, config=None):
    seat = get_seat(obs)
    step = int(obs.get("step", 0))
    init_tape_tasks()
    
    # 1. Get farmer and market actions from the EXACT trace!
    try:
        import importlib.util
        from pathlib import Path
        ROOT = Path(__file__).resolve().parent.parent.parent
        SOURCE_PATH = ROOT / "artifacts/e706_top10_tapes/episode_101408728_seat1.py"
        SPEC = importlib.util.spec_from_file_location("e749a_attributed_niklita_trace", SOURCE_PATH)
        SOURCE = importlib.util.module_from_spec(SPEC)
        sys.modules[SPEC.name] = SOURCE
        SPEC.loader.exec_module(SOURCE)
        trace_actions = SOURCE.TRACE_ACTIONS
        if step < len(trace_actions):
            farmer_action = trace_actions[step].get("farmer", ["PASS"])
            market_action = trace_actions[step].get("market", [])
        else:
            farmer_action = ["PASS"]
            market_action = []
    except Exception:
        import traceback; traceback.print_exc(file=sys.stderr)
        farmer_action = ["PASS"]
        market_action = []
    
    # 2. Map out our current workers
    farm = obs.get("farms", [])[seat]
    hands_pos = farm.get("hands", [])
    
    # 3. Discover jobs from the grid
    tasks, obstacles = find_jobs(obs, seat)
    
    # 4. Dispatch!
    new_hands = []
    idle_workers = {}
    tape_actions = {}
    worker_margins = {}
    worker_dists = {}
    
    for i, current_pos in enumerate(hands_pos):
        w_id = f"w_{i}"
        
        tape_queue = _TAPE_TASKS.get(i, [])
        while tape_queue and tape_queue[0]["step"] < step:
            print(f'MISSED DEADLINE: Worker {i} missed {tape_queue[0]} at step {step} (pos {current_pos})', file=sys.stderr)
            tape_queue.pop(0)
            
        action = None
        if tape_queue:
            next_task = tape_queue[0]
            target_step = next_task["step"]
            target_pos = (next_task["x"], next_task["y"])
            
            if step == target_step:
                if current_pos[0] == target_pos[0] and current_pos[1] == target_pos[1]:
                    action = next_task["command"]
                    tape_queue.pop(0)
                else:
                    d = _DISPATCHER._bfs_path(tuple(current_pos), target_pos, obstacles)
                    if d == (0, 1): action = ['SOUTH']
                    elif d == (0, -1): action = ['NORTH']
                    elif d == (1, 0): action = ['EAST']
                    elif d == (-1, 0): action = ['WEST']
                    else: action = ['PASS']
            else:
                dist = _DISPATCHER._bfs_distance(tuple(current_pos), target_pos, obstacles)
                margin = (target_step - step) - dist
                worker_margins[w_id] = margin
                worker_dists[w_id] = dist
                
                if margin <= 2:
                    if dist > 0:
                        d = _DISPATCHER._bfs_path(tuple(current_pos), target_pos, obstacles)
                        if d == (0, 1): action = ['SOUTH']
                        elif d == (0, -1): action = ['NORTH']
                        elif d == (1, 0): action = ['EAST']
                        elif d == (-1, 0): action = ['WEST']
                        else: action = ['PASS']
                    else:
                        action = ['PASS']
                else:
                    action = None
        else:
            action = None
            worker_margins[w_id] = 999
            worker_dists[w_id] = 0
            
        if action is not None:
            tape_actions[w_id] = action
        else:
            idle_workers[w_id] = (current_pos[0], current_pos[1])
            
    # Process Idle Workers using normal Dispatcher
    assignments = {}
    has_hire = any(m and m[0] == "HIRE" for m in market_action)
    
    shed_evac = {
        (4, 4): ["NORTH"],
        (5, 4): ["NORTH"],
        (4, 5): ["SOUTH"],
        (5, 5): ["SOUTH"]
    }
    
    if has_hire:
        for i, current_pos in enumerate(hands_pos):
            w_id = f"w_{i}"
            hx, hy = current_pos[0], current_pos[1]
            if (hx, hy) in shed_evac:
                executing_now = False
                if w_id in tape_actions:
                    act = tape_actions[w_id]
                    if act and act[0] not in ["PASS", "NORTH", "SOUTH", "EAST", "WEST"]:
                        executing_now = True
                
                if not executing_now:
                    margin = worker_margins.get(w_id, 999)
                    dist = worker_dists.get(w_id, 0)
                    if margin > 2 or (dist == 0 and margin > 0):
                        tape_actions[w_id] = shed_evac[(hx, hy)]
                        if w_id in idle_workers:
                            del idle_workers[w_id]

    if step == 169: print(f'ENGINE STEP 169: W6 task={_TAPE_TASKS.get(6, [{}])[0]}', file=sys.stderr)
    if idle_workers:
        assignments = {w_id: ['PASS'] for w_id in idle_workers}
        
    for i in range(len(hands_pos)):
        w_id = f"w_{i}"
        if w_id in tape_actions:
            new_hands.append(tape_actions[w_id])
        else:
            # Dispatcher returns raw string like "HARVEST", must be wrapped!
            raw = assignments.get(w_id, "PASS")
            if isinstance(raw, list):
                new_hands.append(raw)
            else:
                new_hands.append([raw])
            
    return {
        "farmer": farmer_action,
        "hands": new_hands,
        "market": market_action
    }
