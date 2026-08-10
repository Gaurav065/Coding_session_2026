# scheduler.py
from typing import List, Dict, Tuple, Optional
from state import GameState
from planner import DailyPlan
from pathfinding import find_path, manhattan_distance
from constants import SHED_TILES, HALF, CROPS, SEED_COSTS, ANIMAL_COSTS, STRUCTURE_COSTS

class ActionScheduler:
    def __init__(self):
        self.unit_tasks: Dict[str, List[Dict]] = {}
    
    def schedule_turn(self, state: GameState, plan: DailyPlan, market_submitted: bool) -> Dict:
        actions = {"farmer": [], "hands": [], "market": []}
        
        if not market_submitted:
            actions["market"] = self._build_market_actions(state, plan)
        
        all_units = ["farmer"] + [f"hand_{i}" for i in range(len(state.hands))]
        unit_positions = {"farmer": state.farmer_pos}
        for i, pos in enumerate(state.hands):
            unit_positions[f"hand_{i}"] = pos
        
        task_queues = self._generate_task_queues(state, plan, unit_positions)
        
        for unit_id in all_units:
            if unit_id == "farmer":
                action = self._execute_next_task(state, unit_id, task_queues.get(unit_id, []), unit_positions[unit_id])
                if action:
                    actions["farmer"].append(action)
            else:
                hand_idx = int(unit_id.split("_")[1])
                action = self._execute_next_task(state, unit_id, task_queues.get(unit_id, []), unit_positions[unit_id])
                if action:
                    if len(actions["hands"]) <= hand_idx:
                        actions["hands"].extend([[] for _ in range(hand_idx + 1 - len(actions["hands"]))])
                    actions["hands"][hand_idx].append(action)
        
        return actions
    
    def _build_market_actions(self, state: GameState, plan: DailyPlan) -> List[List]:
        actions = []
        money = state.money
        
        # 1. Sell orders first (generate cash)
        sell_order = ["MELON", "STRAWBERRY", "WOOL", "MILK", "TOMATO", "EGG", "CARROT", "WHEAT", "FERTILIZER"]
        for product in sell_order:
            qty = plan.sell_schedule.get(product, 0)
            if qty > 0:
                actions.append(["SELL", product, qty])
        
        # 2. Buy land
        if plan.land_purchase and money >= {"NE": 1000, "SW": 2000, "SE": 4000}.get(plan.land_purchase, 9999):
            actions.append(["BUY_LAND"])
            money -= {"NE": 1000, "SW": 2000, "SE": 4000}.get(plan.land_purchase, 0)
        
        # 3. Hire hands
        current_hands = len(state.hands)
        hand_costs = [1, 1, 2, 3, 5, 8]
        for i in range(plan.target_hands - current_hands):
            cost_idx = current_hands + i
            if cost_idx < len(hand_costs) and money >= hand_costs[cost_idx]:
                actions.append(["HIRE"])
                money -= hand_costs[cost_idx]
        
        # 4. Buy animals
        for animal, count in plan.buy_animals.items():
            cost = ANIMAL_COSTS[animal]
            for _ in range(count):
                if money >= cost:
                    actions.append(["BUY_ANIMAL", animal, 1])
                    money -= cost
        
        # 5. Buy seeds
        for crop, count in plan.buy_seeds.items():
            cost = SEED_COSTS[crop]
            for _ in range(int(count)):
                if money >= cost:
                    actions.append(["BUY_SEED", crop, 1])
                    money -= cost
        
        return actions[:10]
    
    def _generate_task_queues(self, state: GameState, plan: DailyPlan, positions: Dict) -> Dict[str, List]:
        queues = {uid: [] for uid in positions}
        
        # Day 0: buy seeds hour 0, plant hour 1+
        if state.day == 0:
            if state.hour == 0:
                return queues
            elif state.hour == 1:
                for crop, count in plan.crop_allocation.items():
                    have_seeds = int(state.seeds.get(crop, 0))
                    planted = len(state.plant_tiles(crop))
                    needed = int(count) - planted
                    for _ in range(max(0, min(needed, have_seeds))):
                        empty = state.empty_unlocked_tiles()
                        if not empty:
                            break
                        empty.sort(key=lambda p: manhattan_distance(p, state.farmer_pos))
                        pos = empty[0]
                        queues["farmer"].append({"type": "PLANT", "pos": pos, "crop": crop, "priority": 10})
                return queues
        
        # 1. Fertilize (time-sensitive)
        for pos, crop in plan.fertilizer_use.items():
            uid = self._assign_nearest_unit(positions, pos)
            queues[uid].append({"type": "FERTILIZE", "pos": pos, "crop": crop, "priority": 10})
        
        # 2. Harvest ready (highest priority)
        for pos in state.plant_tiles():
            tile = state.get_tile(*pos)
            age = state.day - tile["planted_day"]
            params = CROPS[tile["crop"]]
            if age >= params.first_yield_day and tile["yield_units"] > 0:
                if tile["crop"] in ["TOMATO", "STRAWBERRY"] or age >= params.max_yield_day:
                    uid = self._assign_nearest_unit(positions, pos)
                    queues[uid].append({"type": "HARVEST", "pos": pos, "priority": 10})
        
        # 3. Water unwatered (CRITICAL - plants die after 2 days unwatered)
        for pos in state.plant_tiles():
            tile = state.get_tile(*pos)
            if not tile["watered_today"]:
                uid = self._assign_nearest_unit(positions, pos)
                queues[uid].append({"type": "WATER", "pos": pos, "priority": 9})
        
        # 4. Animal care
        for pos in state.animal_structures():
            tile = state.get_tile(*pos)
            animal = tile.get("animal")
            if not animal:
                continue
            
            uid = self._assign_nearest_unit(positions, pos)
            
            if not tile["fed_today"]:
                queues[uid].append({"type": "FEED", "pos": pos, "animal": animal, "priority": 8})
            
            if not tile["cared_today"]:
                queues[uid].append({"type": "CARE", "pos": pos, "priority": 7})
            
            if tile["yield_units"] > 0:
                queues[uid].append({"type": "HARVEST", "pos": pos, "priority": 6})
            
            if tile.get("fertilizer_available", False):
                queues[uid].append({"type": "COLLECT_FERTILIZER", "pos": pos, "priority": 5})
        
        # 5. Plant new crops (only if we have seeds)
        for crop, count in plan.crop_allocation.items():
            planted = len(state.plant_tiles(crop))
            have_seeds = int(state.seeds.get(crop, 0))
            needed = int(count) - planted
            for _ in range(max(0, min(needed, have_seeds))):
                empty = state.empty_unlocked_tiles()
                if not empty:
                    break
                empty.sort(key=lambda p: manhattan_distance(p, SHED_TILES[0]))
                pos = empty[0]
                uid = self._assign_nearest_unit(positions, pos)
                queues[uid].append({"type": "PLANT", "pos": pos, "crop": crop, "priority": 4})
        
        # 6. Build structures
        for struct, count in plan.structure_builds.items():
            current = len([t for t in state.animal_structures() if state.get_tile(*t).get("kind") == struct])
            for _ in range(count - current):
                empty = state.empty_unlocked_tiles()
                if not empty:
                    break
                pos = empty[0]
                uid = self._assign_nearest_unit(positions, pos)
                action_type = "BUILD_COOP" if struct == "COOP" else "BUILD_PASTURE"
                queues[uid].append({"type": action_type, "pos": pos, "priority": 3})
        
        # 7. Place animals
        for animal, count in plan.animal_allocation.items():
            for pos in state.animal_structures(animal):
                if count <= 0:
                    break
                tile = state.get_tile(*pos)
                if tile.get("animal") is None and state.shed.get(animal, 0) > 0:
                    uid = self._assign_nearest_unit(positions, pos)
                    queues[uid].append({"type": "PLACE", "pos": pos, "item": animal, "priority": 2})
                    count -= 1
        
        # 8. Clear weeds
        for pos in state.weed_tiles():
            uid = self._assign_nearest_unit(positions, pos)
            queues[uid].append({"type": "DIG", "pos": pos, "priority": 1})
        
        return queues
    
    def _assign_nearest_unit(self, positions: Dict, target: Tuple[int, int]) -> str:
        best_uid = "farmer"
        best_dist = float('inf')
        for uid, pos in positions.items():
            dist = manhattan_distance(pos, target)
            if dist < best_dist:
                best_dist = dist
                best_uid = uid
        return best_uid
    
    def _execute_next_task(self, state: GameState, unit_id: str, queue: List, pos: Tuple[int, int]) -> Optional[str]:
        if not queue:
            return "PASS"
        
        task = queue[0]
        target = task["pos"]
        
        if pos != target:
            path = find_path(pos, target, state)
            if path and len(path) > 1:
                next_pos = path[1]
                return self._move_action(pos, next_pos)
            return "PASS"
        
        queue.pop(0)
        return self._task_action(task, state)
    
    def _move_action(self, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> str:
        dx, dy = to_pos[0] - from_pos[0], to_pos[1] - from_pos[1]
        if dx == 1: return "EAST"
        if dx == -1: return "WEST"
        if dy == 1: return "SOUTH"
        if dy == -1: return "NORTH"
        return "PASS"
    
    def _task_action(self, task: Dict, state: GameState) -> str:
        t = task["type"]
        if t == "PLANT": 
            if state.seeds.get(task['crop'], 0) > 0:
                return f"PLANT {task['crop']}"
        elif t == "WATER": return "WATER"
        elif t == "HARVEST": return "HARVEST"
        elif t == "FERTILIZE": return "FERTILIZE"
        elif t == "FEED": return "FEED"
        elif t == "CARE": return "CARE"
        elif t == "COLLECT_FERTILIZER": return "COLLECT_FERTILIZER"
        elif t == "BUILD_COOP": return "BUILD_COOP"
        elif t == "BUILD_PASTURE": return "BUILD_PASTURE"
        elif t == "DIG": return "DIG"
        elif t == "PLACE": 
            if state.shed.get(task['item'], 0) > 0:
                return f"PLACE {task['item']}"
        return "PASS"