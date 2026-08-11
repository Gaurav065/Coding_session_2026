# constants.py
from dataclasses import dataclass

@dataclass
class CropParams:
    name: str
    seed_cost: int
    base_price: int
    first_yield_day: int
    max_yield_day: int
    max_yield: int
    ongoing: bool
    yield_interval: int = 0
    max_productions: int = 0

CROPS = {
    "WHEAT": CropParams("WHEAT", 10, 25, 2, 4, 6, False),
    "CARROT": CropParams("CARROT", 20, 35, 2, 3, 4, False),
    "TOMATO": CropParams("TOMATO", 50, 60, 8, 11, 4, True, 1, 4),
    "STRAWBERRY": CropParams("STRAWBERRY", 100, 120, 10, 16, 4, True, 2, 4),
    "MELON": CropParams("MELON", 80, 250, 10, 10, 6, False),
}

ANIMALS = {
    "GOOSE": {"cost": 300, "product": "EGG", "interval": 1, "feed": "WHEAT", "structure": "COOP", "max_held": 4, "structure_cost": 100},
    "COW": {"cost": 400, "product": "MILK", "interval": 2, "feed": "WHEAT", "structure": "PASTURE", "max_held": 6, "structure_cost": 100},
    "SHEEP": {"cost": 500, "product": "WOOL", "interval": 3, "feed": "WHEAT", "structure": "PASTURE", "max_held": 6, "structure_cost": 100},
}

MARKET_PARAMS = {
    "WHEAT": {"base": 25, "I0": 10000, "T": 400, "below_func": "sqrt", "below_target": 0.80, "above_func": "log", "above_target": 0.20},
    "CARROT": {"base": 35, "I0": 10000, "T": 450, "below_func": "log", "below_target": 0.20, "above_func": "sqrt", "above_target": 0.70},
    "TOMATO": {"base": 60, "I0": 10000, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "sqrt", "above_target": 0.60},
    "STRAWBERRY": {"base": 120, "I0": 10000, "T": 100, "below_func": "sqrt", "below_target": 0.70, "above_func": "linear", "above_target": 1.60},
    "MELON": {"base": 250, "I0": 10000, "T": 300, "below_func": "log", "below_target": 0.20, "above_func": "sq", "above_target": 3.60},
    "EGG": {"base": 50, "I0": 10000, "T": 332, "below_func": "linear", "below_target": 0.40, "above_func": "log", "above_target": 0.20},
    "MILK": {"base": 160, "I0": 10000, "T": 122, "below_func": "sqrt", "below_target": 0.60, "above_func": "linear", "above_target": 1.60},
    "WOOL": {"base": 200, "I0": 10000, "T": 105, "below_func": "log", "below_target": 0.20, "above_func": "sq", "above_target": 3.20},
    "FERTILIZER": {"base": 100, "I0": 10000, "T": 200, "below_func": "linear", "below_target": 0.40, "above_func": "linear", "above_target": 0.40},
}

SHOP_DEMANDS = {
    "BAKERY": ["EGG", "WHEAT"],
    "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE": ["WOOL", "WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE": ["CARROT", "CARROT"],
    "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}

QUADRANT_COSTS = {"NW": 0, "NE": 1000, "SW": 2000, "SE": 4000}
QUADRANT_ORDER = ["NE", "SW", "SE"]

BOARD_SIZE = 15
HALF = BOARD_SIZE // 2
SHED_TILES = [(HALF-1, HALF-1), (HALF, HALF-1), (HALF-1, HALF), (HALF, HALF)]

SEED_COSTS = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80}
ANIMAL_COSTS = {"GOOSE": 300, "COW": 400, "SHEEP": 500}
STRUCTURE_COSTS = {"COOP": 100, "PASTURE": 100}