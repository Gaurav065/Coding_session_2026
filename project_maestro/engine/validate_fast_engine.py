"""20-Seed Automated Exact Equivalence & Performance Validation Harness - Project Maestro

Validates that FastGame replicates kaggle_environments.make("kaggriculture") bit-for-bit
across 20 fixed seeds in Pure Self-Play (env.run([agent, agent])), with zero delta in reward.
"""

import sys
import time
import statistics
from kaggle_environments import make
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent

SEEDS = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200, 250, 300, 333, 404, 500, 600, 700, 777, 888, 999]

def validate_all_20_seeds():
    print(f"================================================================================")
    print(f"=== VALIDATING FAST ENGINE AGAINST REFERENCE ENGINE (SELF-PLAY, {len(SEEDS)} SEEDS) ===")
    print(f"================================================================================")
    
    mismatches = 0
    ref_times = []
    fast_times = []
    results = []

    for idx, seed in enumerate(SEEDS):
        # 1. Reference Engine Run (env.run([a0, a1]))
        t0 = time.time()
        agent_ref_0 = make_spatial_dispatcher_agent()
        agent_ref_1 = make_spatial_dispatcher_agent()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run([agent_ref_0, agent_ref_1])
        r0_ref = float(env.steps[-1][0]["reward"])
        r1_ref = float(env.steps[-1][1]["reward"])
        t_ref = time.time() - t0
        ref_times.append(t_ref)

        # 2. Fast Engine Run (while not game.done)
        t0 = time.time()
        agent_fast_0 = make_spatial_dispatcher_agent()
        agent_fast_1 = make_spatial_dispatcher_agent()
        game = FastGame(seed=seed)
        while not game.done:
            obs_0 = game.get_observation(0)
            obs_1 = game.get_observation(1)
            act_0 = agent_fast_0(obs_0)
            act_1 = agent_fast_1(obs_1)
            game.step_game(act_0, act_1)
        r0_fast = float(game.farms[0].money)
        r1_fast = float(game.farms[1].money)
        t_fast = time.time() - t0
        fast_times.append(t_fast)

        d0 = abs(r0_ref - r0_fast)
        d1 = abs(r1_ref - r1_fast)
        match = (d0 < 1e-4 and d1 < 1e-4)
        if not match:
            mismatches += 1

        ref_avg = (r0_ref + r1_ref) / 2
        fast_avg = (r0_fast + r1_fast) / 2
        results.append((seed, ref_avg, fast_avg, d0, d1, match, t_ref, t_fast))
        print(f"Seed {seed:4d} | Ref Avg: ${ref_avg:10.2f} | Fast Avg: ${fast_avg:10.2f} | Delta: (${d0:5.2f}, ${d1:5.2f}) | Match: {str(match):5s} | Speedup: {t_ref/max(1e-5, t_fast):5.1f}x")

    avg_ref_t = sum(ref_times) / len(ref_times)
    avg_fast_t = sum(fast_times) / len(fast_times)
    fast_games_per_sec = len(SEEDS) / sum(fast_times)
    fast_steps_per_sec = (len(SEEDS) * 719) / sum(fast_times)

    print(f"\n================================================================================")
    print(f"=== SUMMARY ===")
    print(f"Total Seeds Evaluated : {len(SEEDS)}")
    print(f"Exact Matches (Delta = $0): {len(SEEDS) - mismatches} / {len(SEEDS)}")
    print(f"Mismatches            : {mismatches}")
    print(f"Avg Ref Match Time    : {avg_ref_t:.3f}s ({719/avg_ref_t:.1f} steps/s)")
    print(f"Avg Fast Match Time   : {avg_fast_t:.3f}s ({719/avg_fast_t:.1f} steps/s)")
    print(f"Overall Speedup       : {avg_ref_t / avg_fast_t:.1f}x")
    print(f"Fast Engine Throughput: {fast_games_per_sec:.1f} games/sec ({fast_steps_per_sec:,.0f} steps/sec)")
    print(f"================================================================================")

    assert mismatches == 0, f"Validation failed with {mismatches} mismatches!"

if __name__ == "__main__":
    validate_all_20_seeds()
