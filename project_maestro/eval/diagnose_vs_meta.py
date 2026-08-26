"""Forensic Diagnosis: Why 10c4s and 7c7s close the score margin

Analyzes step-by-step telemetry of IDCMasterAgent vs Dominant_Dairy_Meta (10c4s)
and Balanced_Pasture_Hybrid (7c7s) to isolate the exact points of lost margin.
"""

import sys
import numpy as np
from collections import defaultdict

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.idc_master_agent import IDCMasterAgent
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def diagnose_matchups(seeds=[101, 102, 103, 104, 105]):
    print('=' * 95)
    print('FORENSIC DIAGNOSIS: IDCMasterAgent vs Dominant_Dairy_Meta (10c4s)')
    print('=' * 95)

    for seed in seeds:
        g = FastGame(seed=seed)
        cand = IDCMasterAgent(seed=seed)
        opp = MaestroFullPortfolioAgent(params={'cow_cap_base': 10, 'sheep_cap': 4, 'strawberry_target': 18, 'melon_seed_target': 6, 'enable_3b': False}, seed=seed)

        # Track sales revenue per player
        p0_sales = defaultdict(float)
        p1_sales = defaultdict(float)

        while not g.done:
            obs0 = g.get_observation(0)
            obs1 = g.get_observation(1)

            act0 = cand(obs0)
            act1 = opp(obs1)

            # Record sales
            for order in act0.get("market", []):
                if order and order[0] == "SELL" and len(order) >= 3:
                    item, qty = order[1], int(order[2])
                    p0_sales[item] += qty * obs0["market"]["prices"].get(item, 0)
            for order in act1.get("market", []):
                if order and order[0] == "SELL" and len(order) >= 3:
                    item, qty = order[1], int(order[2])
                    p1_sales[item] += qty * obs1["market"]["prices"].get(item, 0)

            g.step_game(act0, act1)

        f0 = g.farms[0]
        f1 = g.farms[1]
        winner = "OUR AGENT (P0)" if f0.money > f1.money else "OPPONENT (P1)"
        margin = f0.money - f1.money

        print(f'Seed {seed}: Winner: {winner:<15s} | P0: ${f0.money:9.2f} vs P1: ${f1.money:9.2f} (Margin: +${margin:7.2f})')
        print(f'   - P0 Revenue: Milk ${p0_sales["MILK"]:8.0f} | Straw ${p0_sales["STRAWBERRY"]:8.0f} | Wool ${p0_sales["WOOL"]:8.0f} | Melon ${p0_sales["MELON"]:8.0f} | Fert ${p0_sales["FERTILIZER"]:8.0f}')
        print(f'   - P1 Revenue: Milk ${p1_sales["MILK"]:8.0f} | Straw ${p1_sales["STRAWBERRY"]:8.0f} | Wool ${p1_sales["WOOL"]:8.0f} | Melon ${p1_sales["MELON"]:8.0f} | Fert ${p1_sales["FERTILIZER"]:8.0f}\n')

if __name__ == '__main__':
    diagnose_matchups()
