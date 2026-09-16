#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""High-Throughput Parallel Tournament Runner for Apple Silicon M3.

Utilizes all M3 Performance and Efficiency cores via ProcessPoolExecutor
to benchmark self-play, opponent counter-play, and multi-seed stability.
"""

import argparse
import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path

# Add repository root to path
ROOT = Path(__file__).resolve().parent.parent
KAGGLE_DIR = ROOT / "kaggriculture_architecture"
if str(KAGGLE_DIR) not in sys.path:
    sys.path.insert(0, str(KAGGLE_DIR))

import kaggle_environments
from modular_apex.main import agent as modular_agent

def simulate_single_match(seed, seat0_name="modular_apex", seat1_name="pass"):
    """Simulates a single 720-step match and returns full telemetry."""
    try:
        t0 = time.perf_counter()
        env = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        
        # Build agent instances
        # In multi-processing, each process imports cleanly
        p0 = modular_agent if seat0_name == "modular_apex" else "pass"
        p1 = modular_agent if seat1_name == "modular_apex" else "pass"
        
        env.run([p0, p1])
        elapsed = time.perf_counter() - t0
        
        step_final = env.steps[-1]
        r0 = step_final[0]["reward"] or 0
        r1 = step_final[1]["reward"] or 0
        status0 = step_final[0]["status"]
        status1 = step_final[1]["status"]
        
        shed0 = step_final[0]["observation"]["private"]["shed"]
        trapped_cows = shed0.get("COW", 0)
        trapped_sheep = shed0.get("SHEEP", 0)
        
        return {
            "seed": seed,
            "reward_seat0": r0,
            "reward_seat1": r1,
            "margin": r0 - r1,
            "win_seat0": r0 > r1,
            "status0": status0,
            "trapped_cows": trapped_cows,
            "trapped_sheep": trapped_sheep,
            "elapsed_sec": elapsed,
            "steps_per_sec": 720 / max(0.001, elapsed)
        }
    except Exception as e:
        return {
            "seed": seed,
            "error": str(e),
            "reward_seat0": 0,
            "reward_seat1": 0,
            "win_seat0": False
        }

def run_tournament(matches=50, max_workers=None, mode="pass"):
    cores = max_workers or os.cpu_count() or 8
    print("=" * 75)
    print(f"STARTING PARALLEL TOURNAMENT ON APPLE SILICON M3 ({cores} CORES)")
    print(f"Total Matches: {matches} | Matchup Mode: modular_apex vs {mode}")
    print("=" * 75)
    
    seeds = [42 + i * 1337 for i in range(matches)]
    seat1_name = "modular_apex" if mode == "self_play" else "pass"
    
    t_start = time.perf_counter()
    results = []
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=cores) as executor:
        futures = {executor.submit(simulate_single_match, s, "modular_apex", seat1_name): s for s in seeds}
        completed = 0
        
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results.append(res)
            completed += 1
            r0 = res.get("reward_seat0", 0)
            el = res.get("elapsed_sec", 0)
            sys.stdout.write(f"\rProgress: [{completed:3d}/{matches:3d}] | Last Match: Seed {res['seed']} -> ${r0:,.0f} ({el:.2f}s)")
            sys.stdout.flush()

    total_time = time.perf_counter() - t_start
    print("\n" + "=" * 75)
    print("TOURNAMENT RESULTS SUMMARY")
    print("=" * 75)
    
    valid_scores = [r["reward_seat0"] for r in results if "reward_seat0" in r and not r.get("error")]
    wins = sum(1 for r in results if r.get("win_seat0"))
    trapped_total = sum(r.get("trapped_cows", 0) + r.get("trapped_sheep", 0) for r in results)
    
    avg_score = sum(valid_scores) / len(valid_scores) if valid_scores else 0
    max_score = max(valid_scores) if valid_scores else 0
    min_score = min(valid_scores) if valid_scores else 0
    
    print(f"Total Execution Time      : {total_time:.2f} seconds")
    print(f"Throughput                : {matches / total_time:.2f} games/second ({matches * 720 / total_time:.1f} steps/sec)")
    print(f"Average Score (Seat 0)    : ${avg_score:,.0f}")
    print(f"Max Score                 : ${max_score:,.0f}")
    print(f"Min Score                 : ${min_score:,.0f}")
    print(f"Win Rate vs {mode.upper():<13}: {wins}/{matches} ({wins/matches*100:.1f}%)")
    print(f"Total Trapped Animals     : {trapped_total} (must be 0)")
    print("=" * 75)
    
    # Save output to JSON
    out_file = Path(__file__).resolve().parent / "tournament_results.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({
            "matches": matches,
            "cores": cores,
            "total_time_sec": total_time,
            "avg_score": avg_score,
            "max_score": max_score,
            "min_score": min_score,
            "win_rate": wins / matches,
            "trapped_animals": trapped_total,
            "details": results
        }, f, indent=2)
    print(f"Full results saved to: {out_file.name}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Apple Silicon M3 Tournament Runner")
    parser.add_argument("--matches", type=int, default=20, help="Number of matches to simulate")
    parser.add_argument("--cores", type=int, default=None, help="Number of CPU cores to utilize")
    parser.add_argument("--mode", type=str, default="pass", choices=["pass", "self_play"], help="Opponent mode")
    args = parser.parse_args()
    
    run_tournament(matches=args.matches, max_workers=args.cores, mode=args.mode)
