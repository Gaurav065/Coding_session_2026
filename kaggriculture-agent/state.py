# state.py
from typing import Dict, List, Tuple, Any
from constants import CROPS, ANIMALS, SHED_TILES, HALF, BOARD_SIZE

class GameState:
    def __init__(self, obs: Dict):
        self.obs = obs
        self.player = obs["player"]
        self.day = obs["day"]
        self.hour = obs["hour"]
        self.step = self.day * 24 + self.hour
        
        self.me = obs["farms"][self.player]
        self.opp = obs["farms"][1 - self.player]
        self.market = obs["market"]
        self.town = obs["town"]
        self.private = obs["private"]
        
        self.money = self.me["money"]
        self.tiles = self.me["tiles"]
        self.farmer_pos = tuple(self.me["farmer"])
        self.hands = [tuple(h) for h in self.me["hands"]]
        self.unlocked = set(self.me["unlocked_quadrants"])
        self.hires_today = self.me["hires_today"]
        
        self.shed = self.private["shed"]
        self.seeds = self.private["seeds"]
        self.inventories = [inv for inv in self.private["inventories"]]
        
    def get_tile(self, x: int, y: int):
        if 0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE:
            return self.tiles[y][x]
        return "LOCKED"
    
    def is_unlocked(self, x: int, y: int) -> bool:
        quad = self._get_quadrant(x, y)
        return quad in self.unlocked
    
    def _get_quadrant(self, x: int, y: int) -> str:
        if x < HALF and y < HALF: return "NW"
        if x >= HALF and y < HALF: return "NE"
        if x < HALF and y >= HALF: return "SW"
        return "SE"
    
    def find_tiles(self, predicate) -> List[Tuple[int, int]]:
        results = []
        for y in range(BOARD_SIZE):
            for x in range(BOARD_SIZE):
                tile = self.get_tile(x, y)
                if predicate(tile):
                    results.append((x, y))
        return results
    
    def empty_unlocked_tiles(self) -> List[Tuple[int, int]]:
        return self.find_tiles(lambda t: t is None)
    
    def plant_tiles(self, crop: str = None) -> List[Tuple[int, int]]:
        def pred(t):
            if not isinstance(t, dict) or t.get("kind") != "PLANT":
                return False
            if crop and t.get("crop") != crop:
                return False
            return True
        return self.find_tiles(pred)
    
    def animal_structures(self, animal_type: str = None) -> List[Tuple[int, int]]:
        def pred(t):
            if not isinstance(t, dict) or t.get("kind") not in ("COOP", "PASTURE"):
                return False
            if animal_type:
                expected = "COOP" if animal_type == "GOOSE" else "PASTURE"
                if t.get("kind") != expected:
                    return False
                if t.get("animal") is not None:
                    return False
            return True
        return self.find_tiles(pred)
    
    def occupied_animal_structures(self, animal_type: str = None) -> List[Tuple[int, int]]:
        def pred(t):
            if not isinstance(t, dict) or t.get("kind") not in ("COOP", "PASTURE"):
                return False
            if animal_type:
                expected = "COOP" if animal_type == "GOOSE" else "PASTURE"
                if t.get("kind") != expected:
                    return False
                if t.get("animal") != animal_type:
                    return False
            elif t.get("animal") is None:
                return False
            return True
        return self.find_tiles(pred)
    
    def weed_tiles(self) -> List[Tuple[int, int]]:
        return self.find_tiles(lambda t: isinstance(t, dict) and t.get("kind") == "WEED")
    
    def total_shed_items(self) -> int:
        return sum(v for k, v in self.shed.items() if k != "SEEDS")
    
    def can_hold_in_shed(self, n: int = 1) -> bool:
        return self.total_shed_items() + n <= 100
    
    def days_remaining(self) -> int:
        return 30 - self.day
    
    def turns_remaining_today(self) -> int:
        return 24 - self.hour
    
    def wheat_ready_to_harvest(self) -> List[Tuple[int, int]]:
        """Wheat tiles ready for harvest (age >= 2, yield > 0)."""
        res = []
        for pos in self.plant_tiles("WHEAT"):
            tile = self.get_tile(*pos)
            age = self.day - tile["planted_day"]
            if age >= 2 and tile["yield_units"] > 0:
                res.append(pos)
        return res
    
    def wheat_needing_water(self) -> List[Tuple[int, int]]:
        """Wheat tiles not watered today."""
        res = []
        for pos in self.plant_tiles("WHEAT"):
            tile = self.get_tile(*pos)
            if not tile["watered_today"]:
                res.append(pos)
        return res
    
    def tomato_ready_to_harvest(self) -> List[Tuple[int, int]]:
        res = []
        for pos in self.plant_tiles("TOMATO"):
            tile = self.get_tile(*pos)
            if tile["yield_units"] > 0:
                res.append(pos)
        return res
    
    def tomato_needing_water(self) -> List[Tuple[int, int]]:
        res = []
        for pos in self.plant_tiles("TOMATO"):
            tile = self.get_tile(*pos)
            if not tile["watered_today"]:
                res.append(pos)
        return res
    
    def animals_needing_feed(self) -> List[Tuple[int, int]]:
        res = []
        for pos in self.occupied_animal_structures():
            tile = self.get_tile(*pos)
            if not tile["fed_today"]:
                res.append(pos)
        return res
    
    def animals_needing_care(self) -> List[Tuple[int, int]]:
        res = []
        for pos in self.occupied_animal_structures():
            tile = self.get_tile(*pos)
            if not tile["cared_today"]:
                res.append(pos)
        return res
    
    def animals_ready_to_harvest(self) -> List[Tuple[int, int]]:
        res = []
        for pos in self.occupied_animal_structures():
            tile = self.get_tile(*pos)
            if tile["yield_units"] > 0:
                res.append(pos)
        return res
    
    def animals_with_fertilizer(self) -> List[Tuple[int, int]]:
        res = []
        for pos in self.occupied_animal_structures():
            tile = self.get_tile(*pos)
            if tile.get("fertilizer_available", False):
                res.append(pos)
        return res
    
    def geese_count(self) -> int:
        return len(self.occupied_animal_structures("GOOSE"))
    
    def cows_count(self) -> int:
        return len(self.occupied_animal_structures("COW"))
    
    def empty_structures(self, struct_type: str) -> List[Tuple[int, int]]:
        """Empty coops or pastures ready for animals."""
        res = []
        for pos in self.animal_structures():
            tile = self.get_tile(*pos)
            if tile.get("kind") == struct_type and tile.get("animal") is None:
                res.append(pos)
        return res