import os
import json
from collections import defaultdict

def deep_analyze_replay(rf_path):
    print(f"\n=======================================================")
    print(f"ANALYZING: {os.path.basename(rf_path)}")
    print(f"=======================================================")
    
    with open(rf_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    steps = data.get("steps", [])
    print(f"Total steps: {len(steps)}")
    final = steps[-1]
    print(f"Final Rewards: P0 = {final[0].get('reward')}, P1 = {final[1].get('reward')}")
    
    # Track actions taken by each player across the match:
    # 1. Seeds bought (by type)
    # 2. Animals bought (by type)
    # 3. Products bought/sold (by type, amount, turn)
    # 4. Hires per day
    # 5. Land bought
    # 6. Crops planted
    
    market_ops = [defaultdict(int), defaultdict(int)]
    sells_by_turn = [defaultdict(int), defaultdict(int)] # turn -> total items sold
    sells_by_product = [defaultdict(int), defaultdict(int)]
    buys_by_product = [defaultdict(int), defaultdict(int)]
    seeds_bought = [defaultdict(int), defaultdict(int)]
    animals_bought = [defaultdict(int), defaultdict(int)]
    hires_per_day = [defaultdict(int), defaultdict(int)]
    land_bought_turns = [[], []]
    
    # Check shop unlocks
    unlocked_shops_timeline = []
    
    for t, step in enumerate(steps):
        for p in [0, 1]:
            action = step[p].get("action")
            if not action or not isinstance(action, dict):
                continue
            
            # Market actions
            m_orders = action.get("market", [])
            for order in m_orders:
                if not order:
                    continue
                op = order[0]
                market_ops[p][op] += 1
                
                if op == "BUY_SEED":
                    seeds_bought[p][order[1]] += (order[2] if len(order) > 2 else 1)
                elif op == "BUY_ANIMAL":
                    animals_bought[p][order[1]] += (order[2] if len(order) > 2 else 1)
                elif op == "BUY_PRODUCT":
                    buys_by_product[p][order[1]] += (order[2] if len(order) > 2 else 1)
                elif op == "SELL":
                    item = order[1]
                    qty = order[2] if len(order) > 2 else 1
                    sells_by_turn[p][t] += qty
                    sells_by_product[p][item] += qty
                elif op == "HIRE":
                    day = t // 24
                    hires_per_day[p][day] += 1
                elif op == "BUY_LAND":
                    land_bought_turns[p].append(t)
                    
        # Check town shops in obs
        obs0 = step[0].get("observation", {})
        town = obs0.get("town", {})
        shops = town.get("unlocked_shops", [])
        if len(shops) > len(unlocked_shops_timeline):
            unlocked_shops_timeline = list(shops)
            print(f"Turn {t} (Day {t//24}): New Shop Unlocked -> {shops}")

    print("\n--- LAND PURCHASE TIMINGS ---")
    print(f"P0 Land Turns: {land_bought_turns[0]} (Days {[t//24 for t in land_bought_turns[0]]})")
    print(f"P1 Land Turns: {land_bought_turns[1]} (Days {[t//24 for t in land_bought_turns[1]]})")

    print("\n--- SEEDS BOUGHT ---")
    print(f"P0 Seeds: {dict(seeds_bought[0])}")
    print(f"P1 Seeds: {dict(seeds_bought[1])}")

    print("\n--- ANIMALS BOUGHT ---")
    print(f"P0 Animals: {dict(animals_bought[0])}")
    print(f"P1 Animals: {dict(animals_bought[1])}")

    print("\n--- PRODUCTS BOUGHT (Buy Product) ---")
    print(f"P0 Buys: {dict(buys_by_product[0])}")
    print(f"P1 Buys: {dict(buys_by_product[1])}")

    print("\n--- PRODUCTS SOLD (Total Lifetime) ---")
    print(f"P0 Sells: {dict(sells_by_product[0])}")
    print(f"P1 Sells: {dict(sells_by_product[1])}")

    print("\n--- HIRES PROFILE (Days 0 to 5) ---")
    print(f"P0 Early Hires (D0-D5): {[hires_per_day[0][d] for d in range(6)]}")
    print(f"P1 Early Hires (D0-D5): {[hires_per_day[1][d] for d in range(6)]}")
    print(f"P0 Max Hires in a single day: {max(hires_per_day[0].values()) if hires_per_day[0] else 0}")
    print(f"P1 Max Hires in a single day: {max(hires_per_day[1].values()) if hires_per_day[1] else 0}")

    print("\n--- ENDGAME SELLING PROFILE (Turns 700-718) ---")
    print("Turn | P0 Sells | P1 Sells | P0 Money | P1 Money | Mkt Inv: Wheat, Melon, Strawberry, Milk, Wool")
    for t in range(705, len(steps)):
        st = steps[t]
        obs = st[0].get("observation", {})
        f0 = obs.get("farms", [{}, {}])[0]
        f1 = obs.get("farms", [{}, {}])[1]
        mkt = obs.get("market", {}).get("inventory", {})
        p0_s = sells_by_turn[0].get(t, 0)
        p1_s = sells_by_turn[1].get(t, 0)
        m0 = f0.get("money", 0)
        m1 = f1.get("money", 0)
        inv_str = f"W:{mkt.get('WHEAT',0)} M:{mkt.get('MELON',0)} S:{mkt.get('STRAWBERRY',0)} Milk:{mkt.get('MILK',0)} Wool:{mkt.get('WOOL',0)}"
        print(f"T{t:<3} | {p0_s:>8} | {p1_s:>8} | {m0:>8.0f} | {m1:>8.0f} | {inv_str}")

if __name__ == '__main__':
    replay_dir = r'C:\Users\GauravPatel\Downloads\new_data_replays_31st_aug'
    target_files = [
        "103848464.json", # 142k vs 59k blowout
        "102531712.json", # 159k vs 121k high score
        "101511604.json", # 141k vs 145k
    ]
    for tf in target_files:
        full_path = os.path.join(replay_dir, tf)
        if os.path.exists(full_path):
            deep_analyze_replay(full_path)
