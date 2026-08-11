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

@dataclass
class DailyPlan:
    land_purchase: Optional[str] = None
    target_hands: int = 0
    wheat_target: int = 0
    goose_target: int = 0
    build_coops: int = 0
    buy_seeds: Dict[str, int] = field(default_factory=dict)
    buy_animals: Dict[str, int] = field(default_factory=dict)

@dataclass
class Job:
    id: int
    type: str  # 'DIG', 'WATER', 'HARVEST', 'FEED', 'CARE', 'PLACE_ANIMAL', 'PLANT', 'PICKUP', 'DROP', 'BUILD_COOP'
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
        
        # Disable land purchasing to save money unless we absolutely need it
        # Wait, if we cap at 15-20 wheat, we don't need land. The starter farm has 25 tiles.
        plan.land_purchase = None 
        
        if state.day >= 1: plan.target_hands = 1
        if state.day >= 3: plan.target_hands = 2
        if state.day >= 8: plan.target_hands = 3
        
        # Wheat and Goose scaling
        if state.day <= 5:
            plan.wheat_target = min(20, len(state.empty_unlocked_tiles()))
            if state.geese_count() < 2:
                plan.goose_target = 2
                plan.build_coops = max(0, 2 - sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP"))
            else:
                plan.goose_target = state.geese_count()
        elif state.day <= 15:
            plan.wheat_target = min(20, len(state.empty_unlocked_tiles()))
            empty_coops = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP" and t.get("animal") is None)
            if state.geese_count() < 6:
                plan.goose_target = min(6, state.geese_count() + 2)
                plan.build_coops = max(0, plan.goose_target - state.geese_count() - empty_coops)
            else:
                plan.goose_target = state.geese_count()
        else:
            plan.wheat_target = min(20, len(state.empty_unlocked_tiles()))
            plan.goose_target = state.geese_count()
            plan.build_coops = 0
            
        self._calc_purchases(state, plan)
        return plan
    
    def _calc_purchases(self, state: GameState, plan: DailyPlan):
        planted = len(state.plant_tiles("WHEAT"))
        in_shed = state.seeds.get("WHEAT", 0)
        have = planted + in_shed
        if have < plan.wheat_target:
            plan.buy_seeds["WHEAT"] = plan.wheat_target - have
        
        if plan.goose_target > state.geese_count():
            have = state.shed.get("GOOSE", 0) + state.geese_count()
            if have < plan.goose_target:
                plan.buy_animals["GOOSE"] = plan.goose_target - have
    
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
    def __init__(self):
        self.market = MarketPredictor()
        self.jobs: Dict[int, Job] = {}
        self.job_counter = 0
        self.agent_queues: Dict[str, List[Job]] = {} # Personal queue for sub-tasks like PICKUP/DROP
        
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
        for p in state.wheat_needing_water():
            self._add_job("WATER", p, priority=7)
            
        # 9. Harvest Crops (Priority 8)
        for p in state.wheat_ready_to_harvest():
            tile = state.get_tile(*p)
            age = state.day - tile["planted_day"]
            if age >= 2 and tile["yield_units"] > 0:
                self._add_job("HARVEST", p, priority=8)
                
        # 10. Plant Crops (Priority 9)
        planted = len(state.plant_tiles("WHEAT"))
        need = plan.wheat_target - planted
        if need > 0 and state.seeds.get("WHEAT", 0) > 0:
            empty = state.empty_unlocked_tiles()
            for i, p in enumerate(empty[:need]):
                self._add_job("PLANT", p, priority=9, args=["WHEAT"])
                
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
                # Add pickup job to personal queue
                pickup_job = Job(-1, 'PICKUP', shed_target, -1, ["WHEAT", "10"])
                self.agent_queues[agent_id].append(pickup_job)
                return self._execute_agent(agent_id, state) # re-evaluate
                
            if job.type == 'PLACE_ANIMAL' and inv.get("GOOSE", 0) == 0:
                pickup_job = Job(-1, 'PICKUP', shed_target, -1, ["GOOSE", "1"])
                self.agent_queues[agent_id].append(pickup_job)
                return self._execute_agent(agent_id, state)
                
            if job.type == 'HARVEST' and state.get_tile(*job.target_pos).get("kind") == "COOP" and inv.get("EGG", 0) >= 4:
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
            
        current = len(state.hands)
        costs = [1, 1, 2, 3, 5, 8, 13, 21]
        hires = 0
        for i in range(plan.target_hands - current):
            idx = current + i
            if idx < len(costs) and money >= costs[idx]:
                actions["market"].append(["HIRE"])
                money -= costs[idx]
                hires += 1
        plan.target_hands -= hires
        
        if state.hour == 0:
            need_feed = max(0, state.geese_count() * 2 - state.shed.get("WHEAT", 0))
            for _ in range(min(10, need_feed)):
                if money >= state.market["prices"].get("WHEAT", 30):
                    actions["market"].append(["BUY_PRODUCT", "WHEAT", 1])
                    money -= state.market["prices"].get("WHEAT", 30)
                    
        bought_geese = 0
        for _ in range(plan.buy_animals.get("GOOSE", 0)):
            if money >= ANIMAL_COSTS["GOOSE"] + 100 + 30:
                actions["market"].append(["BUY_ANIMAL", "GOOSE", 1])
                money -= ANIMAL_COSTS["GOOSE"]
                bought_geese += 1
        if "GOOSE" in plan.buy_animals: plan.buy_animals["GOOSE"] -= bought_geese
        
        bought_seeds = 0
        for _ in range(plan.buy_seeds.get("WHEAT", 0)):
            if money >= SEED_COSTS["WHEAT"]:
                actions["market"].append(["BUY_SEED", "WHEAT", 1])
                money -= SEED_COSTS["WHEAT"]
                bought_seeds += 1
        if "WHEAT" in plan.buy_seeds: plan.buy_seeds["WHEAT"] -= bought_seeds
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
