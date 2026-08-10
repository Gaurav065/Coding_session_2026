# strategy.py
from typing import Dict, List, Tuple, Optional
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
    tomato_target: int = 0
    goose_target: int = 0
    build_coops: int = 0
    sell_plan: Dict[str, int] = field(default_factory=dict)
    buy_seeds: Dict[str, int] = field(default_factory=dict)
    buy_animals: Dict[str, int] = field(default_factory=dict)

class Strategy:
    def __init__(self):
        self.market = MarketPredictor()
        self.last_plan: Optional[DailyPlan] = None
    
    def create_plan(self, state: GameState) -> DailyPlan:
        self.market.update(state.obs["market"])
        plan = DailyPlan()
        
        budget = state.money
        
        plan.sell_plan = self._create_sell_plan(state)
        est_revenue = sum(qty * state.market["prices"].get(p, 1) for p, qty in plan.sell_plan.items())
        budget += est_revenue
        
        # Land: NE at day 2 if affordable
        if state.day >= 2:
            plan.land_purchase = self._decide_land(state, budget)
            if plan.land_purchase:
                budget -= QUADRANT_COSTS[plan.land_purchase]
        
        # Hands: hire early
        if state.day >= 1:
            plan.target_hands = 1
        if state.day >= 5:
            plan.target_hands = 2
        hand_cost = self._hand_cost(len(state.hands), plan.target_hands)
        budget -= hand_cost
        
        empty_tiles = len(state.empty_unlocked_tiles())
        current_geese = state.geese_count()
        empty_coops = len(state.empty_structures("COOP"))
        
        # AGGRESSIVE EARLY GAME: Geese at day 3
        if state.day <= 2:
            plan.wheat_target = min(6, len(state.empty_unlocked_tiles()))
            plan.goose_target = 0
            plan.build_coops = 0
        elif state.day <= 5:
            plan.wheat_target = min(6, len(state.empty_unlocked_tiles()))
            if budget >= 600 and state.geese_count() == 0:
                plan.goose_target = 2
                plan.build_coops = max(0, 2 - len(state.empty_structures("COOP")))
            else:
                plan.goose_target = state.geese_count()
        elif state.day <= 12:
            plan.wheat_target = min(6, len(state.empty_unlocked_tiles()))
            if budget >= 1000:
                plan.goose_target = max(state.geese_count(), 4)
                plan.build_coops = max(0, plan.goose_target - state.geese_count() - len(state.empty_structures("COOP")))
            else:
                plan.goose_target = state.geese_count()
        elif state.day <= 20:
            plan.wheat_target = min(4, len(state.empty_unlocked_tiles()))
            max_geese = min(len(state.empty_unlocked_tiles()) // 2, 8)
            if budget >= 500:
                plan.goose_target = max(state.geese_count(), min(max_geese, 6))
                plan.build_coops = max(0, plan.goose_target - state.geese_count() - len(state.empty_structures("COOP")))
            else:
                plan.goose_target = state.geese_count()
        else:
            plan.wheat_target = min(4, len(state.empty_unlocked_tiles()))
            plan.goose_target = state.geese_count()
            plan.build_coops = 0
        
        self._calc_purchases(state, plan)
        self.last_plan = plan
        return plan
    
    def _decide_land(self, state: GameState, budget: int) -> Optional[str]:
        for quad in QUADRANT_ORDER:
            if quad not in state.unlocked:
                cost = QUADRANT_COSTS[quad]
                if budget >= cost and (quad == "NE" or "NE" in state.unlocked):
                    return quad
        return None
    
    def _hand_cost(self, current: int, target: int) -> int:
        costs = [1, 1, 2, 3, 5, 8, 13, 21]
        cost = 0
        for i in range(target - current):
            idx = current + i
            if idx < len(costs):
                cost += costs[idx]
        return cost
    
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
        plan = {}
        for product, qty in state.shed.items():
            if qty == 0 or product == "SEEDS":
                continue
            
            if product == "WHEAT":
                if qty > 3:
                    plan[product] = qty - 3
                continue
            
            if product == "EGG":
                if qty > 2:
                    plan[product] = qty - 2
                continue
            
            if product in ["MELON", "STRAWBERRY", "MILK", "WOOL"]:
                current_inv = state.market["inventory"].get(product, 10000)
                opt_qty, _ = self.market.optimal_sell_batch(product, qty, current_inv)
                if opt_qty > 0:
                    plan[product] = opt_qty
            else:
                if qty > 3:
                    plan[product] = qty - 3
        
        return plan


class TaskScheduler:
    def __init__(self):
        self.last_wheat_pos = None
    
    def schedule(self, state: GameState, plan: DailyPlan) -> Dict:
        actions = {"farmer": ["PASS"], "hands": [], "market": []}
        
        # Build market every turn with fresh sell quantities
        actions["market"] = self._build_market_actions(state, plan)
        
        all_units = ["farmer"] + [f"hand_{i}" for i in range(len(state.hands))]
        positions = {"farmer": state.farmer_pos}
        for i, pos in enumerate(state.hands):
            positions[f"hand_{i}"] = pos
        
        queues = self._build_queues(state, plan, positions)
        
        farmer_action = self._pop_action(state, "farmer", queues.get("farmer", []), positions["farmer"])
        actions["farmer"] = farmer_action
        
        hand_actions = []
        for i in range(len(state.hands)):
            hand_id = f"hand_{i}"
            hand_action = self._pop_action(state, hand_id, queues.get(hand_id, []), positions[hand_id])
            hand_actions.append(hand_action)
        actions["hands"] = hand_actions
        
        return actions
    
    def _build_market_actions(self, state: GameState, plan: DailyPlan) -> List[List]:
        actions = []
        money = state.money
        
        # Dynamic sell plan based on CURRENT shed inventory
        sell_now = self._compute_sell_now(state)
        
        for prod in ["EGG", "WOOL", "MILK", "TOMATO", "WHEAT", "FERTILIZER"]:
            qty = sell_now.get(prod, 0)
            if qty > 0:
                actions.append(["SELL", prod, qty])
        
        if plan.land_purchase and money >= QUADRANT_COSTS.get(plan.land_purchase, 9999):
            actions.append(["BUY_LAND"])
            money -= QUADRANT_COSTS[plan.land_purchase]
        
        current = len(state.hands)
        costs = [1, 1, 2, 3, 5, 8, 13, 21]
        for i in range(plan.target_hands - current):
            idx = current + i
            if idx < len(costs) and money >= costs[idx]:
                actions.append(["HIRE"])
                money -= costs[idx]
        
        for count in range(plan.buy_animals.get("GOOSE", 0)):
            if money >= ANIMAL_COSTS["GOOSE"]:
                actions.append(["BUY_ANIMAL", "GOOSE", 1])
                money -= ANIMAL_COSTS["GOOSE"]
        
        for count in range(plan.buy_seeds.get("WHEAT", 0)):
            if money >= SEED_COSTS["WHEAT"]:
                actions.append(["BUY_SEED", "WHEAT", 1])
                money -= SEED_COSTS["WHEAT"]
        
        return actions[:10]
    
    def _compute_sell_now(self, state: GameState) -> Dict[str, int]:
        sell = {}
        for product, qty in state.shed.items():
            if qty == 0 or product == "SEEDS":
                continue
            
            if product == "WHEAT":
                if qty > 3:
                    sell[product] = qty - 3
                continue
            
            if product == "EGG":
                if qty > 2:
                    sell[product] = qty - 2
                continue
            
            current_inv = state.market["inventory"].get(product, 10000)
            if product in ["MELON", "STRAWBERRY", "MILK", "WOOL"]:
                opt_qty, _ = self.market.optimal_sell_batch(product, qty, current_inv)
                if opt_qty > 0:
                    sell[product] = opt_qty
            else:
                if qty > 3:
                    sell[product] = qty - 3
        
        return sell
    
    def _build_queues(self, state: GameState, plan: DailyPlan, positions: Dict) -> Dict[str, List]:
        queues = {uid: [] for uid in positions}
        
        wheat_tiles = state.plant_tiles("WHEAT")
        if wheat_tiles:
            cx = sum(p[0] for p in wheat_tiles) // len(wheat_tiles)
            cy = sum(p[1] for p in wheat_tiles) // len(wheat_tiles)
            self.last_wheat_pos = (cx, cy)
        
        # PRIORITY 1: Water wheat
        for pos in state.wheat_needing_water():
            uid = self._nearest(positions, pos)
            queues[uid].append(("WATER", pos, 100))
        
        # PRIORITY 2: Feed geese
        for pos in state.animals_needing_feed():
            uid = self._nearest(positions, pos)
            queues[uid].append(("FEED", pos, 95))
        
        # PRIORITY 3: Care geese
        for pos in state.animals_needing_care():
            uid = self._nearest(positions, pos)
            queues[uid].append(("CARE", pos, 90))
        
        # PRIORITY 4: Harvest wheat
        for pos in state.wheat_ready_to_harvest():
            tile = state.get_tile(*pos)
            age = state.day - tile["planted_day"]
            if age >= 2 and tile["yield_units"] > 0:
                uid = self._nearest(positions, pos)
                queues[uid].append(("HARVEST", pos, 85))
        
        # PRIORITY 5: Harvest geese
        for pos in state.animals_ready_to_harvest():
            uid = self._nearest(positions, pos)
            queues[uid].append(("HARVEST", pos, 80))
        
        # PRIORITY 6: Collect fertilizer
        for pos in state.animals_with_fertilizer():
            uid = self._nearest(positions, pos)
            queues[uid].append(("COLLECT_FERTILIZER", pos, 75))
        
        # PRIORITY 7: Build coops
        for _ in range(plan.build_coops):
            empty = state.empty_unlocked_tiles()
            if empty:
                center = self.last_wheat_pos or SHED_TILES[0]
                pos = min(empty, key=lambda p: manhattan_distance(p, center))
                uid = self._nearest(positions, pos)
                queues[uid].append(("BUILD_COOP", pos, 70))
        
        # PRIORITY 8: Place geese (if geese in shed and empty coops)
        shed_geese = state.shed.get("GOOSE", 0)
        for pos in state.empty_structures("COOP"):
            if shed_geese > 0:
                uid = self._nearest(positions, pos)
                queues[uid].append(("PLACE_GOOSE", pos, 65))
                shed_geese -= 1
        
        # PRIORITY 9: Plant wheat (adjacent to existing)
        need_wheat = plan.wheat_target - len(state.plant_tiles("WHEAT"))
        if need_wheat > 0 and state.seeds.get("WHEAT", 0) > 0:
            empty = state.empty_unlocked_tiles()
            if empty:
                wheat_adjacent = []
                for pos in state.plant_tiles("WHEAT"):
                    for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)]:
                        adj = (pos[0]+dx, pos[1]+dy)
                        if adj in empty:
                            wheat_adjacent.append(adj)
                
                if wheat_adjacent:
                    pos = min(wheat_adjacent, key=lambda p: manhattan_distance(p, positions["farmer"]))
                else:
                    center = self.last_wheat_pos or positions["farmer"]
                    pos = min(empty, key=lambda p: manhattan_distance(p, center))
                
                uid = self._nearest(positions, pos)
                queues[uid].append(("PLANT_WHEAT", pos, 60))
        
        # PRIORITY 10: Clear weeds
        for pos in state.weed_tiles():
            uid = self._nearest(positions, pos)
            queues[uid].append(("DIG", pos, 10))
        
        return queues
    
    def _nearest(self, positions: Dict, target: Tuple[int, int]) -> str:
        best = "farmer"
        best_dist = float('inf')
        for uid, pos in positions.items():
            d = manhattan_distance(pos, target)
            if d < best_dist:
                best_dist = d
                best = uid
        return best
    
    def _pop_action(self, state: GameState, unit_id: str, queue: List, pos: Tuple[int, int]):
        if not queue:
            return ["PASS"]
        
        action_type, target, _ = queue[0]
        
        if pos != target:
            path = find_path(pos, target, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
            return ["PASS"]
        
        queue.pop(0)
        
        if action_type == "WATER": return ["WATER"]
        elif action_type == "FEED": return ["FEED"]
        elif action_type == "CARE": return ["CARE"]
        elif action_type == "HARVEST": return ["HARVEST"]
        elif action_type == "COLLECT_FERTILIZER": return ["COLLECT_FERTILIZER"]
        elif action_type == "BUILD_COOP": return ["BUILD_COOP"]
        elif action_type == "PLACE_GOOSE": 
            if state.shed.get("GOOSE", 0) > 0:
                return ["PLACE", "GOOSE"]
        elif action_type == "PLANT_WHEAT":
            if state.seeds.get("WHEAT", 0) > 0:
                return ["PLANT", "WHEAT"]
        elif action_type == "DIG": return ["DIG"]
        
        return ["PASS"]
    
    def _move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> List[str]:
        dx, dy = to_pos[0] - from_pos[0], to_pos[1] - from_pos[1]
        if dx == 1: return ["EAST"]
        if dx == -1: return ["WEST"]
        if dy == 1: return ["SOUTH"]
        if dy == -1: return ["NORTH"]
        return ["PASS"]