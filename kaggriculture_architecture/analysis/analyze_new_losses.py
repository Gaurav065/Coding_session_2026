import json
import os
from collections import defaultdict

def analyze_recent_loss_replay(rf_path):
    print(f"\n{'='*80}")
    print(f"ANALYZING LOSS REPLAY: {os.path.basename(rf_path)}")
    print(f"{'='*80}")
    
    with open(rf_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    steps = data.get("steps", [])
    agents = data.get("agents", ["P0", "P1"])
    print(f"Total Steps: {len(steps)}")
    print(f"Agents: P0={agents[0]} | P1={agents[1]}")
    
    final_step = steps[-1]
    p0_rew = final_step[0].get("reward")
    p1_rew = final_step[1].get("reward")
    p0_stat = final_step[0].get("status")
    p1_stat = final_step[1].get("status")
    print(f"Final Outcome: P0 = ${p0_rew:,.1f} ({p0_stat}) vs P1 = ${p1_rew:,.1f} ({p1_stat})")
    print(f"Delta: {p0_rew - p1_rew:+,.1f}")

    # Track shop unlocks
    unlocked_shops = []
    
    # Track actions
    seeds = [defaultdict(int), defaultdict(int)]
    animals = [defaultdict(int), defaultdict(int)]
    buys = [defaultdict(int), defaultdict(int)]
    sells = [defaultdict(int), defaultdict(int)]
    hires = [defaultdict(int), defaultdict(int)]
    land = [[], []]
    
    # Track inventory progression
    money_progression = [[], []]
    
    for t, step in enumerate(steps):
        obs0 = step[0].get("observation", {})
        farms = obs0.get("farms", [{}, {}])
        if len(farms) > 0:
            money_progression[0].append((t, farms[0].get("money", 0)))
        if len(farms) > 1:
            money_progression[1].append((t, farms[1].get("money", 0)))
            
        town = obs0.get("town", {})
        shops = town.get("unlocked_shops", [])
        if len(shops) > len(unlocked_shops):
            unlocked_shops = list(shops)
            print(f"Turn {t:<3} (Day {t//24}): Town Shop Unlocked -> {shops}")
            
        for p in [0, 1]:
            act = step[p].get("action") or {}
            for m in act.get("market", []):
                if not m: continue
                op = m[0]
                if op == "BUY_SEED":
                    seeds[p][m[1]] += (m[2] if len(m) > 2 else 1)
                elif op == "BUY_ANIMAL":
                    animals[p][m[1]] += (m[2] if len(m) > 2 else 1)
                elif op == "BUY_PRODUCT":
                    buys[p][m[1]] += (m[2] if len(m) > 2 else 1)
                elif op == "SELL":
                    sells[p][m[1]] += (m[2] if len(m) > 2 else 1)
                elif op == "HIRE":
                    hires[p][t // 24] += 1
                elif op == "BUY_LAND":
                    land[p].append(t)

    print("\n--- FARM SETUP ---")
    print(f"P0 Animals: {dict(animals[0])}")
    print(f"P1 Animals: {dict(animals[1])}")
    print(f"P0 Seeds:   {dict(seeds[0])}")
    print(f"P1 Seeds:   {dict(seeds[1])}")
    print(f"P0 Land Turns: {land[0]} (Days {[t//24 for t in land[0]]})")
    print(f"P1 Land Turns: {land[1]} (Days {[t//24 for t in land[1]]})")

    print("\n--- TOTAL SALES (LIFETIME) ---")
    print(f"P0 Sells: {dict(sells[0])}")
    print(f"P1 Sells: {dict(sells[1])}")

    print("\n--- PRODUCTS BOUGHT ---")
    print(f"P0 Buys: {dict(buys[0])}")
    print(f"P1 Buys: {dict(buys[1])}")

    print("\n--- TURNING POINTS & LIQUIDATION (Steps 680 to 719) ---")
    print("Step | P0 Bank | P1 Bank | P0 Sells Step | P1 Sells Step | Mkt Inv: Milk, Wool, Wheat, Straw")
    for t in range(695, len(steps)):
        st = steps[t]
        obs = st[0].get("observation", {})
        f0 = obs.get("farms", [{}, {}])[0]
        f1 = obs.get("farms", [{}, {}])[1]
        mkt = obs.get("market", {}).get("inventory", {})
        
        act0 = st[0].get("action") or {}
        act1 = st[1].get("action") or {}
        p0_s = sum(m[2] if len(m) > 2 else 1 for m in act0.get("market", []) if m and m[0] == "SELL")
        p1_s = sum(m[2] if len(m) > 2 else 1 for m in act1.get("market", []) if m and m[0] == "SELL")
        
        inv_str = f"Milk:{mkt.get('MILK',0)} Wool:{mkt.get('WOOL',0)} W:{mkt.get('WHEAT',0)} S:{mkt.get('STRAWBERRY',0)}"
        print(f"T{t:<3} | {f0.get('money',0):>8.0f} | {f1.get('money',0):>8.0f} | {p0_s:>13} | {p1_s:>13} | {inv_str}")

if __name__ == '__main__':
    downloads = r'C:\Users\GauravPatel\Downloads'
    replays = ['104060356.json', '104058126.json', '104055879.json']
    for rp in replays:
        p = os.path.join(downloads, rp)
        if os.path.exists(p):
            analyze_recent_loss_replay(p)
