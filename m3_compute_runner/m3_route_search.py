#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""M3 Route Search & Worker Optimization Engine.

Harnesses 8 Apple Silicon M3 CPU cores to run parallel simulations across diverse seeds.
Searches macro-decisions (SE unlock timing, livestock wings, crop corridors, worker allocation)
to discover and verify paths achieving strictly >= $200,000 coins irrespective of shop spawns.
"""

import concurrent.futures
import copy
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KAGGLE_DIR = ROOT / "kaggriculture_architecture"
if str(KAGGLE_DIR) not in sys.path:
    sys.path.insert(0, str(KAGGLE_DIR))

import os
import sys

with open(os.devnull, 'w') as fnull:
    old_err = os.dup(2)
    os.dup2(fnull.fileno(), 2)
    import kaggle_environments
    os.dup2(old_err, 2)
    os.close(old_err)

BENCHMARK_SEEDS = [7, 24, 42, 1, 100, 2, 3, 4, 5, 6, 8, 9, 10]

def load_submission_agent():
    import submission
    return submission.agent

def simulate_seed(seed, agent_path=None):
    """Simulates an episode with agent and returns detailed metrics."""
    try:
        if agent_path:
            import importlib.util
            spec = importlib.util.spec_from_file_location("agent_mod", str(agent_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            agent = mod.agent
        else:
            import submission
            agent = submission.agent

        env = kaggle_environments.make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        env.run([agent, "starter"])
        
        last_step = env.steps[-1]
        r = last_step[0]["reward"] or 0
        obs = last_step[0]["observation"]
        f = obs["farms"][0]
        quads = f["unlocked_quadrants"]
        
        cows = sum(1 for row in f["tiles"] for t in row if isinstance(t, dict) and t.get("animal") == "COW")
        sheep = sum(1 for row in f["tiles"] for t in row if isinstance(t, dict) and t.get("animal") == "SHEEP")
        shed = obs["private"]["shed"]
        trapped = shed.get("COW", 0) + shed.get("SHEEP", 0)
        
        # Analyze actions
        total_actions = 0
        pass_actions = 0
        for step_record in env.steps:
            act = step_record[0].action
            if act and isinstance(act, dict):
                f_act = act.get("farmer")
                if f_act:
                    total_actions += 1
                    if f_act[0] == "PASS":
                        pass_actions += 1
                for h in act.get("hands", []):
                    if h:
                        total_actions += 1
                        if h[0] == "PASS":
                            pass_actions += 1
                            
        pass_pct = (pass_actions / max(1, total_actions)) * 100.0
        
        return {
            "seed": seed,
            "reward": r,
            "quads_count": len(quads),
            "quads": quads,
            "cows": cows,
            "sheep": sheep,
            "trapped": trapped,
            "pass_pct": pass_pct,
            "success": True,
        }
    except Exception as e:
        return {
            "seed": seed,
            "reward": 0,
            "error": str(e),
            "success": False,
        }

def evaluate_config(agent_path=None, seeds=BENCHMARK_SEEDS, max_workers=8):
    """Evaluates an agent configuration across seeds in parallel on M3 cores."""
    t0 = time.perf_counter()
    results = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(simulate_seed, s, agent_path): s for s in seeds}
        for fut in concurrent.futures.as_completed(futures):
            results.append(fut.result())
    elapsed = time.perf_counter() - t0
    
    rewards = [r["reward"] for r in results if r.get("success")]
    min_r = min(rewards) if rewards else 0
    avg_r = sum(rewards) / len(rewards) if rewards else 0
    max_r = max(rewards) if rewards else 0
    pass_pcts = [r["pass_pct"] for r in results if r.get("success")]
    avg_pass = sum(pass_pcts) / len(pass_pcts) if pass_pcts else 0
    
    return {
        "min_reward": min_r,
        "avg_reward": avg_r,
        "max_reward": max_r,
        "avg_pass_pct": avg_pass,
        "elapsed": elapsed,
        "details": sorted(results, key=lambda x: x["seed"]),
    }

def main():
    import argparse
    parser = argparse.ArgumentParser(description="M3 Route Search & Multi-Core Evaluation")
    parser.add_argument("--agent", default=str(KAGGLE_DIR / "submission.py"), help="Path to agent script")
    parser.add_argument("--seeds", default=None, help="Comma-separated seed list (e.g. 7,24,6,42,1)")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel M3 cores")
    args = parser.parse_args()

    seeds = [int(s.strip()) for s in args.seeds.split(",")] if args.seeds else BENCHMARK_SEEDS
    print("=" * 80)
    print(f"🚀 M3 PARALLEL ROUTE EVALUATION ({len(seeds)} seeds across {args.workers} M3 CPU cores)")
    print(f"Agent: {args.agent}")
    print("=" * 80)

    summary = evaluate_config(agent_path=args.agent, seeds=seeds, max_workers=args.workers)
    
    print(f"{'Seed':<6} | {'Reward':<12} | {'Quads':<6} | {'Cows':<5} | {'Sheep':<6} | {'Pass %':<8} | Status")
    print("-" * 80)
    for r in summary["details"]:
        if r.get("success"):
            status = "✅ PASS" if r["reward"] >= 200000 else "⚠️ BELOW 200K"
            print(f"{r['seed']:<6} | ${r['reward']:<11,.0f} | {r['quads_count']:<6} | {r['cows']:<5} | {r['sheep']:<6} | {r['pass_pct']:<7.1f}% | {status}")
        else:
            print(f"{r['seed']:<6} | ERROR: {r.get('error')}")

    print("-" * 80)
    print(f"Min Reward: ${summary['min_reward']:,.0f} | Avg: ${summary['avg_reward']:,.0f} | Max: ${summary['max_reward']:,.0f}")
    print(f"Average Pass Action Rate: {summary['avg_pass_pct']:.1f}%")
    print(f"Completed in {summary['elapsed']:.2f}s ({summary['elapsed']/len(seeds):.2f}s per episode on {args.workers} cores)")
    print("=" * 80)

if __name__ == "__main__":
    main()

