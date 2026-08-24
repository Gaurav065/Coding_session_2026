"""Phase 0 Meta Analysis Script - Project Maestro (Corrected)

Analyzes Kaggle's official public Top Episodes dataset in place (/kaggle/input/)
without downloading the full ~20GB dataset.

Extracts:
1. Portfolios played by top meta (animal mix, land unlock timing, crop choices, crew size/hires).
2. Realized AMM price paths (min, mean, max, floor-collapse rates).
3. Outcome distributions vs K=15 clustered 8-d daily demand-pressure vector.

Outputs compact summary CSVs into results/:
- meta_portfolio_summary.csv
- realized_prices_summary.csv
- demand_profile_outcomes.csv

References:
- kaggriculture.py:97 (LAND_PRICES)
- kaggriculture.py:99-101 (FARM_HAND_COST_MULT, Fibonacci hire cost)
- kaggriculture.py:103 (SHOPS)
- kaggriculture.py:114 (TOWN_CENTER_PRODUCTS)
- kaggriculture.py:118 (MAX_SHOP_INSTANCES = 8)
- kaggriculture.py:126 (MARKET_PARAMS)
- kaggriculture.py:151 (ANIMALS)
- kaggriculture.py:539 (HIRE execution)
- kaggriculture.py:727 (_town_consume)
- kaggriculture.py:843 (_drop_inventories_to_shed)
- kaggriculture.py:886 (_end_of_day shop unlocks)
- kaggriculture.py:963 (s.reward calculation)
"""

import os
import sys
import glob
import json
import gzip
import csv
import math
from collections import defaultdict
import numpy as np

ALL_PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER")
NON_FERT_PRODUCTS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL")
ALL_CROPS = ("WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON")
ALL_ANIMALS = ("GOOSE", "COW", "SHEEP")

SHOPS_MAP = {
    "BAKERY": ["EGG", "WHEAT"],
    "PIZZA_SHOP": ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT": ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE": ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE": ["CARROT"],
    "SMOOTHIE_SHOP": ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}


def compute_daily_demand_pressure(unlocked_shops):
    """Compute the exact 9-dimensional daily demand pressure vector.
    
    References:
    - kaggriculture.py:736-744: Shop tick every 4 steps (6x/day). Single-product shops use multiplier 2.
    - kaggriculture.py:745-748: Town center tick every 24 steps (1x/day) for non-fertilizer products.
    """
    pressure = {p: (1 if p != "FERTILIZER" else 0) for p in ALL_PRODUCTS}
    for shop in unlocked_shops:
        products = SHOPS_MAP.get(shop, [])
        mult = 2 if len(products) == 1 else 1
        for prod in products:
            pressure[prod] += 6 * mult
    return pressure


def cluster_demand_vectors(records, k=15, random_seed=42):
    """Cluster 8-d non-fertilizer standardized demand pressure vectors into K=15 classes using K-Means."""
    if len(records) < k:
        for idx, r in enumerate(records):
            r["cluster_id"] = idx
        return

    # Build matrix (N x 8)
    data = []
    for r in records:
        pr = r["pressure"]
        row = [float(pr[p]) for p in NON_FERT_PRODUCTS]
        data.append(row)
    X = np.array(data, dtype=np.float64)

    # Standardize features
    mean = np.mean(X, axis=0)
    std = np.std(X, axis=0)
    std[std == 0] = 1.0 # avoid divide by zero
    X_norm = (X - mean) / std

    # K-Means algorithm with fixed seed
    np.random.seed(random_seed)
    # Initialize k-means++
    n_samples = X_norm.shape[0]
    centers = [X_norm[np.random.randint(n_samples)]]
    for _ in range(1, k):
        dist_sq = np.min([np.sum((X_norm - c) ** 2, axis=1) for c in centers], axis=0)
        probs = dist_sq / np.sum(dist_sq)
        next_center = X_norm[np.random.choice(n_samples, p=probs)]
        centers.append(next_center)
    centers = np.array(centers)

    # Iterative Lloyd's update
    for _ in range(50):
        # Assign clusters
        dists = np.array([np.sum((X_norm - c) ** 2, axis=1) for c in centers])
        labels = np.argmin(dists, axis=0)
        # Update centers
        new_centers = np.array([
            X_norm[labels == i].mean(axis=0) if np.sum(labels == i) > 0 else centers[i]
            for i in range(k)
        ])
        if np.allclose(centers, new_centers, atol=1e-4):
            break
        centers = new_centers

    # Assign cluster labels to records
    for r, lbl in zip(records, labels):
        r["cluster_id"] = int(lbl)


def load_json_content(file_path):
    """Load JSON content handling plain or gzipped files."""
    try:
        if file_path.endswith(".gz"):
            with gzip.open(file_path, "rt", encoding="utf-8") as f:
                return json.load(f)
        else:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return None


def parse_episode_data(data, source_id=""):
    """Parse a single episode data dict and extract high-signal meta features."""
    if not isinstance(data, dict):
        return None

    info = data.get("info", {}) or {}
    episode_id = info.get("EpisodeId") or source_id
    names = info.get("TeamNames") or [a.get("Name") for a in info.get("Agents", [])] or ["Player0", "Player1"]
    
    steps = data.get("steps", [])
    if not steps or len(steps) < 720:
        return None

    # Final rewards (money) - engine:963
    p0_reward = float(steps[-1][0].get("reward", 0) or 0)
    p1_reward = float(steps[-1][1].get("reward", 0) or 0)
    winner = 0 if p0_reward > p1_reward else (1 if p1_reward > p0_reward else -1)
    margin = abs(p0_reward - p1_reward)

    # Extract Town Shops - engine:886-891
    final_obs = steps[-1][0].get("observation", {}) or {}
    unlocked_shops = list((final_obs.get("town", {}) or {}).get("unlocked_shops", []) or [])
    
    # Compute 9-d demand pressure vector
    pressure = compute_daily_demand_pressure(unlocked_shops)

    # Track Price Paths across all 720 steps
    price_history = {prod: [] for prod in ALL_PRODUCTS}
    inv_history = {prod: [] for prod in ALL_PRODUCTS}

    player_data = []
    for p_idx in (0, 1):
        p_name = names[p_idx] if p_idx < len(names) else f"Player_{p_idx}"
        p_reward = p0_reward if p_idx == 0 else p1_reward
        p_won = (winner == p_idx)

        quad_unlock_day = {}
        day0_hires = 0
        day0_seeds = defaultdict(int)
        day0_animals = defaultdict(int)
        total_hires = 0
        animals_bought = defaultdict(int)
        seeds_bought = defaultdict(int)
        sells_by_product = defaultdict(int)
        revenue_by_product = defaultdict(float)

        for step_idx, step_data in enumerate(steps):
            obs = step_data[p_idx].get("observation", {}) or {}
            day = obs.get("day", step_idx // 24)

            # Record market prices once per step (from p_idx 0)
            if p_idx == 0:
                mkt = obs.get("market", {}) or {}
                prices = mkt.get("prices", {}) or {}
                invs = mkt.get("inventory", {}) or {}
                for prod in ALL_PRODUCTS:
                    if prod in prices:
                        price_history[prod].append(float(prices[prod]))
                    if prod in invs:
                        inv_history[prod].append(float(invs[prod]))

            farm = (obs.get("farms", []) or [{}, {}])[p_idx]
            unlocked_quads = farm.get("unlocked_quadrants", []) or []
            for q in unlocked_quads:
                if q not in quad_unlock_day:
                    quad_unlock_day[q] = day

            step_shed = dict((obs.get("private", {}) or {}).get("shed", {}) or {})
            act = step_data[p_idx].get("action", {}) or {}
            mkt_actions = act.get("market", []) or []
            for order in mkt_actions:
                if not isinstance(order, list) or len(order) < 1:
                    continue
                cmd = order[0]

                # Fixed HIRE parser: ["HIRE"] has length 1 (kaggriculture.py:539)
                if cmd == "HIRE":
                    total_hires += 1
                    if day == 0:
                        day0_hires += 1
                    continue

                if len(order) < 2:
                    continue
                item = order[1]
                qty = int(order[2]) if len(order) > 2 else 1

                if cmd == "BUY_ANIMAL":
                    animals_bought[item] += qty
                    if day == 0:
                        day0_animals[item] += qty
                elif cmd == "BUY_SEED":
                    seeds_bought[item] += qty
                    if day == 0:
                        day0_seeds[item] += qty
                elif cmd == "SELL":
                    # Bounded by actual shed contents (kaggriculture.py:642-650)
                    available = step_shed.get(item, 0) if step_shed else qty
                    actual_fill = min(qty, available)
                    if actual_fill > 0:
                        sells_by_product[item] += actual_fill
                        cur_price = float((obs.get("market", {}).get("prices", {}) or {}).get(item, 1))
                        revenue_by_product[item] += actual_fill * cur_price
                        if step_shed:
                            step_shed[item] -= actual_fill

        player_data.append({
            "name": p_name,
            "reward": p_reward,
            "won": p_won,
            "quad_unlock_day": quad_unlock_day,
            "day0_hires": day0_hires,
            "day0_seeds": dict(day0_seeds),
            "day0_animals": dict(day0_animals),
            "total_hires": total_hires,
            "animals_bought": dict(animals_bought),
            "seeds_bought": dict(seeds_bought),
            "sells_by_product": dict(sells_by_product),
            "revenue_by_product": dict(revenue_by_product),
        })

    price_stats = {}
    for prod in ALL_PRODUCTS:
        hist = price_history[prod]
        if hist:
            price_stats[prod] = {
                "min": min(hist),
                "max": max(hist),
                "mean": sum(hist) / len(hist),
                "end": hist[-1],
                "floor_steps": sum(1 for p in hist if p <= 1.0),
            }
        else:
            price_stats[prod] = {"min": 0, "max": 0, "mean": 0, "end": 0, "floor_steps": 0}

    return {
        "episode_id": episode_id,
        "shops": unlocked_shops,
        "pressure": pressure,
        "p0": player_data[0],
        "p1": player_data[1],
        "winner": winner,
        "margin": margin,
        "price_stats": price_stats,
    }


def discover_files(input_dir):
    """Scan directory and find all supported episode files."""
    print(f"=== Discovering files in {input_dir} ===")
    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    items = os.listdir(input_dir)
    print(f"Found {len(items)} top-level items in {input_dir}: {items[:10]}")

    patterns = ["*.json", "*.json.gz", "**/*.json", "**/*.json.gz"]
    files = []
    for pat in patterns:
        files.extend(glob.glob(os.path.join(input_dir, pat), recursive=True))
    files = sorted(list(set(files)))
    print(f"Discovered {len(files)} candidate episode files (.json / .json.gz).")
    return files


def run_analysis(input_dir, output_dir, max_episodes=None):
    """Run full corpus extraction and write summary CSVs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    
    files = discover_files(input_dir)
    if not files:
        raise FileNotFoundError(f"No episode JSON files discovered in {input_dir}. Ensure dataset is attached.")

    if max_episodes:
        files = files[:max_episodes]

    parsed_records = []
    for idx, f in enumerate(files):
        data = load_json_content(f)
        if data:
            res = parse_episode_data(data, source_id=os.path.splitext(os.path.basename(f))[0])
            if res:
                parsed_records.append(res)
        if (idx + 1) % 100 == 0 or (idx + 1) == len(files):
            print(f"Processed {idx + 1}/{len(files)} files (valid full episodes: {len(parsed_records)})")

    print(f"Successfully parsed {len(parsed_records)} full 720-step episodes.")
    if not parsed_records:
        raise ValueError(f"No valid 720-step episodes parsed from {len(files)} files.")

    # Apply K=15 clustering to the 8-d pressure vectors
    print("Applying K=15 clustering on 8-d demand pressure vectors...")
    cluster_demand_vectors(parsed_records, k=15)

    # 1. meta_portfolio_summary.csv
    portfolio_csv = os.path.join(output_dir, "meta_portfolio_summary.csv")
    with open(portfolio_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "episode_id", "seat", "player_name", "won", "reward", "opponent_reward",
            "day0_hires", "total_hires",
            "cows", "sheep", "geese",
            "wheat_seeds", "carrot_seeds", "tomato_seeds", "strawberry_seeds", "melon_seeds",
            "ne_unlock_day", "sw_unlock_day", "se_unlock_day",
            "milk_sold", "wool_sold", "egg_sold", "wheat_sold", "carrot_sold",
            "tomato_sold", "strawberry_sold", "melon_sold", "fert_sold",
            "pressure_wheat", "pressure_carrot", "pressure_tomato", "pressure_strawberry",
            "pressure_melon", "pressure_egg", "pressure_milk", "pressure_wool", "pressure_fert",
            "cluster_id", "shops_list"
        ])
        for rec in parsed_records:
            shops_str = "|".join(rec["shops"])
            pr = rec["pressure"]
            for seat, p in enumerate([rec["p0"], rec["p1"]]):
                opp = rec["p1"] if seat == 0 else rec["p0"]
                q = p["quad_unlock_day"]
                anim = p["animals_bought"]
                seed = p["seeds_bought"]
                sold = p["sells_by_product"]
                writer.writerow([
                    rec["episode_id"], seat, p["name"], int(p["won"]), p["reward"], opp["reward"],
                    p["day0_hires"], p["total_hires"],
                    anim.get("COW", 0), anim.get("SHEEP", 0), anim.get("GOOSE", 0),
                    seed.get("WHEAT", 0), seed.get("CARROT", 0), seed.get("TOMATO", 0), seed.get("STRAWBERRY", 0), seed.get("MELON", 0),
                    q.get("NE", -1), q.get("SW", -1), q.get("SE", -1),
                    sold.get("MILK", 0), sold.get("WOOL", 0), sold.get("EGG", 0), sold.get("WHEAT", 0), sold.get("CARROT", 0),
                    sold.get("TOMATO", 0), sold.get("STRAWBERRY", 0), sold.get("MELON", 0), sold.get("FERTILIZER", 0),
                    pr["WHEAT"], pr["CARROT"], pr["TOMATO"], pr["STRAWBERRY"],
                    pr["MELON"], pr["EGG"], pr["MILK"], pr["WOOL"], pr["FERTILIZER"],
                    rec["cluster_id"], shops_str
                ])
    print(f"Wrote {portfolio_csv}")

    # 2. realized_prices_summary.csv
    price_csv = os.path.join(output_dir, "realized_prices_summary.csv")
    with open(price_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "episode_id", "product", "min_price", "mean_price", "max_price", "end_price", "floor_steps",
            "pressure_wheat", "pressure_carrot", "pressure_tomato", "pressure_strawberry",
            "pressure_melon", "pressure_egg", "pressure_milk", "pressure_wool", "pressure_fert",
            "cluster_id", "shops_list"
        ])
        for rec in parsed_records:
            shops_str = "|".join(rec["shops"])
            pr = rec["pressure"]
            for prod, stats in rec["price_stats"].items():
                writer.writerow([
                    rec["episode_id"], prod, stats["min"], f"{stats['mean']:.2f}", stats["max"], stats["end"], stats["floor_steps"],
                    pr["WHEAT"], pr["CARROT"], pr["TOMATO"], pr["STRAWBERRY"],
                    pr["MELON"], pr["EGG"], pr["MILK"], pr["WOOL"], pr["FERTILIZER"],
                    rec["cluster_id"], shops_str
                ])
    print(f"Wrote {price_csv}")

    # 3. demand_profile_outcomes.csv (Aggregated across K=15 demand clusters)
    cluster_outcomes = defaultdict(lambda: {
        "count": 0, "p0_wins": 0, "p1_wins": 0, "ties": 0,
        "total_reward": 0.0, "total_margin": 0.0,
        "sum_pressure": defaultdict(float)
    })
    for rec in parsed_records:
        cid = rec["cluster_id"]
        st = cluster_outcomes[cid]
        st["count"] += 1
        if rec["winner"] == 0:
            st["p0_wins"] += 1
        elif rec["winner"] == 1:
            st["p1_wins"] += 1
        else:
            st["ties"] += 1
        st["total_reward"] += (rec["p0"]["reward"] + rec["p1"]["reward"])
        st["total_margin"] += rec["margin"]
        for prod, val in rec["pressure"].items():
            st["sum_pressure"][prod] += val

    profile_csv = os.path.join(output_dir, "demand_profile_outcomes.csv")
    with open(profile_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "cluster_id", "episodes_count", "p0_win_rate", "p1_win_rate", "avg_player_reward", "avg_margin",
            "avg_p_wheat", "avg_p_carrot", "avg_p_tomato", "avg_p_strawberry",
            "avg_p_melon", "avg_p_egg", "avg_p_milk", "avg_p_wool", "avg_p_fert"
        ])
        for cid, st in sorted(cluster_outcomes.items(), key=lambda x: -x[1]["count"]):
            c = st["count"]
            p_avg = {p: f"{st['sum_pressure'][p] / c:.1f}" for p in ALL_PRODUCTS}
            writer.writerow([
                f"Cluster_{cid:02d}", c, f"{st['p0_wins'] / c:.3f}", f"{st['p1_wins'] / c:.3f}",
                f"{st['total_reward'] / (2 * c):.1f}", f"{st['total_margin'] / c:.1f}",
                p_avg["WHEAT"], p_avg["CARROT"], p_avg["TOMATO"], p_avg["STRAWBERRY"],
                p_avg["MELON"], p_avg["EGG"], p_avg["MILK"], p_avg["WOOL"], p_avg["FERTILIZER"]
            ])
    print(f"Wrote {profile_csv}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        in_dir = sys.argv[1]
    else:
        kaggle_candidate = "/kaggle/input/kaggriculture-episodes-2026-08-21"
        if os.path.exists(kaggle_candidate):
            in_dir = kaggle_candidate
        elif os.path.exists("/kaggle/input"):
            in_dir = "/kaggle/input"
        else:
            print("ERROR: No input directory specified and not running in Kaggle environment.")
            print("Usage: python phase0_analysis.py <input_dataset_dir> [output_dir]")
            sys.exit(1)

    if len(sys.argv) > 2:
        out_dir = sys.argv[2]
    else:
        if os.path.exists("/kaggle/working"):
            out_dir = "/kaggle/working"
        else:
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            out_dir = os.path.join(root, "results")

    print(f"Starting Phase 0 Meta Analysis: input={in_dir}, output={out_dir}")
    run_analysis(in_dir, out_dir)
