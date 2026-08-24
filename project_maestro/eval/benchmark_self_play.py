"""Canonical 20-seed self-play benchmark - Project Maestro.

Standing evaluation harness (see README.md's `eval/` folder definition). Measures pure
self-play performance: env.run([agent, agent]) across 20 fixed seeds. This is the
headline benchmark for this project -- an earlier round was invalidated when it was run
against an unnamed do-nothing opponent instead of self-play, so ALWAYS report this, not
a diagnostic-ceiling number, as the primary result.
"""

import time
import statistics
from kaggle_environments import make
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

SEEDS = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200, 250, 300, 333, 404, 500, 600, 700, 777, 888, 999]


def benchmark_self_play(seeds=SEEDS):
    print("=" * 80)
    print("=== PURE SELF-PLAY BENCHMARK: env.run([agent, agent]) OVER 20 FIXED SEEDS ===")
    print("=" * 80)

    p0_rewards = []
    p1_rewards = []
    avg_rewards = []

    for seed in seeds:
        t0 = time.time()
        agent0 = make_spatial_dispatcher_agent()
        agent1 = make_spatial_dispatcher_agent()

        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([agent0, agent1])

        r0 = float(env.steps[-1][0]["reward"])
        r1 = float(env.steps[-1][1]["reward"])
        r_avg = (r0 + r1) / 2.0
        elapsed = time.time() - t0

        p0_rewards.append(r0)
        p1_rewards.append(r1)
        avg_rewards.append(r_avg)

        print(f"Seed {seed:>4} | P0: ${r0:>10,.2f} | P1: ${r1:>10,.2f} | Match Avg: ${r_avg:>10,.2f} | Time: {elapsed:>5.2f}s", flush=True)

    print("=" * 80)
    print("=== 20-SEED SELF-PLAY SUMMARY STATISTICS ===")
    print("=" * 80)
    print(f"P0 Mean Reward    : ${statistics.mean(p0_rewards):>12,.2f} (Median: ${statistics.median(p0_rewards):>10,.2f}, Min: ${min(p0_rewards):>10,.2f}, Max: ${max(p0_rewards):>10,.2f})")
    print(f"P1 Mean Reward    : ${statistics.mean(p1_rewards):>12,.2f} (Median: ${statistics.median(p1_rewards):>10,.2f}, Min: ${min(p1_rewards):>10,.2f}, Max: ${max(p1_rewards):>10,.2f})")
    all_rewards = p0_rewards + p1_rewards
    print(f"Overall Player Mean: ${statistics.mean(all_rewards):>11,.2f} (Median: ${statistics.median(all_rewards):>10,.2f})")
    print(f"Match Average Mean : ${statistics.mean(avg_rewards):>11,.2f} (Median: ${statistics.median(avg_rewards):>10,.2f}, Min: ${min(avg_rewards):>10,.2f}, Max: ${max(avg_rewards):>10,.2f})")
    print("=" * 80)
    return {"p0": p0_rewards, "p1": p1_rewards, "avg": avg_rewards}


if __name__ == "__main__":
    benchmark_self_play()
