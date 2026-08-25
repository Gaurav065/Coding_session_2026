import shutil

shutil.copy(r'C:\Users\GauravPatel\.gemini\antigravity\brain\a4ab4dc5-5b88-48a4-bc75-ba3e8146c3f5\scratch\main_v2.py', 'continuous_agent/main_dynamic.py')

with open('continuous_agent/main_dynamic.py', 'r') as f:
    text = f.read()

text = text.replace('if farm["tiles"][y][x] is None:', 'if farm["tiles"][y][x] is None and (x, y) not in [(4,4), (5,4), (4,5), (5,5)]:')

old_buy = """        if item in CROPS:
            seeds_owned = obs["private"]["seeds"].get(item, 0)
            if seeds_owned < qty:
                to_buy = qty - seeds_owned
                cost = to_buy * CROPS[item]["seed_cost"]
                if money >= cost:
                    market_orders.append(["BUY_SEED", item, to_buy])
                    money -= cost
        elif item in ANIMAL_PRODUCT.values():
            animal = PRODUCT_ANIMAL[item]
            animals_owned = obs["private"]["shed"].get(animal, 0)
            if animals_owned < qty:
                to_buy = qty - animals_owned
                cost = to_buy * ANIMALS[animal]["cost"]
                if money >= cost:
                    market_orders.append(["BUY_ANIMAL", animal, to_buy])
                    money -= cost"""

new_buy = """        if item in CROPS:
            seeds_owned = obs["private"]["seeds"].get(item, 0)
            if seeds_owned < qty:
                cost_per = CROPS[item]["seed_cost"]
                to_buy = min(qty - seeds_owned, int(money // cost_per))
                if to_buy > 0:
                    market_orders.append(["BUY_SEED", item, to_buy])
                    money -= to_buy * cost_per
        elif item in ANIMAL_PRODUCT.values():
            animal = PRODUCT_ANIMAL[item]
            animals_owned = obs["private"]["shed"].get(animal, 0)
            if animals_owned < qty:
                cost_per = ANIMALS[animal]["cost"]
                to_buy = min(qty - animals_owned, int(money // cost_per))
                if to_buy > 0:
                    market_orders.append(["BUY_ANIMAL", animal, to_buy])
                    money -= to_buy * cost_per"""

text = text.replace(old_buy, new_buy)

old_task = "    all_tasks = harvests | weeds | unwatered | unfed | set(_PLANNED_PLACEMENTS.keys())"
new_task = """    valid_planned = {pos for pos, item in _PLANNED_PLACEMENTS.items() if (item in CROPS and private.get("seeds", {}).get(item, 0) > 0) or (item in ANIMALS and private.get("shed", {}).get(item, 0) > 0)}
    all_tasks = harvests | weeds | unwatered | unfed | valid_planned"""

text = text.replace(old_task, new_task)

with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(text)

print("FIX SCRIPT COMPLETE")
