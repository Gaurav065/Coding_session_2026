# planner.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from constants import CROPS, ANIMALS, QUADRANT_COSTS, QUADRANT_ORDER, SHED_TILES, MARKET_PARAMS, SEED_COSTS, ANIMAL_COSTS, STRUCTURE_COSTS
from state import GameState
from market import MarketPredictor

@dataclass
class DailyPlan:
    land_purchase: Optional[str] = None
    target_hands: int = 0
    crop_allocation: Dict[str, int] = field(default_factory=dict)
    animal_allocation: Dict[str, int] = field(default_factory=dict)
    structure_builds: Dict[str, int] = field(default_factory=dict)
    sell_schedule: Dict[str, int] = field(default_factory=dict)
    buy_seeds: Dict[str, int] = field(default_factory=dict)
    buy_animals: Dict[str, int] = field(default_factory=dict)
    fertilizer_use: Dict[Tuple[int, int], str] = field(default_factory=dict)

class StrategicPlanner:
    def __init__(self):
        self.market = MarketPredictor()
        self.last_plan: Optional[DailyPlan] = None
    
    def create_plan(self, state: GameState) -> DailyPlan:
        self.market.update(state.obs["market"])
        plan = DailyPlan()
        
        days_left = state.days_remaining()
        
        # For short games (< 10 days), only wheat makes sense
        if days_left <= 10:
            return self._wheat_only_plan(state, days_left)
        
        # Budget-aware planning
        budget = state.money
        
        # 1. Sell first to raise cash
        plan.sell_schedule = self._create_sell_schedule(state)
        estimated_sell_revenue = sum(
            qty * state.market["prices"].get(prod, 1) 
            for prod, qty in plan.sell_schedule.items()
        )
        budget += estimated_sell_revenue
        
        # 2. Land purchase
        plan.land_purchase = self._decide_land_purchase(state, budget)
        if plan.land_purchase:
            budget -= QUADRANT_COSTS[plan.land_purchase]
        
        # 3. Hand hiring
        plan.target_hands = self._optimal_hand_count(state)
        hand_cost = sum([1, 1, 2, 3, 5, 8][:max(0, plan.target_hands - len(state.hands))])
        budget -= hand_cost
        
        # 4. Resource allocation
        plan.crop_allocation, plan.animal_allocation, plan.structure_builds = \
            self._allocate_resources(state, len(state.empty_unlocked_tiles()), budget, days_left)
        
        struct_cost = sum(STRUCTURE_COSTS[s] * c for s, c in plan.structure_builds.items())
        budget -= struct_cost
        
        # 5. Animal purchases
        plan.buy_animals = self._calculate_animal_needs(state, plan)
        animal_cost = sum(ANIMAL_COSTS[a] * c for a, c in plan.buy_animals.items())
        budget -= animal_cost
        
        # 6. Seed purchases
        plan.buy_seeds = self._calculate_seed_needs(state, plan)
        seed_cost = sum(SEED_COSTS[c] * q for c, q in plan.buy_seeds.items())
        budget -= seed_cost
        
        # 7. Fertilizer
        plan.fertilizer_use = self._allocate_fertilizer(state, plan)
        
        self.last_plan = plan
        return plan
    
    def _wheat_only_plan(self, state: GameState, days_left: int) -> DailyPlan:
        """Simple wheat loop for endgame or short games."""
        plan = DailyPlan()
        tiles = len(state.empty_unlocked_tiles())
        # Wheat cycle: 2 days to first harvest, 4 days to max. Plant continuously.
        plan.crop_allocation = {"WHEAT": min(tiles, 20)}
        plan.buy_seeds = {"WHEAT": max(0, plan.crop_allocation["WHEAT"] - len(state.plant_tiles("WHEAT")) - state.seeds.get("WHEAT", 0))}
        plan.sell_schedule = self._create_sell_schedule(state)
        plan.target_hands = min(2, max(0, (plan.crop_allocation["WHEAT"] // 10) - 1))
        return plan
    
    def _decide_land_purchase(self, state: GameState, budget: int) -> Optional[str]:
        for quad in QUADRANT_ORDER:
            if quad not in state.unlocked:
                cost = QUADRANT_COSTS[quad]
                if budget >= cost and (quad == "NE" or "NE" in state.unlocked):
                    return quad
        return None
    
    def _optimal_hand_count(self, state: GameState) -> int:
        plants_needing_care = len(state.plant_tiles()) + len([
            t for t in state.animal_structures() 
            if state.get_tile(*t).get("animal") is not None
        ])
        needed = max(0, (plants_needing_care // 10) - 1)
        return min(needed, 2)
    
    def _allocate_resources(self, state: GameState, tiles: int, budget: int, days_left: int) -> Tuple[Dict, Dict, Dict]:
        crops = {}
        animals = {}
        structures = {}
        
        if days_left <= 15:
            crops["WHEAT"] = min(tiles, budget // 10)
            return crops, animals, structures
        
        # Conservative animal investment
        if days_left > 20 and budget > 800:
            max_animals = min(tiles // 5, 3)
            animals["GOOSE"] = min(max_animals, 2)
            structures["COOP"] = animals.get("GOOSE", 0)
        
        remaining = tiles - sum(animals.values()) - sum(structures.values())
        
        # Crop allocation
        if days_left > 25 and budget > 400:
            crops["MELON"] = min(remaining // 4, 3, budget // 80)
            crops["TOMATO"] = min(remaining - crops["MELON"], 4, max(0, (budget - crops["MELON"]*80) // 50))
            crops["WHEAT"] = remaining - crops["MELON"] - crops["TOMATO"]
        elif days_left > 15 and budget > 200:
            crops["TOMATO"] = min(remaining // 2, 6, budget // 50)
            crops["WHEAT"] = remaining - crops["TOMATO"]
        else:
            crops["WHEAT"] = min(remaining, budget // 10)
        
        return crops, animals, structures
    
    def _create_sell_schedule(self, state: GameState) -> Dict[str, int]:
        schedule = {}
        town_rates = self.market.get_town_consumption_rate(state.town)
        
        for product, qty in state.shed.items():
            if qty == 0 or product == "SEEDS":
                continue
            
            current_price = state.market["prices"].get(product, 1)
            
            if current_price <= 1 and town_rates.get(product, 0) > 0:
                continue
            
            if product in ["MELON", "STRAWBERRY", "MILK", "WOOL"]:
                opt_qty, _ = self.market.optimal_sell_batch(product, qty, state.market["inventory"].get(product, 10000))
                if opt_qty > 0:
                    schedule[product] = opt_qty
            else:
                buffer = 10 if product == "WHEAT" else 5
                if qty > buffer:
                    schedule[product] = qty - buffer
        
        return schedule
    
    def _calculate_seed_needs(self, state: GameState, plan: DailyPlan) -> Dict[str, int]:
        needs = {}
        for crop, count in plan.crop_allocation.items():
            have = state.seeds.get(crop, 0)
            planted = len(state.plant_tiles(crop))
            total_have = have + planted
            if total_have < count:
                needs[crop] = count - total_have
        return needs
    
    def _calculate_animal_needs(self, state: GameState, plan: DailyPlan) -> Dict[str, int]:
        needs = {}
        for animal, count in plan.animal_allocation.items():
            in_shed = state.shed.get(animal, 0)
            on_farm = sum(1 for pos in state.animal_structures(animal) 
                         if state.get_tile(*pos).get("animal") == animal)
            have = in_shed + on_farm
            if have < count:
                needs[animal] = count - have
        return needs
    
    def _allocate_fertilizer(self, state: GameState, plan: DailyPlan) -> Dict[Tuple[int, int], str]:
        fert = state.shed.get("FERTILIZER", 0)
        if fert == 0:
            return {}
        
        targets = {}
        priority_crops = ["MELON", "TOMATO", "STRAWBERRY", "WHEAT", "CARROT"]
        
        for crop in priority_crops:
            if fert == 0:
                break
            for pos in state.plant_tiles(crop):
                if fert == 0:
                    break
                tile = state.get_tile(*pos)
                if tile.get("fertilized_until_day", -1) < state.day:
                    age = state.day - tile["planted_day"]
                    params = CROPS[crop]
                    bonus_start = (params.max_yield_day + 1) // 2
                    if bonus_start <= age <= params.max_yield_day:
                        targets[pos] = crop
                        fert -= 1
        
        return targets