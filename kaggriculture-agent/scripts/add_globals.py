import json
from kaggle_environments.envs.kaggriculture.kaggriculture import CROPS, ANIMALS, PRODUCTS

with open('continuous_agent/main_dynamic.py', 'r') as f:
    text = f.read()

# Clean up any duplicated `with open` logic inside it
import re
text = re.sub(r'with open\(.*?# Clean up', '', text, flags=re.DOTALL)

globals_str = f"""
CROPS = {json.dumps(CROPS)}
ANIMALS = {json.dumps(ANIMALS)}
PRODUCTS = {json.dumps(PRODUCTS)}
PRODUCT_ANIMAL = {{v["product"]: k for k, v in ANIMALS.items()}}
ANIMAL_PRODUCT = {{k: v["product"] for k, v in ANIMALS.items()}}
FARM_HAND_COST_MULT = 1
PRICE_FLOOR = 1
MARKET_I0 = 1000
SHOPS = {{
    "Restaurant": ["CARROT", "TOMATO", "MILK", "EGG"],
    "Bakery": ["WHEAT", "EGG", "MILK", "STRAWBERRY"],
    "Market": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"],
    "Farm Stand": ["CARROT", "STRAWBERRY", "MELON", "EGG"],
    "Textile Mill": ["WOOL"],
    "Butcher": ["EGG"],
    "Dairy": ["MILK"],
    "Greengrocer": ["TOMATO", "MELON"]
}}
ARCHETYPES = list(SHOPS.keys())
"""

idx = text.find('_CURRENT_GAP = {}')
if idx != -1:
    text = text[:idx] + globals_str + "\n" + text[idx:]
else:
    text = globals_str + "\n_CURRENT_GAP = {}\n_LAST_SHADOW_PRICE = 50.0\n_PLANNED_PLACEMENTS = {}\n" + text

with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(text)
print("ALL GLOBALS ADDED")
