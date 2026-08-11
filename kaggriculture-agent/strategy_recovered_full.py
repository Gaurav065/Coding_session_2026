from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from constants import (
    CROPS, ANIMALS, QUADRANT_COSTS, QUADRANT_ORDER, 
    SHED_TILES, SEED_COSTS, ANIMAL_COSTS, STRUCTURE_COSTS,
    MARKET_PARAMS, SHOP_DEMANDS
)
from state import GameState
from market import MarketPredictor
from pathfinding import find_path, manhattan_distance

import json
import os

# Default fallback parameters (our previous manual heuristics)
DEFAULT_PARAMS = {
    "wheat_ratio": 1.0,
    "tomato_ratio": 0.0,
    "melon_ratio": 0.0,
    "land_buy_threshold": 999999,  # Never buy by default
    "max_hands": 3,
    "goose_target": 6
}

def load_params():
    try:
        if os.path.exists('params.json'):
            with open('params.json', 'r') as f:
                return json.load(f)
    except:
        pass
    return DEFAULT_PARAMS

GLOBAL_PARAMS = load_params()

@dataclass
class DailyPlan:
    land_purchase: Optional[str] = None
    target_hands: int = 0
    crop_targets: Dict[str, int] = field(default_factory=dict)
    animal_targets: Dict[str, int] = field(default_factory=dict)
    build_coops: int = 0
    build_pastures: int = 0
    buy_seeds: Dict[str, int] = field(default_factory=dict)
    buy_animals: Dict[str, int] = field(default_factory=dict)

@dataclass
class Job:
    id: int
    type: str  # 'DIG', 'WATER', 'HARVEST', 'FEED', 'CARE', 'PLACE_ANIMAL', 'PLANT', 'PICKUP', 'DROP', 'BUILD_COOP', 'BUILD_PASTURE', 'FERTILIZE'
    target_pos: Tuple[int, int]
    priority: int  # lower is higher priority
    args: List[str] = field(default_factory=list)
    assigned_to: Optional[str] = None  # 'FARMER', 'HAND_0', etc.
    status: str = 'PENDING'

class Strategy:
    def __init__(self):
        self.market = MarketPredictor()
    
    def create_plan(self, state: GameState) -> DailyPlan:
        self.market.update(state.obs["market"])
        plan = DailyPlan()
        
        budget = state.money
        sell_plan = self._create_sell_plan(state)
        est_revenue = sum(qty * state.market["prices"].get(p, 1) for p, qty in sell_plan.items())
        budget += est_revenue
        
        p = GLOBAL_PARAMS
        stop_day = p.get("stop_investment_day", 26)
        
        # 1. Land Purchasing Logic
        plan.land_purchase = None
        if state.day < stop_day:
            empty = len(state.empty_unlocked_tiles())
            if empty < 15:
                if "NE" not in state.unlocked and budget > p.get("buy_NE_thresh", 1000):
                    plan.land_purchase = "NE"
                elif "SW" not in state.unlocked and budget > p.get("buy_SW_thresh", 2000) and "NE" in state.unlocked:
                    plan.land_purchase = "SW"
        
        # 2. Hand Scaling Logic
        quadrants_active = max(1, len(state.find_tiles(lambda t: isinstance(t, dict) and t.get("kind") in ["PLANT", "WEED", "TREE"])) // 25)
        desired_hands = 6 * quadrants_active
        
        # Never spend more than 10% of current budget on daily hand salaries
        max_hand_spend = max(30, budget * 0.10)
        costs = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765, 10946]
        affordable = 0
        spend = 0
        for c in costs:
            if spend + c <= max_hand_spend:
                spend += c
                affordable += 1
            else:
                break
                
        plan.target_hands = min(desired_hands, affordable)
        if state.day >= stop_day:
            plan.target_hands = len(state.hands) # Don't hire more at the end
            
        # 3. Crop Target Logic (Dynamic Rotation)
        available_tiles = len(state.find_tiles(lambda t: t is None or (isinstance(t, dict) and t.get("kind") in ["PLANT", "TREE", "WEED"])))
        
        cash_crops = ["TOMATO", "STRAWBERRY", "CARROT", "MELON"]
        best_crop = "TOMATO"
        best_profit = -9999
        for c in cash_crops:
            price = state.market["prices"].get(c, MARKET_PARAMS[c]["base"])
            if price > best_profit:
                best_profit = price
                best_crop = c
                
        if state.day < stop_day:
            plan.crop_targets["WHEAT"] = int(available_tiles * 0.25)
            plan.crop_targets[best_crop] = available_tiles - plan.crop_targets["WHEAT"]
        else:
            for c in ["WHEAT", "TOMATO", "CARROT", "STRAWBERRY", "MELON"]:
                plan.crop_targets[c] = len(state.plant_tiles(c))
            
        # 4. Animal Target Logic
        if state.day < stop_day:
            plan.animal_targets["GOOSE"] = p.get("goose_target", 6)
            empty_coops = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP" and t.get("animal") is None)
            plan.build_coops = max(0, plan.animal_targets["GOOSE"] - state.geese_count() - empty_coops)
        else:
            plan.animal_targets["GOOSE"] = state.geese_count()
            plan.build_coops = 0
            
        self._calc_purchases(state, plan)
        return plan
    
    def _calc_purchases(self, state: GameState, plan: DailyPlan):
        budget = state.money
        for crop, target in plan.crop_targets.items():
            planted = len(state.plant_tiles(crop))
            in_shed = state.seeds.get(crop, 0)
            have = planted + in_shed
            if have < target:
                plan.buy_seeds[crop] = target - have
        
        # 1. Budget for Feed (Priority over everything else so animals don't die)
        cows = len(state.occupied_animal_structures("COW"))
        sheep = len(state.occupied_animal_structures("SHEEP"))
        geese = state.geese_count()
        need_feed = max(0, (geese + cows + sheep) * 2 - state.shed.get("WHEAT", 0))
        if need_feed > 0:
            feed_cost_per = state.market["prices"].get("WHEAT", 30)
            feed_cost = min(need_feed, budget // feed_cost_per) * feed_cost_per
            budget -= feed_cost
            
        for animal, target in plan.animal_targets.items():
            current = state.geese_count() if animal == "GOOSE" else 0
            in_shed = state.shed.get(animal, 0)
            have = current + in_shed
            if have < target:
                plan.buy_animals[animal] = target - have
    
    def _create_sell_plan(self, state: GameState) -> Dict[str, int]:
        sell = {}
        for product, qty in state.shed.items():
            if qty == 0 or product == "SEEDS": continue
            if product == "WHEAT":
                if qty >= 3: sell[product] = qty - 2
                continue
            if product == "EGG":
                sell[product] = qty
                continue
            current_inv = state.market["inventory"].get(product, 10000)
            if product in ["MELON", "STRAWBERRY", "MILK", "WOOL"]:
                opt_qty, _ = self.market.optimal_sell_batch(product, qty, current_inv)
                if opt_qty > 0: sell[product] = opt_qty
            else:
                if qty >= 3: sell[product] = qty - 2
        return sell

class DynamicController:
    """
    The DynamicController implements a decoupled, state-driven Job Queue.
    Instead of hardcoding action sequences, it scans the game state and generates
    a list of Jobs based on priority. Agents (Farmer/Hands) are then dynamically
    assigned the highest priority job that is closest to them.
    
    This architecture handles edge cases like getting stuck, animal death, and 
    excessive walking by automatically re-evaluating the optimal action for each 
    agent every turn.
    """
    def __init__(self):
        self.market = MarketPredictor()
        self.jobs: Dict[int, Job] = {}
        self.job_counter = 0
        # Personal queues allow an agent to inject prerequisites (e.g. going to shed to pick up feed)
        self.agent_queues: Dict[str, List[Job]] = {} 
        
    def _add_job(self, job_type: str, target_pos: Tuple[int, int], priority: int, args: List[str] = None):
        for j in self.jobs.values():
            if j.type == job_type and j.target_pos == target_pos and j.status != 'COMPLETED':
                return # Job already exists
        self.job_counter += 1
        self.jobs[self.job_counter] = Job(self.job_counter, job_type, target_pos, priority, args or [])

    def _sync_world_jobs(self, state: GameState, plan: DailyPlan):
        # 1. Critical Feed (Priority 0)
        for p in state.occupied_animal_structures("GOOSE"):
            tile = state.get_tile(*p)
            if not tile["fed_today"] and tile.get("consecutive_unfed", 0) > 0:
                self._add_job("FEED", p, priority=0)
                
        # 2. Dig Weeds (Priority 1)
        for p in state.weed_tiles():
            self._add_job("DIG", p, priority=1)
            
        # 3. Standard Feed (Priority 2)
        for p in state.animals_needing_feed():
            self._add_job("FEED", p, priority=2)
            
        # 4. Build Coop (Priority 3) - Farmer only
        coop_count = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP")
        if coop_count < plan.build_coops and state.money >= 100:
            empty = state.empty_unlocked_tiles()
            if empty:
                target = min(empty, key=lambda p: manhattan_distance(p, SHED_TILES[0]))
                self._add_job("BUILD_COOP", target, priority=3)
                
        # 5. Place Animal (Priority 4)
        if state.shed.get("GOOSE", 0) > 0:
            empty = state.empty_structures("COOP")
            if empty:
                self._add_job("PLACE_ANIMAL", empty[0], priority=4, args=["GOOSE"])
                
        # 6. Care Animals (Priority 5)
        for p in state.animals_needing_care():
            self._add_job("CARE", p, priority=5)
            
        # 7. Harvest Animals (Priority 6)
        for p in state.animals_ready_to_harvest():
            self._add_job("HARVEST", p, priority=6)
            
        # 8. Water Crops (Priority 7)
        for p in state.crops_needing_water():
            self._add_job("WATER", p, priority=7)
            
        # 8.5. Fertilize Crops (Priority 7)
        for p in state.crops_needing_fertilizer():
            self._add_job("FERTILIZE", p, priority=7)
            
        # 9. Harvest Crops (Priority 8)
        for p in state.crops_ready_to_harvest():
            self._add_job("HARVEST", p, priority=8)
                
        # 10. Plant Crops (Priority 9)
        for crop, target in plan.crop_targets.items():
            planted = len(state.plant_tiles(crop))
            need = target - planted
            if need > 0 and state.seeds.get(crop, 0) > 0:
                empty = state.empty_unlocked_tiles()
                # Ensure we don't assign multiple plants to the same empty tile
                # _add_job checks for existing jobs on target_pos
                for i, p in enumerate(empty[:need]):
                    self._add_job("PLANT", p, priority=9, args=[crop])
                
        # Clean up completed or invalid jobs
        to_delete = []
        for jid, j in self.jobs.items():
            if j.status == 'COMPLETED':
                to_delete.append(jid)
        for jid in to_delete:
            del self.jobs[jid]

    def _get_agent_pos(self, agent_id: str, state: GameState) -> Tuple[int, int]:
        if agent_id == 'FARMER':
            return state.farmer_pos
        else:
            idx = int(agent_id.split('_')[1])
            return state.hands[idx]
            
    def _get_agent_inv(self, agent_id: str, state: GameState) -> Dict:
        if agent_id == 'FARMER':
            return state.inventories[0]
        else:
            idx = int(agent_id.split('_')[1])
            return state.inventories[idx + 1]

    def _assign_jobs(self, state: GameState):
        agents = ['FARMER'] + [f'HAND_{i}' for i in range(len(state.hands))]
        for agent_id in agents:
            if agent_id not in self.agent_queues:
                self.agent_queues[agent_id] = []
            
            # If agent has personal queue jobs, don't assign global jobs
            if len(self.agent_queues[agent_id]) > 0:
                continue
                
            # If agent is already assigned a global job, continue
            if any(j.assigned_to == agent_id and j.status != 'COMPLETED' for j in self.jobs.values()):
                continue
                
            # Find best job
            best_job = None
            best_score = 999999
            
            pos = self._get_agent_pos(agent_id, state)
            
            for j in self.jobs.values():
                if j.assigned_to is None and j.status == 'PENDING':
                    if j.type == 'BUILD_COOP' and agent_id != 'FARMER':
                        continue # Only farmer can build coops according to rule (wait, hands can't? hands can build too, but let's limit to farmer to avoid money sync issues)
                    dist = manhattan_distance(pos, j.target_pos)
                    score = j.priority * 100 + dist
                    if score < best_score:
                        best_score = score
                        best_job = j
            
            if best_job:
                best_job.assigned_to = agent_id
                best_job.status = 'IN_PROGRESS'

    def _execute_agent(self, agent_id: str, state: GameState) -> List[str]:
        pos = self._get_agent_pos(agent_id, state)
        inv = self._get_agent_inv(agent_id, state)
        shed_target = min(SHED_TILES, key=lambda p: manhattan_distance(pos, p))
        
        # Check personal queue first (e.g. forced pickup/drop)
        if len(self.agent_queues[agent_id]) > 0:
            job = self.agent_queues[agent_id][0]
            action = self._attempt_job(pos, job, state)
            if action != ["PASS"]:
                if action[0] not in ("NORTH", "SOUTH", "EAST", "WEST"):
                    self.agent_queues[agent_id].pop(0) # completed
                return action
            else:
                self.agent_queues[agent_id].pop(0) # failed, remove it
        
        # Check global assigned job
        job = None
        for j in self.jobs.values():
            if j.assigned_to == agent_id and j.status == 'IN_PROGRESS':
                job = j
                break
                
        if job:
            # Pre-requisite checks
            if job.type == 'FEED' and inv.get("WHEAT", 0) == 0:
                if state.shed.get("WHEAT", 0) > 0:
                    pickup_job = Job(-1, 'PICKUP', shed_target, -1, ["WHEAT", "10"])
                    self.agent_queues[agent_id].append(pickup_job)
                    return self._execute_agent(agent_id, state)
                else:
                    job.status = 'COMPLETED'
                    return ["PASS"]
                
            if job.type == 'PLACE_ANIMAL':
                animal = job.args[0] if job.args else "GOOSE"
                if inv.get(animal, 0) == 0:
                    if state.shed.get(animal, 0) > 0:
                        pickup_job = Job(-1, 'PICKUP', shed_target, -1, [animal, "1"])
                        self.agent_queues[agent_id].append(pickup_job)
                        return self._execute_agent(agent_id, state)
                    else:
                        job.status = 'COMPLETED'
                        return ["PASS"]
                
            if job.type == 'FERTILIZE' and inv.get("FERTILIZER", 0) == 0:
                if state.shed.get("FERTILIZER", 0) > 0:
                    pickup_job = Job(-1, 'PICKUP', shed_target, -1, ["FERTILIZER", "10"])
                    self.agent_queues[agent_id].append(pickup_job)
                    return self._execute_agent(agent_id, state)
                else:
                    job.status = 'COMPLETED'
                    return ["PASS"]
                    
            tile_data = state.get_tile(*job.target_pos)
            if job.type == 'HARVEST' and isinstance(tile_data, dict) and tile_data.get("kind") == "COOP" and inv.get("EGG", 0) >= 4:
                drop_job = Job(-1, 'DROP', shed_target, -1, [])
                self.agent_queues[agent_id].append(drop_job)
                return self._execute_agent(agent_id, state)
                
            # Execute job
            action = self._attempt_job(pos, job, state)
            if action != ["PASS"]:
                if action[0] not in ("NORTH", "SOUTH", "EAST", "WEST"):
                    job.status = 'COMPLETED'
                return action
            else:
                job.status = 'COMPLETED' # Failed to execute, mark complete to drop it
        
        return ["PASS"]

    def _attempt_job(self, pos: Tuple[int, int], job: Job, state: GameState) -> List[str]:
        if pos == job.target_pos or (job.type in ("PICKUP", "DROP") and pos in SHED_TILES):
            if job.type == "PLANT":
                return ["PLANT", job.args[0]]
            if job.type == "PLACE_ANIMAL":
                return ["PLACE", job.args[0]]
            if job.type in ("PICKUP", "DROP", "BUY_LAND", "HIRE"):
                return [job.type] + job.args
            if job.type == "COLLECT_FERTILIZER":
                return ["CARE"]
            return [job.type]
            
        path = find_path(pos, job.target_pos, state)
        if path and len(path) > 1:
            return self._move(pos, path[1])
        return ["PASS"]
        
    def _move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> List[str]:
        dx, dy = to_pos[0] - from_pos[0], to_pos[1] - from_pos[1]
        if dx == 1: return ["EAST"]
        if dx == -1: return ["WEST"]
        if dy == 1: return ["SOUTH"]
        if dy == -1: return ["NORTH"]
        return ["PASS"]

    def get_actions(self, state: GameState, plan: DailyPlan) -> Dict:
        self._sync_world_jobs(state, plan)
        self._assign_jobs(state)
        
        actions = {"farmer": ["PASS"], "hands": [], "market": []}
        
        # Market Actions
        money = state.money
        if state.hour == 0 or state.total_shed_items() > 90:
            sell = Strategy()._create_sell_plan(state)
            for p, q in sell.items(): actions["market"].append(["SELL", p, q])
            
        # Generate fibonacci costs for hands
        costs = [1, 1]
        for _ in range(18):
            costs.append(costs[-1] + costs[-2])
            
        current = len(state.hands)
        hires = 0
        for i in range(plan.target_hands - current):
            idx = current + i
            if len(actions["market"]) >= 6: break # Reserve 4 actions for buying feed, animals, seeds
            if idx < len(costs) and money >= costs[idx]:
                actions["market"].append(["HIRE"])
                money -= costs[idx]
                hires += 1
        
        if state.hour <= 1:
            geese = state.geese_count() + plan.buy_animals.get("GOOSE", 0)
            cows = len(state.occupied_animal_structures("COW")) + plan.buy_animals.get("COW", 0)
            sheep = len(state.occupied_animal_structures("SHEEP")) + plan.buy_animals.get("SHEEP", 0)
            need_feed = max(0, (geese + cows + sheep) * 2 - state.shed.get("WHEAT", 0))
            if need_feed > 0 and money >= state.market["prices"].get("WHEAT", 30) and len(actions["market"]) < 10:
                cost_per = state.market["prices"].get("WHEAT", 30)
                affordable_feed = int(min(need_feed, money // cost_per))
                if affordable_feed > 0:
                    actions["market"].append(["BUY_PRODUCT", "WHEAT", affordable_feed])
                    money -= affordable_feed * cost_per
                    
        for animal, target_qty in list(plan.buy_animals.items()):
            if len(actions["market"]) >= 10: break
            if target_qty > 0 and money >= ANIMAL_COSTS.get(animal, 100):
                affordable = int(min(target_qty, money // ANIMAL_COSTS.get(animal, 100)))
                if affordable > 0:
                    actions["market"].append(["BUY_ANIMAL", animal, affordable])
                    money -= affordable * ANIMAL_COSTS.get(animal, 100)
                    plan.buy_animals[animal] -= affordable
            
        for crop, target_qty in list(plan.buy_seeds.items()):
            if len(actions["market"]) >= 10: break
            if target_qty > 0 and money >= SEED_COSTS.get(crop, 10):
                affordable = int(min(target_qty, money // SEED_COSTS.get(crop, 10)))
                if affordable > 0:
                    actions["market"].append(["BUY_SEED", crop, affordable])
                    money -= affordable * SEED_COSTS.get(crop, 10)
                    plan.buy_seeds[crop] -= affordable
                    
        actions["market"] = actions["market"][:10]

        # Agent Actions
        actions["farmer"] = self._execute_agent("FARMER", state)
        for i in range(len(state.hands)):
            actions["hands"].append(self._execute_agent(f"HAND_{i}", state))
            
        return actions

_controller = DynamicController()

def agent(obs: Dict) -> Dict[str, Any]:
    player = obs["player"]
    if not hasattr(_controller, '_state'): _controller._state = {}
    if player not in _controller._state: _controller._state[player] = {"last_day": -1, "plan": None}
    
    pstate = _controller._state[player]
    state = GameState(obs)
    
    if state.day != pstate["last_day"]:
        pstate["last_day"] = state.day
        pstate["plan"] = Strategy().create_plan(state)
        
    return _controller.get_actions(state, pstate["plan"])
