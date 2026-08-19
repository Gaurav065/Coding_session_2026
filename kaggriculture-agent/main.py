import json
import copy
import os

_TAPES = {}
_OPP_MODEL = None
_CURRENT_TAPE = "151k"
_LAST_STEP = -1

_BASE_PRICE = {"MELON": 250, "STRAWBERRY": 120, "MILK": 160, "WOOL": 200, "WHEAT": 25, "CARROT": 35, "TOMATO": 60, "EGG": 50, "FERTILIZER": 100}
_GLUT_WEIGHT = {"MELON": 3.6, "STRAWBERRY": 1.6, "MILK": 1.6, "WOOL": 3.2, "WHEAT": 0.2, "CARROT": 0.7, "TOMATO": 0.6, "EGG": 0.2, "FERTILIZER": 0.4}
_SELLABLE = ("STRAWBERRY", "MELON", "MILK", "WOOL", "EGG", "TOMATO", "CARROT", "WHEAT", "FERTILIZER")

def load_tapes():
    global _TAPES
    if _TAPES: return
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    except NameError:
        base_dir = "/kaggle_simulations/agent/"
        if not os.path.exists(base_dir):
            base_dir = os.getcwd()
    tapes_to_load = {

        "151k": "tape_151k.json",
        "143k": "top_tape_143954.json"
    }
    for tid, fname in tapes_to_load.items():
        path = os.path.join(base_dir, fname)
        if os.path.exists(path):
            with open(path, 'r') as f:
                _TAPES[tid] = json.load(f)
        else:
            _TAPES[tid] = [{"farmer": ["PASS"], "hands": [], "market": []}] * 720

class OpponentModel:
    def __init__(self):
        self.shed_inventory = {}

    def update(self, obs):
        pass 

    def forecast(self, obs, H=5):
        player = obs.get("player", 0)
        farms = obs.get("farms", [])
        if len(farms) < 2: return [{}] * H
        
        opp_farm = farms[1 - player]
        tiles = opp_farm.get("tiles", [])
        
        ripe_counts = {}
        for row in tiles:
            for tile in row:
                if isinstance(tile, dict) and tile.get("kind") == "PLANT":
                    crop = tile.get("crop")
                    y = int(tile.get("yield_units", 0) or 0)
                    if y > 0:
                        ripe_counts[crop] = ripe_counts.get(crop, 0) + y
                elif isinstance(tile, dict) and tile.get("kind") in ("COOP", "PASTURE"):
                    animal = tile.get("animal")
                    y = int(tile.get("yield_units", 0) or 0)
                    if y > 0:
                        product = {"COW": "MILK", "SHEEP": "WOOL", "GOOSE": "EGG"}.get(animal)
                        if product:
                            ripe_counts[product] = ripe_counts.get(product, 0) + y
                            
        forecast_sales = []
        for step_delta in range(1, H+1):
            expected = {}
            if step_delta == min(H, 2): 
                for item, count in ripe_counts.items():
                    if item in ["MELON", "STRAWBERRY", "MILK", "WOOL"] and count >= 2:
                        expected[item] = count
            forecast_sales.append(expected)
            
        return forecast_sales

def get_candidates(tapes, cur_id, step, H):
    candidates = []
    tape_cur = tapes.get(cur_id, [])
    
    base_actions = []
    for i in range(H):
        if step + i < len(tape_cur):
            base_actions.append(copy.deepcopy(tape_cur[step + i]))
        else:
            base_actions.append({"farmer": ["PASS"], "hands": [], "market": []})
            
    candidates.append({"tape_id": cur_id, "actions": copy.deepcopy(base_actions), "type": "base"})
    
    adv_actions = copy.deepcopy(base_actions)
    sales_to_advance = []
    for i, act in enumerate(adv_actions):
        for order in act.get("market", []):
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL" and i > 0:
                sales_to_advance.append((i, order))
                
    if sales_to_advance:
        for i, order in sales_to_advance:
            cand = copy.deepcopy(base_actions)
            if order in cand[i].get("market", []):
                cand[i]["market"].remove(order)
            cand[0].setdefault("market", []).insert(0, order)
            candidates.append({"tape_id": cur_id, "actions": cand, "type": "front_run"})
            
    for alt_id, alt_tape in tapes.items():
        if alt_id != cur_id:
            alt_actions = []
            for i in range(H):
                if step + i < len(alt_tape):
                    alt_actions.append(copy.deepcopy(alt_tape[step + i]))
                else:
                    alt_actions.append({"farmer": ["PASS"], "hands": [], "market": []})
            candidates.append({"tape_id": alt_id, "actions": alt_actions, "type": "switch"})
            
    return candidates

def compute_score(candidate, obs, H, opp_forecast):
    G_profit = 0.0
    G_defense = 0.0
    C_risk = 0.0
    
    market_prices = obs.get("market", {}).get("prices", {})
    
    # Extract item names from opp_forecast list
    opp_dump_items = set()
    if opp_forecast:
        for d in opp_forecast:
            opp_dump_items.update(d.keys())
    
    # 1. Base Profit
    # If the candidate sells earlier, it gets a slight time-value bonus
    for i, step_data in enumerate(candidate["actions"]):
        for order in step_data.get("market", []):
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                item = order[1]
                qty = int(order[2] or 0)
                p = float(market_prices.get(item, _BASE_PRICE.get(item, 10)))
                # slight discount for later steps so earlier sells win ties
                G_profit += (qty * p) * (1.0 - 0.001 * i)
                
                # 2. Defense Term
                if item in opp_dump_items:
                    if i == 0:
                        G_defense += 200.0  # Big bonus for front-running
                    else:
                        G_defense -= 500.0  # Penalty for selling after dump

    # 3. Risk Term
    if candidate["type"] == "switch":
        C_risk += 5000000.0  # disabled tape switching for now

    if candidate["type"] == "front_run":
        # Check if we actually have the item in our shed right now!
        my_shed = (obs.get("private") or {}).get("shed", {})
        for order in candidate["actions"][0].get("market", []):
            if isinstance(order, list) and len(order) >= 3 and order[0] == "SELL":
                item = order[1]
                qty = int(order[2] or 0)
                if my_shed.get(item, 0) < qty:
                    C_risk += 999999.0 # We cant front-run what we dont have

    return G_profit + G_defense - C_risk

def move_toward(pos, target, tiles):
    x, y = pos
    tx, ty = target
    choices = []
    if tx < x: choices.append(("WEST", (x - 1, y)))
    if tx > x: choices.append(("EAST", (x + 1, y)))
    if ty < y: choices.append(("NORTH", (x, y - 1)))
    if ty > y: choices.append(("SOUTH", (x, y + 1)))
    size = len(tiles)
    for op, (nx, ny) in choices:
        if 0 <= nx < size and 0 <= ny < size and tiles[ny][nx] != "LOCKED":
            return [op]
    return ["PASS"]

def efficiency_overlay(action, obs):
    player = obs.get("player", 0)
    farm = (obs.get("farms") or [])[player]
    tiles = farm.get("tiles") or []
    size = len(tiles)
    positions = [farm.get("farmer", [0, 0])] + (farm.get("hands") or [])
    
    unwatered = set()
    unfed = set()
    weeds = set()
    for y, row in enumerate(tiles):
        for x, tile in enumerate(row):
            if isinstance(tile, dict):
                if tile.get("kind") == "WEED":
                    weeds.add((x, y))
                elif tile.get("kind") == "PLANT" and int(tile.get("consecutive_unwatered", 0) or 0) > 0:
                    if int(tile.get("yield_units", 10) or 0) > 0:
                        unwatered.add((x, y))
                elif tile.get("kind") in ["COOP", "PASTURE"] and tile.get("animal") and int(tile.get("consecutive_unfed", 0) or 0) > 0:
                    unfed.add((x, y))

    tasks = unwatered | unfed | weeds
    ops = [action.get("farmer", ["PASS"])] + (action.get("hands") or [])
    ops += [["PASS"]] * max(0, len(positions) - len(ops))
    
    for i, (pos_raw, op) in enumerate(zip(positions, ops)):
        if op and op[0] == "PASS" and tasks:
            pos = tuple(pos_raw)
            x, y = pos
            if pos in unwatered:
                new_op = ["WATER"]
                unwatered.discard(pos)
                tasks.discard(pos)
            elif pos in unfed:
                my_inv = (obs.get("private") or {}).get("shed", {}).get("WHEAT", 0)
                if my_inv > 0:
                    new_op = ["FEED"]
                    unfed.discard(pos)
                    tasks.discard(pos)
                else:
                    new_op = ["PASS"]
            elif pos in weeds:
                new_op = ["DIG"]
                weeds.discard(pos)
                tasks.discard(pos)
            else:
                target = min(tasks, key=lambda q: abs(q[0] - x) + abs(q[1] - y))
                new_op = move_toward(pos, target, tiles)
                
            if i == 0:
                action["farmer"] = new_op
            else:
                while len(action.setdefault("hands", [])) <= i - 1:
                    action["hands"].append(["PASS"])
                action["hands"][i - 1] = new_op

def agent(obs, config=None):
    global _LAST_STEP, _OPP_MODEL, _CURRENT_TAPE
    load_tapes()
    
    if _OPP_MODEL is None or obs.get("step", 0) <= _LAST_STEP:
        _OPP_MODEL = OpponentModel()
        _CURRENT_TAPE = "151k"
        
    step = min(int(obs.get("step", 0)), 719)
    _OPP_MODEL.update(obs)
    _LAST_STEP = step

    H = 5
    opp_forecast = _OPP_MODEL.forecast(obs, H)
    candidates = get_candidates(_TAPES, _CURRENT_TAPE, step, H)
    
    best_score = float('-inf')
    best_candidate = None
    
    for c in candidates:
        score = compute_score(c, obs, H, opp_forecast)
        if score > best_score:
            best_score = score
            best_candidate = c
            
    if best_candidate and best_candidate["tape_id"] != _CURRENT_TAPE:
        _CURRENT_TAPE = best_candidate["tape_id"]
        
    if best_candidate and best_candidate["type"] == "front_run":
        for i_step in range(H):
            if step + i_step < len(_TAPES[_CURRENT_TAPE]):
                _TAPES[_CURRENT_TAPE][step + i_step] = copy.deepcopy(best_candidate["actions"][i_step])

    action = copy.deepcopy(best_candidate["actions"][0]) if best_candidate else {"farmer": ["PASS"], "hands": [], "market": []}

    # efficiency_overlay(action, obs)
    return action
