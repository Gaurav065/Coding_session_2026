"""Rigorous Statistical Analysis of Day-3 Shop Steering - Project Maestro

Performs:
1. Per-shop delta mean, standard deviation, standard error, and 95% CI.
2. Direct paired comparison (PIZZA_SHOP vs BAKERY, SMOOTHIE vs BAKERY, etc.) with t-test and p-values.
3. K-occupancy correlation and regression controlling for K (testing whether K-confounding drives shop value).
"""

import sys
import math
from typing import Dict, List, Tuple, Any
from scipy import stats
import numpy as np

sys.path.insert(0, r"C:\Coding")

from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    COW_PASTURES, GOOSE_COOPS, NW_WHEAT, get_step_towards,
    MaestroFullPortfolioAgent, DEFAULT_PARAMS
)

ALL_SHOPS = [
    "PIZZA_SHOP",
    "SMOOTHIE_SHOP",
    "FARMERS_MARKET",
    "ICE_CREAM_SHOP",
    "BRUNCH_SPOT",
    "YARN_STORE",
    "PET_CAFE",
    "BAKERY",
]

NW_ALL = list(dict.fromkeys(COW_PASTURES + GOOSE_COOPS + NW_WHEAT))  # 24 distinct tiles


def make_hybrid_agent(k: int, params=None):
    planter_state = {"bought": False, "idx": 0}
    dispatcher = MaestroFullPortfolioAgent(params)

    def agent(obs: Dict[str, Any]) -> Dict[str, Any]:
        day = obs["day"]
        if day >= 3:
            return dispatcher(obs)

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
    shop_to_k = {}
    for k in range(25):
        game = FastGame(seed=seed)
        p0 = make_hybrid_agent(k, params)
        p1 = MaestroFullPortfolioAgent(params)

        while game.day < 3:
            act0 = p0(game.get_observation(0))
            act1 = p1(game.get_observation(1))
            game.step_game(act0, act1)

        if game.unlocked_shops:
            first_shop = game.unlocked_shops[0]
            if first_shop not in shop_to_k:
                shop_to_k[first_shop] = k

    return shop_to_k


def run_episode(seed: int, k: int, params=None) -> float:
    game = FastGame(seed=seed)
    p0 = make_hybrid_agent(k, params)
    p1 = MaestroFullPortfolioAgent(params)

    while not game.done:
        act0 = p0(game.get_observation(0))
        act1 = p1(game.get_observation(1))
        game.step_game(act0, act1)

    return float(game.farms[0].money)


def main():
    print("=" * 90)
    print("=== RIGOROUS STATISTICAL ANALYSIS OF DAY-3 SHOP STEERING (100 SEEDS) ===")
    print("=" * 90)

    SEED_LIST = list(range(10000, 10100))  # 100 disjoint seeds
    print(f"Sweeping K in 0..24 across {len(SEED_LIST)} seeds...")

    # Data structures
    # seed -> {shop: (p0_money, k)}
    raw_results = {}
    shop_deltas = {s: [] for s in ALL_SHOPS}
    shop_k_values = {s: [] for s in ALL_SHOPS}
    shop_raw_money = {s: [] for s in ALL_SHOPS}

    all_k_flat = []
    all_r_flat = []
    all_shop_flat = []

    for idx, seed in enumerate(SEED_LIST):
        shop_to_k = find_achievable_shops(seed)
        seed_data = {}
        for shop, k in shop_to_k.items():
            r = run_episode(seed, k)
            seed_data[shop] = (r, k)

        raw_results[seed] = seed_data

        # Within-seed mean
        rewards = [r for r, k in seed_data.values()]
        seed_mean = sum(rewards) / len(rewards)

        for shop, (r, k) in seed_data.items():
            delta = r - seed_mean
            shop_deltas[shop].append(delta)
            shop_k_values[shop].append(k)
            shop_raw_money[shop].append(r)

            all_k_flat.append(k)
            all_r_flat.append(r)
            all_shop_flat.append(shop)

        if (idx + 1) % 20 == 0 or (idx + 1) == len(SEED_LIST):
            print(f"Processed {idx + 1:>3}/{len(SEED_LIST)} seeds...")

    # =========================================================================
    # PART 1: PER-SHOP VARIANCE & CONFIDENCE INTERVALS
    # =========================================================================
    print("\n" + "=" * 90)
    print("=== PART 1: PER-SHOP CAUSAL DELTA & VARIANCE TABLE ===")
    print("=" * 90)
    print(f"{'Shop Type':<16} | {'n':<4} | {'Mean Delta':<12} | {'Std Dev':<10} | {'Std Error':<10} | {'95% Conf Interval':<24} | {'Mean K (Std)':<12}")
    print("-" * 90)

    for s in ALL_SHOPS:
        deltas = np.array(shop_deltas[s])
        ks = np.array(shop_k_values[s])
        n = len(deltas)
        mean_d = np.mean(deltas)
        std_d = np.std(deltas, ddof=1)
        se_d = std_d / math.sqrt(n)
        ci_low = mean_d - 1.96 * se_d
        ci_high = mean_d + 1.96 * se_d

        mean_k = np.mean(ks)
        std_k = np.std(ks, ddof=1)

        ci_str = f"[${ci_low:>+7,.0f}, ${ci_high:>+7,.0f}]"
        k_str = f"{mean_k:>4.1f} (±{std_k:>3.1f})"
        print(f"{s:<16} | {n:>3}  | ${mean_d:>+9,.2f}  | ${std_d:>8,.2f} | ${se_d:>8,.2f} | {ci_str:<24} | {k_str:<12}")

    # =========================================================================
    # PART 2: PAIRED DIRECT COMPARISONS (TOP vs BOTTOM)
    # =========================================================================
    print("\n" + "=" * 90)
    print("=== PART 2: DIRECT PAIRED COMPARISONS (SAME-SEED MATCHED PAIRS) ===")
    print("=" * 90)

    pairs_to_test = [
        ("PIZZA_SHOP", "BAKERY"),
        ("SMOOTHIE_SHOP", "BAKERY"),
        ("PIZZA_SHOP", "PET_CAFE"),
        ("SMOOTHIE_SHOP", "PET_CAFE"),
        ("PIZZA_SHOP", "YARN_STORE"),
        ("FARMERS_MARKET", "BAKERY"),
    ]

    print(f"{'Comparison (A vs B)':<28} | {'Paired n':<8} | {'Mean Diff (A - B)':<18} | {'Std Dev':<10} | {'SE':<9} | {'t-stat':<7} | {'p-value':<9}")
    print("-" * 90)

    for shop_a, shop_b in pairs_to_test:
        diffs = []
        k_diffs = []
        for seed, data in raw_results.items():
            if shop_a in data and shop_b in data:
                r_a, k_a = data[shop_a]
                r_b, k_b = data[shop_b]
                diffs.append(r_a - r_b)
                k_diffs.append(k_a - k_b)

        diffs = np.array(diffs)
        n_pair = len(diffs)
        mean_diff = np.mean(diffs)
        std_diff = np.std(diffs, ddof=1)
        se_diff = std_diff / math.sqrt(n_pair)
        t_stat = mean_diff / se_diff
        p_val = 2 * (1 - stats.t.cdf(abs(t_stat), df=n_pair - 1))

        comp_str = f"{shop_a} vs {shop_b}"
        print(f"{comp_str:<28} | {n_pair:>4} / 100 | ${mean_diff:>+14,.2f}   | ${std_diff:>8,.2f} | ${se_diff:>7,.2f} | {t_stat:>+6.2f} | {p_val:<9.4e}")

    # =========================================================================
    # PART 3: K-OCCUPANCY CORRELATION & CONFOUNDING ANALYSIS
    # =========================================================================
    print("\n" + "=" * 90)
    print("=== PART 3: K-OCCUPANCY CORRELATION & CONFOUNDING ANALYSIS ===")
    print("=" * 90)

    all_k = np.array(all_k_flat)
    all_r = np.array(all_r_flat)
    r_k_corr, p_k_corr = stats.pearsonr(all_k, all_r)

    print(f"Overall Pearson correlation between K (tiles planted) and Final P0 Money: r = {r_k_corr:+.4f} (p = {p_k_corr:.4e})")

    # Mean K per shop vs Mean Reward per shop correlation
    shop_mean_k = [np.mean(shop_k_values[s]) for s in ALL_SHOPS]
    shop_mean_r = [np.mean(shop_raw_money[s]) for s in ALL_SHOPS]
    r_shop_k_corr, p_shop_k_corr = stats.pearsonr(shop_mean_k, shop_mean_r)
    print(f"Across-Shop correlation between Mean K and Mean Shop Money:               r = {r_shop_k_corr:+.4f} (p = {p_shop_k_corr:.4e})")

    print("\nPer-Shop K Distribution:")
    for s in ALL_SHOPS:
        ks = shop_k_values[s]
        print(f"  {s:<16}: Mean K = {np.mean(ks):>4.2f}, Median = {np.median(ks):>2.0f}, Min K = {min(ks):>2}, Max K = {max(ks):>2}")

    # ANOVA / OLS regression: Money ~ K + Shop_Dummies
    print("\nTesting Shop Effect After Controlling for K (Two-Way Fixed Effects):")
    # For each seed, center by seed mean, then regress (r - seed_mean) on K and Shop dummies
    y_centered = []
    x_k = []
    x_shops = {s: [] for s in ALL_SHOPS}

    for seed, data in raw_results.items():
        seed_mean = sum(r for r, k in data.values()) / len(data)
        for shop, (r, k) in data.items():
            y_centered.append(r - seed_mean)
            x_k.append(k)
            for s in ALL_SHOPS:
                x_shops[s].append(1.0 if s == shop else 0.0)

    # Design matrix: [K, Shop_1, ..., Shop_7] (Bakery as reference)
    ref_shop = "BAKERY"
    other_shops = [s for s in ALL_SHOPS if s != ref_shop]
    X = np.column_stack([np.array(x_k)] + [np.array(x_shops[s]) for s in other_shops] + [np.ones(len(y_centered))])
    Y = np.array(y_centered)

    # OLS solve: (X^T X)^-1 X^T Y
    beta, residuals, rank, s_sv = np.linalg.lstsq(X, Y, rcond=None)
    residuals_sum = np.sum((Y - X @ beta) ** 2)
    dof = len(Y) - X.shape[1]
    mse = residuals_sum / dof
    var_beta = mse * np.linalg.inv(X.T @ X)
    se_beta = np.sqrt(np.diagonal(var_beta))

    print(f"{'Feature / Shop':<20} | {'Coeff (vs BAKERY)':<20} | {'Std Error':<12} | {'t-stat':<8} | {'p-value':<9}")
    print("-" * 75)
    print(f"{'K (Tiles Planted)':<20} | ${beta[0]:>+15,.2f}    | ${se_beta[0]:>10,.2f} | {beta[0]/se_beta[0]:>+7.2f} | {2*(1-stats.t.cdf(abs(beta[0]/se_beta[0]), df=dof)):<9.4e}")
    for i, s in enumerate(other_shops):
        b = beta[i+1]
        se = se_beta[i+1]
        t = b / se
        p = 2 * (1 - stats.t.cdf(abs(t), df=dof))
        print(f"{s:<20} | ${b:>+15,.2f}    | ${se:>10,.2f} | {t:>+7.2f} | {p:<9.4e}")

    print("=" * 90)


if __name__ == "__main__":
    main()
