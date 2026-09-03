import sys
from kaggle_environments import make

env = make("kaggriculture", configuration={"randomSeed": 42})
env.run(["C:\\Coding\\kaggriculture_architecture\\heuristic_agent6.py", "random"])

harvest_count = 0
water_count = 0
melon_sold = 0
for step in env.steps:
    hands = step[0]["action"].get("hands", [])
    for h in hands:
        if h and h[0] == "HARVEST": harvest_count += 1
        elif h and h[0] == "WATER": water_count += 1
    
    market = step[0]["action"].get("market", [])
    for m in market:
        if m and m[0] == "SELL" and m[1] == "MELON":
            melon_sold += m[2]

final_money = env.steps[-1][0]["observation"].get("farms", [])[0].get("money", 0)

print(f"Harvest count: {harvest_count}")
print(f"Water count: {water_count}")
print(f"Melon sold: {melon_sold}")
print(f"Final money: {final_money}")
