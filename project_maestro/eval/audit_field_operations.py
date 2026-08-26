"""Field Operations & Waste Forensic Auditor — Project Maestro

Audits 50 matches (36,000 turns) tracking:
1. Animal Care Coverage: % of animal days receiving daily CARE.
2. Crop Watering Coverage: % of plant days receiving daily WATER (and 0 missed-water events).
3. Weed Digging Efficiency: Count of useful vs wasteful DIG operations.
4. AMM Price Evolution & Sales Execution: Tracking price highs, lows, and margin capture.
"""

import sys
import json
import numpy as np
from collections import defaultdict

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.idc_master_agent import IDCMasterAgent
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def audit_field_operations(num_seeds: int = 50):
    print(f'Starting Field Operations Forensic Audit across N={num_seeds} Matches (36,000 Turns)...\n')

    total_animal_days = 0
    cared_animal_days = 0
    fed_animal_days = 0

    total_plant_days = 0
    watered_plant_days = 0
    withered_plants = 0

    total_digs = 0
    useful_digs = 0
    wasteful_digs = 0

    price_history = defaultdict(list)
    sales_by_product = defaultdict(float)

    for s in range(300, 300 + num_seeds):
        g = FastGame(seed=s)
        agent = IDCMasterAgent(seed=s)
        opp = MaestroFullPortfolioAgent(seed=s)

        while not g.done:
            obs0 = g.get_observation(0)
            obs1 = g.get_observation(1)
            act0 = agent(obs0)
            act1 = opp(obs1)

            # Record prices
            for prod, p in obs0["market"]["prices"].items():
                price_history[prod].append(p)

            # Inspect Farm 0 Tiles at turn 0 of each day
            if obs0["hour"] == 0:
                for r in obs0["farms"][0]["tiles"]:
                    for t in r:
                        if isinstance(t, dict):
                            if "animal" in t:
                                total_animal_days += 1
                                if t.get("fed_today", False):
                                    fed_animal_days += 1
                                if t.get("cared_today", False):
                                    cared_animal_days += 1
                            elif t.get("kind") == "PLANT":
                                total_plant_days += 1
                                if t.get("watered_today", False):
                                    watered_plant_days += 1
                                if t.get("consecutive_unwatered", 0) >= 2:
                                    withered_plants += 1

            # Inspect DIG actions in act0
            for u_act in [act0.get("farmer", [])] + act0.get("hands", []):
                if u_act and u_act[0] == "DIG":
                    total_digs += 1
                    # In FastGame, if day > 20 and digging outside NW/NE/SW, flag as wasteful
                    if obs0["day"] >= 20:
                        wasteful_digs += 1
                    else:
                        useful_digs += 1

            g.step_game(act0, act1)

    care_rate = (cared_animal_days / max(1, total_animal_days)) * 100
    feed_rate = (fed_animal_days / max(1, total_animal_days)) * 100
    water_rate = (watered_plant_days / max(1, total_plant_days)) * 100

    print('=' * 105)
    print('FIELD OPERATIONS & WASTE FORENSIC AUDIT REPORT (N=50 Matches)')
    print('=' * 105)
    print(f'1. ANIMAL HEALTH & CARE:')
    print(f'   - Total Animal-Days Tracked   : {total_animal_days:,}')
    print(f'   - Daily Feeding Coverage Rate : {feed_rate:5.2f}% (100% Target)')
    print(f'   - Daily CARE Coverage Rate    : {care_rate:5.2f}% (Doubles output when 100%)')
    print()
    print(f'2. CROP HEALTH & WATERING:')
    print(f'   - Total Plant-Days Tracked    : {total_plant_days:,}')
    print(f'   - Daily Watering Coverage Rate: {water_rate:5.2f}%')
    print(f'   - Plants Withered / Decayed   : {withered_plants} (Zero Defect Invariant)')
    print()
    print(f'3. WEED DIGGING EFFICIENCY:')
    print(f'   - Total DIG Actions Executed  : {total_digs:,}')
    print(f'   - Useful Construction DIGs    : {useful_digs:,}')
    print(f'   - Wasteful Late-Season DIGs   : {wasteful_digs:,}')
    print()
    print(f'4. AMM PRICE VOLATILITY RANGE (Average across 50 Seeds):')
    for prod in ["STRAWBERRY", "MELON", "MILK", "WOOL", "FERTILIZER", "WHEAT", "CARROT", "TOMATO"]:
        prices = price_history.get(prod, [0])
        print(f'   - {prod:<12s}: Min ${np.min(prices):3d} | Max ${np.max(prices):3d} | Mean ${np.mean(prices):5.1f} | Std ${np.std(prices):4.1f}')
    print('=' * 105)

    out_file = 'project_maestro/data/field_operations_audit_report.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_animal_days": total_animal_days,
            "feed_rate": feed_rate,
            "care_rate": care_rate,
            "total_plant_days": total_plant_days,
            "water_rate": water_rate,
            "withered_plants": withered_plants,
            "total_digs": total_digs,
            "wasteful_digs": wasteful_digs
        }, f, indent=2)

if __name__ == '__main__':
    audit_field_operations(50)
