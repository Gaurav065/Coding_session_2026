# strategy.py
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
        
        if state.day >= 2:
            plan.land_purchase = self._decide_land(state, budget)
            if plan.land_purchase:
                budget -= QUADRANT_COSTS[plan.land_purchase]
        
        if state.day >= 1:
            plan.target_hands = 1
        if state.day >= 3:
            plan.target_hands = 2
        if state.day >= 8:
            plan.target_hands = 3
        hand_cost = self._hand_cost(len(state.hands), plan.target_hands)
        budget -= hand_cost
        
        current_geese = state.geese_count()
        
        if state.day <= 1:
            plan.wheat_target = min(6, len(state.empty_unlocked_tiles()))
            plan.goose_target = 0
            plan.build_coops = 0
        elif state.day == 2:
            plan.wheat_target = min(6, len(state.empty_unlocked_tiles()))
            if state.money >= 500 and state.geese_count() == 0:
                plan.goose_target = 2
                plan.build_coops = 2
            else:
                plan.goose_target = state.geese_count()
        elif state.day <= 5:
            plan.wheat_target = min(6, len(state.empty_unlocked_tiles()))
            if state.geese_count() < 2:
                plan.goose_target = 2
                plan.build_coops = max(0, 2 - sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP"))
            else:
                plan.goose_target = state.geese_count()
        elif state.day <= 12:
            plan.wheat_target = min(6, len(state.empty_unlocked_tiles()))
            empty_coops = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP" and t.get("animal") is None)
            if state.geese_count() < 4:
                plan.goose_target = min(4, state.geese_count() + 2)
                plan.build_coops = max(0, plan.goose_target - state.geese_count() - empty_coops)
            else:
                plan.goose_target = state.geese_count()
        elif state.day <= 20:
            plan.wheat_target = min(4, len(state.empty_unlocked_tiles()))
            empty_coops = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP" and t.get("animal") is None)
            if state.geese_count() < 6:
                plan.goose_target = min(6, state.geese_count() + 2)
                plan.build_coops = max(0, plan.goose_target - state.geese_count() - empty_coops)
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
                if qty >= 3:
                    plan[product] = qty - 2
                continue
            if product == "EGG":
                if qty >= 2:
                    plan[product] = qty - 1
                continue
            current_inv = state.market["inventory"].get(product, 10000)
            if product in ["MELON", "STRAWBERRY", "MILK", "WOOL"]:
                opt_qty, _ = self.market.optimal_sell_batch(product, qty, current_inv)
                if opt_qty > 0:
                    plan[product] = opt_qty
            else:
                if qty >= 3:
                    plan[product] = qty - 2
        return plan


class SimpleController:
    def __init__(self):
        self.market = MarketPredictor()
    
    def get_actions(self, state: GameState, plan: DailyPlan) -> Dict:
        actions = {"farmer": ["PASS"], "hands": [], "market": []}
        
        # Market every turn
        actions["market"] = self._market_actions(state, plan)
        
        # Simple deterministic actions
        actions["farmer"] = self._farmer_action(state, plan)
        
        hand_actions = []
        for i in range(len(state.hands)):
            hand_actions.append(self._hand_action(i, state, plan))
        actions["hands"] = hand_actions
        
        return actions
    
    def _market_actions(self, state: GameState, plan: DailyPlan) -> List[List]:
        actions = []
        money = state.money
        
        sell_now = self._compute_sell(state)
        est_rev = sum(qty * state.market["prices"].get(p, 1) for p, qty in sell_now.items())
        money += est_rev
        
        for prod in ["EGG", "WOOL", "MILK", "TOMATO", "WHEAT", "FERTILIZER"]:
            qty = self._sell_qty(state, prod)
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
        
        for _ in range(plan.buy_animals.get("GOOSE", 0)):
            if money >= ANIMAL_COSTS["GOOSE"]:
                actions.append(["BUY_ANIMAL", "GOOSE", 1])
                money -= ANIMAL_COSTS["GOOSE"]
        
        for _ in range(plan.buy_seeds.get("WHEAT", 0)):
            if money >= SEED_COSTS["WHEAT"]:
                actions.append(["BUY_SEED", "WHEAT", 1])
                money -= SEED_COSTS["WHEAT"]
        
        return actions[:10]
    
    def _compute_sell(self, state: GameState) -> Dict[str, int]:
        sell = {}
        for product, qty in state.shed.items():
            if qty == 0 or product == "SEEDS":
                continue
            if product == "WHEAT":
                if qty >= 3:
                    sell[product] = qty - 2
                continue
            if product == "EGG":
                if qty >= 2:
                    sell[product] = qty - 1
                continue
            current_inv = state.market["inventory"].get(product, 10000)
            if product in ["MELON", "STRAWBERRY", "MILK", "WOOL"]:
                opt_qty, _ = self.market.optimal_sell_batch(product, qty, current_inv)
                if opt_qty > 0:
                    sell[product] = opt_qty
            else:
                if qty >= 3:
                    sell[product] = qty - 2
        return sell
    
    def _sell_qty(self, state: GameState, product: str) -> int:
        qty = state.shed.get(product, 0)
        if qty == 0:
            return 0
        if product == "WHEAT":
            return max(0, qty - 2) if qty >= 3 else 0
        if product == "EGG":
            return max(0, qty - 1) if qty >= 2 else 0
        current_inv = state.market["inventory"].get(product, 10000)
        if product in ["MELON", "STRAWBERRY", "MILK", "WOOL"]:
            opt_qty, _ = self.market.optimal_sell_batch(product, qty, current_inv)
            return opt_qty
        return max(0, qty - 2) if qty >= 3 else 0
    
    def _farmer_action(self, state: GameState, plan: DailyPlan) -> List[str]:
        pos = state.farmer_pos
        
        # 1. Build coops (max 2, near shed)
        if plan.build_coops > 0:
            coop_count = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP")
            if coop_count < plan.build_coops:
                empty = state.empty_unlocked_tiles()
                if empty:
                    target = min(empty, key=lambda p: manhattan_distance(p, SHED_TILES[0]))
                    return self._move_or_act(pos, target, "BUILD_COOP", state)
        
        # 2. Plant wheat (near shed, max 6)
        need = plan.wheat_target - len(state.plant_tiles("WHEAT"))
        if need > 0 and state.seeds.get("WHEAT", 0) > 0:
            empty = state.empty_unlocked_tiles()
            if empty:
                target = min(empty, key=lambda p: manhattan_distance(p, SHED_TILES[0]))
                return self._move_or_act(pos, target, "PLANT_WHEAT", state)
        
        # 3. Water wheat
        for p in state.wheat_needing_water():
            return self._move_or_act(pos, p, "WATER", state)
        
        # 3. Harvest wheat
        for p in state.wheat_ready_to_harvest():
            tile = state.get_tile(*p)
            age = state.day - tile["planted_day"]
            if age >= 2 and tile["yield_units"] > 0:
                return self._move_or_act(pos, p, "HARVEST", state)
        
        return ["PASS"]
    
    def _hand_action(self, hand_idx: int, state: GameState, plan: DailyPlan) -> List[str]:
        if hand_idx >= len(state.hands):
            return ["PASS"]
        
        pos = state.hands[hand_idx]
        
        # Hand 0: Goose management - SIMPLE AND ROBUST
        if hand_idx == 0:
            # 1. Feed ALL geese (always feed if we can)
            for p in state.occupied_animal_structures("GOOSE"):
                return self._move_or_act(pos, p, "FEED", state)
            
            # 2. Care geese
            for p in state.occupied_animal_structures("GOOSE"):
                tile = state.get_tile(*p)
                if not tile.get("cared_today", False):
                    return self._move_or_act(pos, p, "CARE", state)
            
            # 3. Harvest eggs
            for p in state.occupied_animal_structures("GOOSE"):
                tile = state.get_tile(*p)
                if tile.get("yield_units", 0) > 0:
                    return self._move_or_act(pos, p, "HARVEST", state)
            
            # 4. Place geese in empty coops
            if state.shed.get("GOOSE", 0) > 0:
                for p in state.empty_structures("COOP"):
                    return self._move_or_act(pos, p, "PLACE_GOOSE", state)
            
            # 5. Help with wheat
            for p in state.wheat_needing_water():
                return self._move_or_act(pos, p, "WATER", state)
            
            for p in state.wheat_ready_to_harvest():
                tile = state.get_tile(*p)
                age = state.day - tile["planted_day"]
                if age >= 2 and tile["yield_units"] > 0:
                    return self._move_or_act(pos, p, "HARVEST", state)
            
            need = 6 - len(state.plant_tiles("WHEAT"))
            if need > 0 and state.seeds.get("WHEAT", 0) > 0:
                empty = state.empty_unlocked_tiles()
                if empty:
                    target = min(empty, key=lambda p: manhattan_distance(p, SHED_TILES[0]))
                    return self._move_or_act(pos, target, "PLANT_WHEAT", state)
            
            return ["PASS"]
        
        # Hand 1+: Wheat support
        else:
            for p in state.wheat_needing_water():
                return self._move_or_act(pos, p, "WATER", state)
            for p in state.wheat_ready_to_harvest():
                tile = state.get_tile(*p)
                age = state.day - tile["planted_day"]
                if age >= 2 and tile["yield_units"] > 0:
                    return self._move_or_act(pos, p, "HARVEST", state)
            
            need = 6 - len(state.plant_tiles("WHEAT"))
            if need > 0 and state.seeds.get("WHEAT", 0) > 0:
                empty = state.empty_unlocked_tiles()
                if empty:
                    target = min(empty, key=lambda p: manhattan_distance(p, SHED_TILES[0]))
                    return self._move_or_act(pos, target, "PLANT_WHEAT", state)
            
            return ["PASS"]
    
    def _move_or_act(self, from_pos: Tuple[int, int], target: Tuple[int, int], action: str, state: GameState) -> List[str]:
        if from_pos == target:
            if action == "PLACE_GOOSE":
                return ["PLACE", "GOOSE"]
            elif action == "PLANT_WHEAT":
                return ["PLANT", "WHEAT"]
            return [action]
        path = find_path(from_pos, target, state)
        if path and len(path) > 1:
            return self._move(from_pos, path[1])
        return ["PASS"]
    
    def _move(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> List[str]:
        dx, dy = to_pos[0] - from_pos[0], to_pos[1] - from_pos[1]
        if dx == 1: return ["EAST"]
        if dx == -1: return ["WEST"]
        if dy == 1: return ["SOUTH"]
        if dy == -1: return ["NORTH"]
        return ["PASS"]


_controller = SimpleController()

def agent(obs: Dict) -> Dict[str, Any]:
    player = obs["player"]
    
    if not hasattr(_controller, '_state'):
        _controller._state = {}
    
    if player not in _controller._state:
        _controller._state[player] = {"last_day": -1, "plan": None}
    
    pstate = _controller._state[player]
    state = GameState(obs)
    
    if state.day != pstate["last_day"]:
        pstate["last_day"] = state.day
        pstate["plan"] = Strategy().create_plan(state)
    
    return _controller.get_actions(state, pstate["plan"])