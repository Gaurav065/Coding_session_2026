"""Causal Shop-Value Table for Day-3 Shop Draws - Project Maestro

Quantifies how much forcing each of the 8 shop types on Day 3 changes final
self-play money for Player 0, holding seed fixed and with Player 1 running
the unmodified dispatcher agent throughout.
"""

import sys
import math
from typing import Dict, List, Tuple, Any

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    COW_PASTURES, GOOSE_COOPS, NW_WHEAT, get_step_towards,
    MaestroFullPortfolioAgent, DEFAULT_PARAMS
)

ALL_SHOPS = [
    "BAKERY",
    "PIZZA_SHOP",
    "BRUNCH_SPOT",
    "YARN_STORE",
    "ICE_CREAM_SHOP",
    "PET_CAFE",
    "SMOOTHIE_SHOP",
    "FARMERS_MARKET",
]

NW_ALL = list(dict.fromkeys(COW_PASTURES + GOOSE_COOPS + NW_WHEAT))  # 24 distinct tiles


def make_hybrid_agent(k: int, params=None):
    """
    Days 0..2: Plants WHEAT on the first k tiles of NW_ALL using the planter logic.
    Days 3..29: Hands off to unmodified MaestroFullPortfolioAgent.
    """
    planter_state = {"bought": False, "idx": 0}
    dispatcher = MaestroFullPortfolioAgent(params)

    def agent(obs: Dict[str, Any]) -> Dict[str, Any]:
        day = obs["day"]
        if day >= 3:
            return dispatcher(obs)

        # Planter logic for days 0..2
        farm = obs["farms"][obs["player"]]
        pos = tuple(farm["farmer"])
        seeds = obs["private"]["seeds"].get("WHEAT", 0)
        market = []
        if not planter_state["bought"] and k > 0:
            market.append(["BUY_SEED", "WHEAT", k])
            planter_state["bought"] = True

        if planter_state["idx"] >= k:
            return {"farmer": ["PASS"], "hands": [], "market": market}

        target = NW_ALL[planter_state["idx"]]
        if pos == target:
            tile = farm["tiles"][target[1]][target[0]]
            if tile is None and seeds > 0:
                planter_state["idx"] += 1
                return {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": market}
            planter_state["idx"] += 1
            return {"farmer": ["PASS"], "hands": [], "market": market}

        step = get_step_towards(pos, target)
        return {"farmer": [step], "hands": [], "market": market}

    return agent


def find_achievable_shops(seed: int, params=None) -> Dict[str, int]:
    """
    For a given seed, sweeps K in 0..24 with P1 running MaestroFullPortfolioAgent.
    Returns a dict mapping: shop_name -> chosen K value (smallest K).
    """
    shop_to_k = {}
    for k in range(25):
        game = FastGame(seed=seed)
        p0 = make_hybrid_agent(k, params)
        p1 = MaestroFullPortfolioAgent(params)

        # Run to start of day 3 (turn 72)
        while game.day < 3:
            act0 = p0(game.get_observation(0))
            act1 = p1(game.get_observation(1))
            game.step_game(act0, act1)

        if game.unlocked_shops:
            first_shop = game.unlocked_shops[0]
            if first_shop not in shop_to_k:
                shop_to_k[first_shop] = k

    return shop_to_k


def evaluate_seed(seed: int, shop_to_k: Dict[str, int], params=None) -> Dict[str, float]:
    """
    For each achievable shop on this seed, runs the full episode (720 steps)
    and records Player 0's final money.
    """
    shop_rewards = {}
    for shop, k in shop_to_k.items():
        game = FastGame(seed=seed)
        p0 = make_hybrid_agent(k, params)
        p1 = MaestroFullPortfolioAgent(params)

        while not game.done:
            act0 = p0(game.get_observation(0))
            act1 = p1(game.get_observation(1))
            game.step_game(act0, act1)

        shop_rewards[shop] = float(game.farms[0].money)

    return shop_rewards


def main():
    print("=" * 85)
    print("=== CAUSAL SHOP-VALUE TABLE FOR DAY-3 DRAW (CONTROLLED SEED COMPARISON) ===")
    print("=" * 85)

    # We evaluate 80 seeds to ensure every shop has at least 40 (seed, shop) observations
    SEED_LIST = list(range(10000, 10080))
    print(f"Sweeping K in 0..24 across {len(SEED_LIST)} seeds (P1 = real dispatcher agent)...")

    seed_shop_data = {}      # seed -> {shop: p0_money}
    shop_deltas = {s: [] for s in ALL_SHOPS}   # shop -> [delta_relative_to_seed_mean]
    shop_raw_money = {s: [] for s in ALL_SHOPS} # shop -> [raw_p0_money]
    shop_reach_count = {s: 0 for s in ALL_SHOPS}

    for idx, seed in enumerate(SEED_LIST):
        shop_to_k = find_achievable_shops(seed)
        for s in shop_to_k:
            shop_reach_count[s] += 1

        rewards = evaluate_seed(seed, shop_to_k)
        seed_shop_data[seed] = rewards

        # Controlled within-seed comparison: delta relative to the seed's mean across its achievable shops
        seed_mean = sum(rewards.values()) / len(rewards)
        for shop, r in rewards.items():
            shop_raw_money[shop].append(r)
            shop_deltas[shop].append(r - seed_mean)

        if (idx + 1) % 10 == 0 or (idx + 1) == len(SEED_LIST):
            print(f"Processed {idx + 1:>2}/{len(SEED_LIST)} seeds...")

    print("\n" + "=" * 85)
    print(f"{'Shop Type':<18} | {'Reachable (n)':<14} | {'Mean Delta vs Seed Avg':<24} | {'Min Delta':<11} | {'Max Delta':<11}")
    print("-" * 85)

    sorted_shops = sorted(ALL_SHOPS, key=lambda s: (sum(shop_deltas[s])/len(shop_deltas[s])) if shop_deltas[s] else -1e9, reverse=True)

    for s in sorted_shops:
        deltas = shop_deltas[s]
        n = len(deltas)
        if n > 0:
            mean_d = sum(deltas) / n
            min_d = min(deltas)
            max_d = max(deltas)
            print(f"{s:<18} | {n:>3} / {len(SEED_LIST):<8} | ${mean_d:>+11,.2f}            | ${min_d:>+9,.2f} | ${max_d:>+9,.2f}")
        else:
            print(f"{s:<18} | {0:>3} / {len(SEED_LIST):<8} | {'N/A':>14}            | {'N/A':>10} | {'N/A':>10}")

    print("=" * 85)


if __name__ == "__main__":
    main()
