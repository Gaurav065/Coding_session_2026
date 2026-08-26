"""Forensic Root Cause Isolator for 80s Matchups

Isolates and prints full game-state diagnostics for the exact seeds where our agent
lost against Dominant Dairy Meta (10C/4S) and All-In Sheep & Strawberries (14S/28Str).
"""

import sys
import json
import numpy as np
from collections import defaultdict

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def diagnose_80s_losses(seeds=list(range(500, 550))):
    print('=' * 115)
    print('ISOLATING ROOT CAUSE: DOMINANT DAIRY META (10C/4S) & ALL-IN SHEEP (14S/28Str) LOSSES')
    print('=' * 115)

    dairy_losses = []
    sheep_losses = []

    # 1. Dominant Dairy Meta
    opp_dairy = lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 6, "enable_3b": False
    }, seed=s)

    for s in seeds:
        g = FastGame(seed=s)
        agent = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 9, "sheep_cap": 4, "strawberry_target": 22, "melon_seed_target": 10,
            "crew_mid": 10, "crew_late": 12, "enable_3b": True, "feed_protection": True
        }, seed=s)
        opp = opp_dairy(s)

        p0_sales = defaultdict(float)
        p1_sales = defaultdict(float)

        while not g.done:
            obs0 = g.get_observation(0)
            obs1 = g.get_observation(1)
            act0 = agent(obs0)
            act1 = opp(obs1)

            for order in act0.get("market", []):
                if order and order[0] == "SELL" and len(order) >= 3:
                    p0_sales[order[1]] += int(order[2]) * obs0["market"]["prices"].get(order[1], 0)
            for order in act1.get("market", []):
                if order and order[0] == "SELL" and len(order) >= 3:
                    p1_sales[order[1]] += int(order[2]) * obs1["market"]["prices"].get(order[1], 0)

            g.step_game(act0, act1)

        f0 = g.farms[0]
        f1 = g.farms[1]
        if f0.money <= f1.money:
            dairy_losses.append({
                "seed": s, "margin": f0.money - f1.money, "p0_score": f0.money, "p1_score": f1.money,
                "p0_milk": p0_sales["MILK"], "p1_milk": p1_sales["MILK"],
                "p0_straw": p0_sales["STRAWBERRY"], "p1_straw": p1_sales["STRAWBERRY"],
                "p0_wool": p0_sales["WOOL"], "p1_wool": p1_sales["WOOL"],
                "p0_shed_leftover": sum(g.farms[0].shed.values()),
                "p1_shed_leftover": sum(g.farms[1].shed.values()),
                "shops": list(g.unlocked_shops)
            })

    # 2. All-In Sheep & Strawberries
    opp_sheep = lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 0, "sheep_cap": 14, "strawberry_target": 28, "melon_seed_target": 0, "crew_mid": 11, "crew_late": 13
    }, seed=s)

    for s in seeds:
        g = FastGame(seed=s)
        agent = MaestroFullPortfolioAgent(params={
            "cow_cap_base": 9, "sheep_cap": 4, "strawberry_target": 22, "melon_seed_target": 10,
            "crew_mid": 10, "crew_late": 12, "enable_3b": True, "feed_protection": True
        }, seed=s)
        opp = opp_sheep(s)

        p0_sales = defaultdict(float)
        p1_sales = defaultdict(float)

        while not g.done:
            obs0 = g.get_observation(0)
            obs1 = g.get_observation(1)
            act0 = agent(obs0)
            act1 = opp(obs1)

            for order in act0.get("market", []):
                if order and order[0] == "SELL" and len(order) >= 3:
                    p0_sales[order[1]] += int(order[2]) * obs0["market"]["prices"].get(order[1], 0)
            for order in act1.get("market", []):
                if order and order[0] == "SELL" and len(order) >= 3:
                    p1_sales[order[1]] += int(order[2]) * obs1["market"]["prices"].get(order[1], 0)

            g.step_game(act0, act1)

        f0 = g.farms[0]
        f1 = g.farms[1]
        if f0.money <= f1.money:
            sheep_losses.append({
                "seed": s, "margin": f0.money - f1.money, "p0_score": f0.money, "p1_score": f1.money,
                "p0_milk": p0_sales["MILK"], "p1_milk": p1_sales["MILK"],
                "p0_straw": p0_sales["STRAWBERRY"], "p1_straw": p1_sales["STRAWBERRY"],
                "p0_wool": p0_sales["WOOL"], "p1_wool": p1_sales["WOOL"],
                "shops": list(g.unlocked_shops)
            })

    print(f'DOMINANT DAIRY META LOSSES: {len(dairy_losses)} / {len(seeds)}')
    for d in dairy_losses[:5]:
        print(f'Seed {d["seed"]}: Deficit -${abs(d["margin"]):,.0f} | P0: ${d["p0_score"]:,.0f} vs P1: ${d["p1_score"]:,.0f}')
        print(f'   - Milk: P0 ${d["p0_milk"]:,.0f} vs P1 ${d["p1_milk"]:,.0f} (Delta: -${d["p1_milk"] - d["p0_milk"]:,.0f})')
        print(f'   - Straw: P0 ${d["p0_straw"]:,.0f} vs P1 ${d["p1_straw"]:,.0f} (Delta: +${d["p0_straw"] - d["p1_straw"]:,.0f})')
        print(f'   - Wool: P0 ${d["p0_wool"]:,.0f} vs P1 ${d["p1_wool"]:,.0f} (Delta: -${d["p1_wool"] - d["p0_wool"]:,.0f})')
        print(f'   - Shed Leftovers: P0 {d["p0_shed_leftover"]} items vs P1 {d["p1_shed_leftover"]} items')
        print(f'   - Shops: {d["shops"][:4]}\n')

    print(f'\nALL-IN SHEEP & STRAWBERRIES LOSSES: {len(sheep_losses)} / {len(seeds)}')
    for s in sheep_losses[:5]:
        print(f'Seed {s["seed"]}: Deficit -${abs(s["margin"]):,.0f} | P0: ${s["p0_score"]:,.0f} vs P1: ${s["p1_score"]:,.0f}')
        print(f'   - Milk: P0 ${s["p0_milk"]:,.0f} vs P1 ${s["p1_milk"]:,.0f}')
        print(f'   - Straw: P0 ${s["p0_straw"]:,.0f} vs P1 ${s["p1_straw"]:,.0f}')
        print(f'   - Wool: P0 ${s["p0_wool"]:,.0f} vs P1 ${s["p1_wool"]:,.0f}')
        print(f'   - Shops: {s["shops"][:4]}\n')

if __name__ == '__main__':
    diagnose_80s_losses()
