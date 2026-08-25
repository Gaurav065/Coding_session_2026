ANIMALS = {
    "GOOSE": {"cost": 100, "product": "EGG"},
    "SHEEP": {"cost": 400, "product": "WOOL"},
    "COW": {"cost": 500, "product": "MILK"}
}
PRODUCT_ANIMAL = {v["product"]: k for k, v in ANIMALS.items()}
ANIMAL_PRODUCT = {k: v["product"] for k, v in ANIMALS.items()}

FARM_HAND_COST_MULT = 1
PRICE_FLOOR = 1
MARKET_I0 = 1000

SHOPS = {
    "Restaurant": ["CARROT", "TOMATO", "MILK", "EGG"],
    "Bakery": ["WHEAT", "EGG", "MILK", "STRAWBERRY"],
    "Market": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"],
    "Farm Stand": ["CARROT", "STRAWBERRY", "MELON", "EGG"],
    "Textile Mill": ["WOOL"],
    "Butcher": ["EGG"],
    "Dairy": ["MILK"],
    "Greengrocer": ["TOMATO", "MELON"]
}
ARCHETYPES = list(SHOPS.keys())

with open('continuous_agent/main_dynamic.py', 'r') as f:
    text = f.read()

import re
idx = text.find('_CURRENT_GAP = {}')
if idx != -1:
    text = text[:idx] + "\n" + open('add_animals.py', 'r').read() + "\n" + text[idx:]

with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(text)
print("ANIMALS AND CONSTANTS ADDED")
