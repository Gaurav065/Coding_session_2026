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

DEFAULT_PARAMS = {
    "buy_NE_thresh": 2885,
    "buy_SW_thresh": 5698,
    "buy_SE_thresh": 8873,
    "max_hands_per_quadrant": 8,
    "wheat_ratio": 0.2589,
    "cow_target": 2,
    "sheep_target": 5,
    "goose_target": 2,
    "stop_investment_day": 28
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
        
        plan.land_purchase = None
        if state.day < stop_day:
            empty = len(state.empty_unlocked_tiles())
            if empty < 15:
                if "NE" not in state.unlocked and budget > p.get("buy_NE_thresh", 1000):
                    plan.land_purchase = "NE"
                elif "SW" not in state.unlocked and budget > p.get("buy_SW_thresh", 2000) and "NE" in state.unlocked:
                    plan.land_purchase = "SW"
        
        quadrants_active = max(1, len([q for q in state.unlocked if q != "NW"]))
        desired_hands = min(6 * quadrants_active, p.get("max_hands_per_quadrant", 8) * quadrants_active)
        
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
            
        available_tiles = len(state.find_tiles(lambda t: t is None or (isinstance(t, dict) and t.get("kind") in ["PLANT", "TREE", "WEED"])))
        
        if state.day < 10:
            plan.crop_targets["WHEAT"] = min(available_tiles, 12)
            if available_tiles > 12:
                plan.crop_targets["TOMATO"] = available_tiles - 12
        else:
            cash_crops = ["TOMATO", "STRAWBERRY", "CARROT", "MELON"]
            best_crop = "TOMATO"
            best_profit = -9999
            for c in cash_crops:
                price = state.market["prices"].get(c, MARKET_PARAMS[c]["base"])
                if price < MARKET_PARAMS[c]["base"] * 0.6:
                    continue
                cost = CROPS[c].seed_cost
                days = CROPS[c].max_yield_day
                expected_days = days
                if c in ("MELON", "STRAWBERRY", "TOMATO"):
                    expected_days = max(1, days * 0.6)
                profit_velocity = (price - cost) / expected_days
                if profit_velocity > best_profit:
                    best_profit = profit_velocity
                    best_crop = c
                    
            wheat_target = int(available_tiles * p.get("wheat_ratio", 0.25))
            if state.day < stop_day:
                plan.crop_targets["WHEAT"] = min(wheat_target, available_tiles)
                plan.crop_targets[best_crop] = max(0, available_tiles - plan.crop_targets["WHEAT"])
            else:
                for c in ["WHEAT", "TOMATO", "CARROT", "STRAWBERRY", "MELON"]:
                    plan.crop_targets[c] = len(state.plant_tiles(c))
            
        if state.day < stop_day:
            plan.animal_targets["GOOSE"] = min(p.get("goose_target", 6), 4)
            if state.day >= 10:
                plan.animal_targets["COW"] = p.get("cow_target", 2)
                plan.animal_targets["SHEEP"] = p.get("sheep_target", 5)
            
            empty_coops = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP" and t.get("animal") is None)
            empty_pastures = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE" and t.get("animal") is None)
            plan.build_coops = max(0, plan.animal_targets.get("GOOSE", 0) - state.geese_count() - empty_coops)
            plan.build_pastures = max(0, plan.animal_targets.get("COW", 0) + plan.animal_targets.get("SHEEP", 0) - state.cows_count() - len(state.occupied_animal_structures("SHEEP")) - empty_pastures)
        else:
            plan.animal_targets["GOOSE"] = state.geese_count()
            plan.animal_targets["COW"] = state.cows_count()
            plan.animal_targets["SHEEP"] = len(state.occupied_animal_structures("SHEEP"))
            plan.build_coops = 0
            plan.build_pastures = 0
            
        self._calc_purchases(state, plan)
        return plan
    
    def _calc_purchases(self, state: GameState, plan: DailyPlan):
        budget = state.money
        
        if plan.land_purchase:
            budget -= QUADRANT_COSTS.get(plan.land_purchase, 15000)
        
        current_hands = len(state.hands)
        hires_needed = max(0, plan.target_hands - current_hands - state.hires_today)
        hire_costs = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765, 10946]
        for i in range(hires_needed):
            idx = current_hands + state.hires_today + i
            if idx < len(hire_costs):
                budget -= hire_costs[idx]
        
        cows = len(state.occupied_animal_structures("COW"))
        sheep = len(state.occupied_animal_structures("SHEEP"))
        geese = state.geese_count()
        need_feed = max(0, (geese + cows + sheep) * 2 - state.shed.get("WHEAT", 0))
        if need_feed > 0:
            feed_cost_per = state.market["prices"].get("WHEAT", 30)
            feed_cost = min(need_feed, budget // feed_cost_per) * feed_cost_per
            budget -= feed_cost
            plan.buy_feed_wheat = need_feed
        
        if "WHEAT" in plan.crop_targets:
            c = "WHEAT"
            t = plan.crop_targets[c]
            have = len(state.plant_tiles(c)) + state.seeds.get(c, 0)
            if have < t:
                need = t - have
                cost_per = SEED_COSTS.get(c, 10)
                affordable = min(need, max(0, budget // cost_per))
                if affordable > 0:
                    plan.buy_seeds[c] = affordable
                    budget -= affordable * cost_per
        
        for c, t in plan.crop_targets.items():
            if c == "WHEAT":
                continue
            have = len(state.plant_tiles(c)) + state.seeds.get(c, 0)
            if have < t:
                need = t - have
                cost_per = SEED_COSTS.get(c, 10)
                affordable = min(need, max(0, budget // cost_per))
                if affordable > 0:
                    plan.buy_seeds[c] = affordable
                    budget -= affordable * cost_per
        
        for animal in ["GOOSE", "COW", "SHEEP"]:
            if animal not in plan.animal_targets:
                continue
            target = plan.animal_targets[animal]
            if animal == "GOOSE":
                current = state.geese_count() + state.shed.get("GOOSE", 0)
                empty_structs = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP" and t.get("animal") is None)
            elif animal == "COW":
                current = state.cows_count() + state.shed.get("COW", 0)
                empty_structs = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE" and t.get("animal") is None)
            else:
                current = len(state.occupied_animal_structures("SHEEP")) + state.shed.get("SHEEP", 0)
                empty_structs = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE" and t.get("animal") is None)
            
            if current < target and empty_structs > 0:
                need = min(target - current, empty_structs)
                cost_per = ANIMAL_COSTS.get(animal, 100)
                affordable = min(need, max(0, budget // cost_per))
                if affordable > 0:
                    plan.buy_animals[animal] = affordable
                    budget -= affordable * cost_per
        
        if plan.build_coops > 0:
            cost = plan.build_coops * STRUCTURE_COSTS["COOP"]
            if budget >= cost:
                budget -= cost
        if plan.build_pastures > 0:
            cost = plan.build_pastures * STRUCTURE_COSTS["PASTURE"]
            if budget >= cost:
                budget -= cost

    def _create_sell_plan(self, state: GameState) -> Dict[str, int]:
        sell = {}
        for product, qty in state.shed.items():
            if qty == 0 or product == "SEEDS": continue
            if product in ["GOOSE", "COW", "SHEEP"]:
                continue
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


class SimpleController:
    def __init__(self):
        self.market = MarketPredictor()
        # carrying[agent_id] = {"item": "GOOSE", "target": (x,y), "action": "PLACE"}
        # action: "PLACE" | "DROP" | None - what to do when at target
        self.carrying = {}
        
    def get_actions(self, state: GameState, plan: DailyPlan) -> Dict:
        self.market.update(state.obs["market"])
        
        if state.hour == 0:
            self.carrying = {}
        
        actions = {"farmer": ["PASS"], "hands": [], "market": []}
        money = state.money
        
        if state.hour == 0:
            sell = self._create_sell_plan(state)
            for p, q in sell.items(): 
                actions["market"].append(["SELL", p, q])
            
            if plan.land_purchase:
                actions["market"].append(["BUY_LAND"])
            
            geese = state.geese_count()
            cows = len(state.occupied_animal_structures("COW"))
            sheep = len(state.occupied_animal_structures("SHEEP"))
            need_feed = max(0, (geese + cows + sheep) * 2 - state.shed.get("WHEAT", 0))
            if need_feed > 0 and money >= state.market["prices"].get("WHEAT", 30) and len(actions["market"]) < 10:
                cost_per = state.market["prices"].get("WHEAT", 30)
                affordable_feed = int(min(need_feed, money // cost_per))
                if affordable_feed > 0:
                    actions["market"].append(["BUY_PRODUCT", "WHEAT", affordable_feed])
                    money -= affordable_feed * cost_per
            
            if "WHEAT" in plan.buy_seeds and plan.buy_seeds["WHEAT"] > 0 and money >= SEED_COSTS.get("WHEAT", 10) and len(actions["market"]) < 10:
                target_qty = plan.buy_seeds["WHEAT"]
                affordable = int(min(target_qty, money // SEED_COSTS.get("WHEAT", 10)))
                if affordable > 0:
                    actions["market"].append(["BUY_SEED", "WHEAT", affordable])
                    money -= affordable * SEED_COSTS.get("WHEAT", 10)
            
            for animal in ["GOOSE", "COW", "SHEEP"]:
                if animal in plan.buy_animals and plan.buy_animals[animal] > 0 and money >= ANIMAL_COSTS.get(animal, 100) and len(actions["market"]) < 10:
                    target_qty = plan.buy_animals[animal]
                    affordable = int(min(target_qty, money // ANIMAL_COSTS.get(animal, 100)))
                    if affordable > 0:
                        actions["market"].append(["BUY_ANIMAL", animal, affordable])
                        money -= affordable * ANIMAL_COSTS.get(animal, 100)
            
            for crop, target_qty in plan.buy_seeds.items():
                if crop == "WHEAT":
                    continue
                if target_qty > 0 and money >= SEED_COSTS.get(crop, 10) and len(actions["market"]) < 10:
                    affordable = int(min(target_qty, money // SEED_COSTS.get(crop, 10)))
                    if affordable > 0:
                        actions["market"].append(["BUY_SEED", crop, affordable])
                        money -= affordable * SEED_COSTS.get(crop, 10)
            
            costs = [1, 1]
            for _ in range(18):
                costs.append(costs[-1] + costs[-2])
            
            current = len(state.hands)
            for i in range(plan.target_hands - current):
                idx = current + i
                if len(actions["market"]) >= 9: break
                if idx < len(costs) and money >= costs[idx]:
                    actions["market"].append(["HIRE"])
                    money -= costs[idx]
        
        actions["market"] = actions["market"][:10]
        
        actions["farmer"] = self._get_farmer_action(state, plan, "FARMER", state.farmer_pos, state.inventories[0])
        
        if len(state.hands) > 0:
            actions["hands"].append(self._get_hand0_action(state, plan, "HAND_0", state.hands[0], state.inventories[1]))
        
        for i in range(1, len(state.hands)):
            actions["hands"].append(self._get_wheat_hand_action(i, state, plan, f"HAND_{i}", state.hands[i], state.inventories[i + 1]))
            
        return actions
    
    def _create_sell_plan(self, state: GameState) -> Dict[str, int]:
        sell = {}
        for product, qty in state.shed.items():
            if qty == 0 or product == "SEEDS": continue
            if product in ["GOOSE", "COW", "SHEEP"]:
                continue
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
    
    def _get_farmer_action(self, state: GameState, plan: DailyPlan, agent_id: str, pos: Tuple[int, int], inv: Dict) -> List[str]:
        shed_target = min(SHED_TILES, key=lambda p: manhattan_distance(pos, p))
        
        if agent_id not in self.carrying:
            self.carrying[agent_id] = {"item": None, "target": None, "action": None}
        carry = self.carrying[agent_id]
        
        # Clear carry after successful action
        if carry["action"] == "PLACE" and pos == carry["target"]:
            carry["item"] = None
            carry["target"] = None
            carry["action"] = None
        if carry["action"] == "DROP" and pos == shed_target and inv.get(carry["item"], 0) > 0:
            carry["item"] = None
            carry["target"] = None
            carry["action"] = None
        
        # 1. Build coops
        if plan.build_coops > 0 and state.money >= 100:
            empty = state.empty_unlocked_tiles()
            if empty:
                target = min(empty, key=lambda p: manhattan_distance(p, SHED_TILES[0]))
                if pos == target:
                    return ["BUILD_COOP"]
                path = find_path(pos, target, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        # 2. Build pastures
        if plan.build_pastures > 0 and state.money >= 100:
            empty = state.empty_unlocked_tiles()
            if empty:
                target = min(empty, key=lambda p: manhattan_distance(p, SHED_TILES[0]))
                if pos == target:
                    return ["BUILD_PASTURE"]
                path = find_path(pos, target, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        # 3. Get wheat for feeding
        if inv.get("WHEAT", 0) == 0 and state.shed.get("WHEAT", 0) > 0 and carry["item"] is None:
            if pos == shed_target:
                carry["item"] = "WHEAT"
                carry["target"] = shed_target
                carry["action"] = "DROP"
                return ["PICKUP", "WHEAT", "10"]
            path = find_path(pos, shed_target, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        # 4. Feed animals (geese first)
        for p in state.occupied_animal_structures("GOOSE"):
            tile = state.get_tile(*p)
            if tile and not tile.get("fed_today", False):
                if pos == p and (inv.get("WHEAT", 0) > 0 or carry["item"] == "WHEAT"):
                    return ["FEED"]
                path = find_path(pos, p, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        for p in state.animals_needing_feed():
            if pos == p and (inv.get("WHEAT", 0) > 0 or carry["item"] == "WHEAT"):
                return ["FEED"]
            path = find_path(pos, p, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        # 5. Care animals
        for p in state.animals_needing_care():
            if pos == p:
                return ["CARE"]
            path = find_path(pos, p, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        # 6. Harvest animals
        for p in state.animals_ready_to_harvest():
            if pos == p:
                return ["HARVEST"]
            path = find_path(pos, p, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        # 7. Drop at shed
        for item in ["EGG", "WHEAT", "MILK", "WOOL"]:
            threshold = 4 if item in ["EGG", "MILK", "WOOL"] else 10
            if inv.get(item, 0) >= threshold:
                if pos == shed_target:
                    return ["DROP"]
                if carry["item"] is None:
                    carry["item"] = item
                    carry["target"] = shed_target
                    carry["action"] = "DROP"
                path = find_path(pos, shed_target, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        # 8. Water crops
        for p in state.crops_needing_water():
            if pos == p:
                return ["WATER"]
            path = find_path(pos, p, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        # 9. Fertilize
        for p in state.crops_needing_fertilizer():
            if pos == p and inv.get("FERTILIZER", 0) > 0:
                return ["FERTILIZE"]
            if pos == p and inv.get("FERTILIZER", 0) == 0 and state.shed.get("FERTILIZER", 0) > 0:
                path = find_path(pos, shed_target, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
            path = find_path(pos, p, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        # 10. Harvest crops
        for p in state.crops_ready_to_harvest():
            if pos == p:
                return ["HARVEST"]
            path = find_path(pos, p, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        # 11. Plant WHEAT first
        if "WHEAT" in plan.crop_targets:
            crop = "WHEAT"
            target = plan.crop_targets[crop]
            planted = len(state.plant_tiles(crop))
            need = min(target - planted, state.seeds.get(crop, 0))
            if need > 0:
                empty = state.empty_unlocked_tiles()
                for p in empty[:need]:
                    if pos == p:
                        return ["PLANT", crop]
                    path = find_path(pos, p, state)
                    if path and len(path) > 1:
                        return self._move(pos, path[1])
        
        for crop, target in plan.crop_targets.items():
            if crop == "WHEAT":
                continue
            planted = len(state.plant_tiles(crop))
            need = min(target - planted, state.seeds.get(crop, 0))
            if need > 0:
                empty = state.empty_unlocked_tiles()
                for p in empty[:need]:
                    if pos == p:
                        return ["PLANT", crop]
                    path = find_path(pos, p, state)
                    if path and len(path) > 1:
                        return self._move(pos, path[1])
        
        # 12. Dig weeds
        for p in state.weed_tiles():
            if pos == p:
                return ["DIG"]
            path = find_path(pos, p, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        return ["PASS"]
    
    def _get_hand0_action(self, state: GameState, plan: DailyPlan, agent_id: str, pos: Tuple[int, int], inv: Dict) -> List[str]:
        """Hand 0: Goose specialist - PLACE GEESE, feed, care, harvest eggs"""
        shed_target = min(SHED_TILES, key=lambda p: manhattan_distance(pos, p))
        
        if agent_id not in self.carrying:
            self.carrying[agent_id] = {"item": None, "target": None, "action": None}
        carry = self.carrying[agent_id]
        
        # Clear carry AFTER successful PLACE
        if carry["action"] == "PLACE" and pos == carry["target"]:
            carry["item"] = None
            carry["target"] = None
            carry["action"] = None
        
        if carry["action"] == "DROP" and pos == shed_target and inv.get("WHEAT", 0) > 0:
            carry["item"] = None
            carry["target"] = None
            carry["action"] = None
        
        # 1. PLACE GEESE FROM SHED - HIGHEST PRIORITY
        if state.shed.get("GOOSE", 0) > 0:
            empty_coops = state.empty_structures("COOP")
            if empty_coops:
                target = empty_coops[0]
                
                # If AT coop with goose -> PLACE (check this FIRST before clearing carry)
                if pos == target and (carry["item"] == "GOOSE" or inv.get("GOOSE", 0) > 0):
                    carry["item"] = None
                    carry["target"] = None
                    carry["action"] = None
                    return ["PLACE", "GOOSE"]
                
                # If carrying goose -> move to coop
                if carry["item"] == "GOOSE" and carry["action"] == "PLACE":
                    path = find_path(pos, target, state)
                    if path and len(path) > 1:
                        return self._move(pos, path[1])
                
                # If at shed and not carrying -> pick up
                if pos == shed_target and carry["item"] is None:
                    carry["item"] = "GOOSE"
                    carry["target"] = target
                    carry["action"] = "PLACE"
                    return ["PICKUP", "GOOSE", "1"]
                
                # If we have goose in inventory -> move to coop
                if inv.get("GOOSE", 0) > 0 and carry["item"] is None:
                    carry["item"] = "GOOSE"
                    carry["target"] = target
                    carry["action"] = "PLACE"
                    path = find_path(pos, target, state)
                    if path and len(path) > 1:
                        return self._move(pos, path[1])
                
                # Otherwise move to shed
                path = find_path(pos, shed_target, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        # 2. Feed geese
        for p in state.occupied_animal_structures("GOOSE"):
            tile = state.get_tile(*p)
            if tile and not tile.get("fed_today", False):
                if pos == p and (inv.get("WHEAT", 0) > 0 or carry["item"] == "WHEAT"):
                    return ["FEED"]
                if pos == p and inv.get("WHEAT", 0) == 0 and carry["item"] != "WHEAT":
                    if pos == shed_target and state.shed.get("WHEAT", 0) > 0:
                        carry["item"] = "WHEAT"
                        carry["target"] = shed_target
                        carry["action"] = "DROP"
                        return ["PICKUP", "WHEAT", "10"]
                    path = find_path(pos, shed_target, state)
                    if path and len(path) > 1:
                        return self._move(pos, path[1])
                path = find_path(pos, p, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        # 3. Care geese
        for p in state.occupied_animal_structures("GOOSE"):
            tile = state.get_tile(*p)
            if tile and not tile.get("cared_today", False):
                if pos == p:
                    return ["CARE"]
                path = find_path(pos, p, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        # 4. Harvest eggs
        for p in state.occupied_animal_structures("GOOSE"):
            tile = state.get_tile(*p)
            if tile and tile.get("yield_units", 0) > 0:
                if pos == p:
                    return ["HARVEST"]
                path = find_path(pos, p, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        # 5. Drop eggs at shed
        if inv.get("EGG", 0) >= 4:
            if pos == shed_target:
                return ["DROP"]
            if carry["item"] is None:
                carry["item"] = "EGG"
                carry["target"] = shed_target
                carry["action"] = "DROP"
            path = find_path(pos, shed_target, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        # 6. Get wheat for feeding
        if inv.get("WHEAT", 0) == 0 and state.shed.get("WHEAT", 0) > 0 and carry["item"] is None:
            if pos == shed_target:
                carry["item"] = "WHEAT"
                carry["target"] = shed_target
                carry["action"] = "DROP"
                return ["PICKUP", "WHEAT", "10"]
            path = find_path(pos, shed_target, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        return ["PASS"]
    
    def _get_wheat_hand_action(self, hand_idx: int, state: GameState, plan: DailyPlan, agent_id: str, pos: Tuple[int, int], inv: Dict) -> List[str]:
        """Hand 1+: Wheat cycle - plant, water, harvest, DROP AT SHED"""
        shed_target = min(SHED_TILES, key=lambda p: manhattan_distance(pos, p))
        
        if agent_id not in self.carrying:
            self.carrying[agent_id] = {"item": None, "target": None, "action": None}
        carry = self.carrying[agent_id]
        
        if carry["action"] == "DROP" and pos == shed_target and inv.get("WHEAT", 0) > 0:
            carry["item"] = None
            carry["target"] = None
            carry["action"] = None
        
        # 1. DROP wheat at shed - ABSOLUTE HIGHEST PRIORITY
        if inv.get("WHEAT", 0) > 0:
            if pos == shed_target:
                return ["DROP"]
            if carry["item"] is None:
                carry["item"] = "WHEAT"
                carry["target"] = shed_target
                carry["action"] = "DROP"
            path = find_path(pos, shed_target, state)
            if path and len(path) > 1:
                return self._move(pos, path[1])
        
        # 2. Water wheat
        for p in state.plant_tiles("WHEAT"):
            tile = state.get_tile(*p)
            if tile and not tile.get("watered_today", False):
                if pos == p:
                    return ["WATER"]
                path = find_path(pos, p, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        # 3. Harvest wheat
        for p in state.plant_tiles("WHEAT"):
            tile = state.get_tile(*p)
            if tile and tile.get("yield_units", 0) > 0:
                if pos == p:
                    return ["HARVEST"]
                path = find_path(pos, p, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        # 4. Plant wheat
        wheat_target = plan.crop_targets.get("WHEAT", 0)
        planted = len(state.plant_tiles("WHEAT"))
        need = min(wheat_target - planted, state.seeds.get("WHEAT", 0))
        if need > 0:
            empty = state.empty_unlocked_tiles()
            for p in empty[:need]:
                if pos == p:
                    return ["PLANT", "WHEAT"]
                path = find_path(pos, p, state)
                if path and len(path) > 1:
                    return self._move(pos, path[1])
        
        # 5. Help other crops
        for crop in ["TOMATO", "STRAWBERRY", "CARROT", "MELON"]:
            target = plan.crop_targets.get(crop, 0)
            planted = len(state.plant_tiles(crop))
            need = min(target - planted, state.seeds.get(crop, 0))
            if need > 0:
                empty = state.empty_unlocked_tiles()
                for p in empty[:need]:
                    if pos == p:
                        return ["PLANT", crop]
                    path = find_path(pos, p, state)
                    if path and len(path) > 1:
                        return self._move(pos, path[1])
        
        # 6. Water other crops
        for p in state.crops_needing_water():
            tile = state.get_tile(*p)
            if tile and tile.get("crop") != "WHEAT":
                if pos == p:
                    return ["WATER"]
                path = find_path(pos, p, state)
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


_controller = SimpleController()

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