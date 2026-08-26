"""Granular Telemetry Match Auditor for Project Maestro

Simulates a match and records:
1. Exact Price Trajectories of all 9 items over all 720 turns.
2. Exact Town Shop reveals on Days 3, 6, 9, 12, 15, 18, 21, 24, 27.
3. Leftover / Unused items in Shed and Worker Inventories at Turn 719.
4. Seeds purchased vs planted vs wasted in private['seeds'].
5. Endgame field yield vs what was harvested vs what was missed/unsold.
6. Total monetary value lost to inefficiencies.
"""

import sys
import json
import numpy as np
from collections import defaultdict
from typing import Dict, List, Any

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.master_counter_agent import MasterCounterAgent
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent

def run_match_telemetry(seed: int = 42):
    g = FastGame(seed=seed)
    agent0 = MasterCounterAgent(seed=seed)
    agent1 = make_meta_calibrated_opponent(seed=seed)

    # Trackers
    price_history = defaultdict(list) # item -> list of 720 prices
    market_inv_history = defaultdict(list) # item -> list of 720 market inventories
    shop_spawns = [] # list of (day, shop_name)

    seeds_bought = defaultdict(int)
    seeds_planted = defaultdict(int)
    items_sold = defaultdict(int)
    revenue_earned = defaultdict(float)

    prev_shops_len = 0

    while not g.done:
        step = g.step
        day = g.day
        hour = g.hour

        obs0 = g.get_observation(0)
        obs1 = g.get_observation(1)

        # Record Prices & Market Inventory
        for item, p in obs0["market"]["prices"].items():
            price_history[item].append(p)
        for item, inv_val in obs0["market"]["inventory"].items():
            market_inv_history[item].append(inv_val)

        # Record Shop Spawns
        cur_shops = obs0["town"]["unlocked_shops"]
        if len(cur_shops) > prev_shops_len:
            new_shop = cur_shops[-1]
            shop_spawns.append({
                "day": day,
                "step": step,
                "shop": new_shop
            })
            prev_shops_len = len(cur_shops)

        act0 = agent0(obs0)
        act1 = agent1(obs1)

        # Track purchases & sales
        for order in act0.get("market", []):
            if not order: continue
            op = order[0]
            if op == "BUY_SEED" and len(order) >= 3:
                seeds_bought[order[1]] += int(order[2])
            elif op == "SELL" and len(order) >= 3:
                item = order[1]
                qty = int(order[2])
                p = obs0["market"]["prices"].get(item, 0)
                items_sold[item] += qty
                revenue_earned[item] += (qty * p)

        # Track plant actions
        farmer_act = act0.get("farmer", [])
        if farmer_act and farmer_act[0] == "PLANT" and len(farmer_act) >= 2:
            seeds_planted[farmer_act[1]] += 1
        for hand_act in act0.get("hands", []):
            if hand_act and hand_act[0] == "PLANT" and len(hand_act) >= 2:
                seeds_planted[hand_act[1]] += 1

        g.step_game(act0, act1)

    # End of Match Forensic Analysis
    final_obs = g.get_observation(0)
    final_p0 = g.farms[0]
    final_prices = final_obs["market"]["prices"]

    # 1. Unused Shed Inventory
    shed_leftovers = dict(final_p0.shed)
    shed_value = sum(qty * final_prices.get(item, 0) for item, qty in shed_leftovers.items())

    # 2. Unused Worker Inventories
    worker_inv_leftovers = defaultdict(int)
    for inv in final_p0.inventories:
        for item, qty in inv.items():
            worker_inv_leftovers[item] += qty
    worker_inv_value = sum(qty * final_prices.get(item, 0) for item, qty in worker_inv_leftovers.items())

    # 3. Unused Seeds in private['seeds']
    seeds_leftover = dict(final_p0.seeds)
    seeds_wasted_cost = {
        "WHEAT": seeds_leftover.get("WHEAT", 0) * 10,
        "CARROT": seeds_leftover.get("CARROT", 0) * 40,
        "TOMATO": seeds_leftover.get("TOMATO", 0) * 45,
        "STRAWBERRY": seeds_leftover.get("STRAWBERRY", 0) * 120,
        "MELON": seeds_leftover.get("MELON", 0) * 250,
    }
    total_seed_waste_cost = sum(seeds_wasted_cost.values())

    # 4. Field Yield Left Unharvested
    field_unharvested = defaultdict(int)
    for row in final_p0.tiles:
        for t in row:
            if isinstance(t, dict):
                y = t.get("yield_units", 0)
                if y > 0:
                    if t.get("kind") == "PLANT":
                        field_unharvested[t.get("crop")] += y
                    elif "animal" in t:
                        prod = "MILK" if t.get("animal") == "COW" else ("WOOL" if t.get("animal") == "SHEEP" else "EGG")
                        field_unharvested[prod] += y

    field_unharvested_value = sum(qty * final_prices.get(item, 0) for item, qty in field_unharvested.items())

    report = {
        "seed": seed,
        "final_score_p0": final_p0.money,
        "final_score_p1": g.farms[1].money,
        "winner": "Our Agent (P0)" if final_p0.money > g.farms[1].money else "Opponent (P1)",
        "shop_spawns": shop_spawns,
        "price_summary": {
            item: {
                "start_price": price_history[item][0],
                "min_price": int(min(price_history[item])),
                "max_price": int(max(price_history[item])),
                "final_price": price_history[item][-1],
                "avg_price": round(float(np.mean(price_history[item])), 1)
            }
            for item in price_history
        },
        "sales_and_revenue": {
            item: {
                "units_sold": items_sold[item],
                "revenue": round(revenue_earned[item], 2)
            }
            for item in items_sold
        },
        "seed_accounting": {
            crop: {
                "bought": seeds_bought.get(crop, 0),
                "planted": seeds_planted.get(crop, 0),
                "leftover_in_slot": seeds_leftover.get(crop, 0),
                "wasted_capital": seeds_wasted_cost.get(crop, 0)
            }
            for crop in ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"]
            if seeds_bought.get(crop, 0) > 0 or seeds_leftover.get(crop, 0) > 0
        },
        "total_seed_capital_wasted": total_seed_waste_cost,
        "leftover_shed_inventory": {k: v for k, v in shed_leftovers.items() if v > 0},
        "leftover_shed_market_value": shed_value,
        "leftover_worker_carrying": dict(worker_inv_leftovers),
        "leftover_worker_market_value": worker_inv_value,
        "unharvested_field_yield": dict(field_unharvested),
        "unharvested_field_market_value": field_unharvested_value,
        "total_unrealized_potential_cash": round(shed_value + worker_inv_value + total_seed_waste_cost + field_unharvested_value, 2)
    }

    # Print Formatted Report
    print("=" * 95)
    print(f"MATCH TELEMETRY & EFFICIENCY AUDIT REPORT (Seed {seed})")
    print("=" * 95)
    print(f"Final Score : {report['winner']} | P0: ${final_p0.money:,.2f} vs P1: ${g.farms[1].money:,.2f}\n")

    print("1. TOWN SHOP UNLOCKS:")
    for s in shop_spawns:
        print(f"   - Day {s['day']:2d} (Turn {s['step']:3d}): {s['shop']}")
    if not shop_spawns:
        print("   - No shops spawned.")

    print("\n2. PRICE TRAJECTORY SUMMARY (Start -> Min -> Max -> End [Avg]):")
    for item, p_data in report["price_summary"].items():
        print(f"   - {item:12s}: Start ${p_data['start_price']:3d} | Min ${p_data['min_price']:3d} | Max ${p_data['max_price']:3d} | Final ${p_data['final_price']:3d} (Avg: ${p_data['avg_price']:4.1f})")

    print("\n3. SEED UTILIZATION & WASTED CAPITAL:")
    for crop, s_data in report["seed_accounting"].items():
        print(f"   - {crop:12s}: Bought {s_data['bought']:3d} | Planted {s_data['planted']:3d} | Leftover {s_data['leftover_in_slot']:3d} (Wasted Cost: ${s_data['wasted_capital']})")
    print(f"   -> TOTAL UNUSED SEED CAPITAL: ${total_seed_waste_cost:,.2f}")

    print("\n4. ENDGAME LEFTOVERS & MISSED HARVESTS (At Final Market Prices):")
    print(f"   - Leftover in Shed       : {report['leftover_shed_inventory']} (Value: ${shed_value:,.2f})")
    print(f"   - In Worker Hands        : {report['leftover_worker_carrying']} (Value: ${worker_inv_value:,.2f})")
    print(f"   - Unharvested on Plots   : {report['unharvested_field_yield']} (Value: ${field_unharvested_value:,.2f})")
    print("   " + "-" * 90)
    print(f"   -> TOTAL UNREALIZED CASH (LEFT ON TABLE): ${report['total_unrealized_potential_cash']:,.2f}")
    print("=" * 95)

    out_path = f"project_maestro/data/telemetry_seed_{seed}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nSaved raw telemetry audit to {out_path}")

    return report

if __name__ == "__main__":
    seed_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 42
    run_match_telemetry(seed_arg)
