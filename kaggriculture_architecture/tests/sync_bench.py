import os
import sys
import time
from kaggle_environments import make

def run_bench_sync(agent0_path, agent1_path, seeds):
    name0 = os.path.basename(agent0_path)
    name1 = os.path.basename(agent1_path)
    print(f"\n=======================================================", flush=True)
    print(f"BENCHMARK: {name0} (P0) vs {name1} (P1) across {len(seeds)} seeds", flush=True)
    print(f"=======================================================", flush=True)
    
    with open(agent0_path, 'r', encoding='utf-8') as f:
        c0 = f.read()
    with open(agent1_path, 'r', encoding='utf-8') as f:
        c1 = f.read()
        
    p0_wins = 0
    p1_wins = 0
    ties = 0
    p0_scores = []
    p1_scores = []
    
    for s in seeds:
        t0 = time.time()
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env.run([c0, c1])
        elapsed = time.time() - t0
        
        step0 = env.steps[-1][0]
        step1 = env.steps[-1][1]
        r0 = step0.get("reward", 0)
        r1 = step1.get("reward", 0)
        s0 = step0.get("status", "UNKNOWN")
        s1 = step1.get("status", "UNKNOWN")
        
        p0_scores.append(r0)
        p1_scores.append(r1)
        diff = r0 - r1
        
        if r0 > r1:
            p0_wins += 1
            res_str = "P0 WIN"
        elif r1 > r0:
            p1_wins += 1
            res_str = "P1 WIN"
        else:
            ties += 1
            res_str = "TIE"
            
        print(f"Seed {s:<4} | P0: {r0:>8.1f} ({s0}) vs P1: {r1:>8.1f} ({s1}) | Diff: {diff:>+8.1f} | {res_str} ({elapsed:.1f}s)", flush=True)
        
    avg_r0 = sum(p0_scores) / len(p0_scores)
    avg_r1 = sum(p1_scores) / len(p1_scores)
    avg_diff = avg_r0 - avg_r1
    print("-" * 70, flush=True)
    print(f"SUMMARY: {name0} Wins: {p0_wins}/{len(seeds)} ({p0_wins/len(seeds)*100:.1f}%), {name1} Wins: {p1_wins}/{len(seeds)}, Ties: {ties}", flush=True)
    print(f"AVERAGE SCORES: P0 = {avg_r0:,.1f} | P1 = {avg_r1:,.1f} | Avg Diff = {avg_diff:+,.1f}", flush=True)
    print("-" * 70, flush=True)

if __name__ == '__main__':
    agent_v50 = r'C:\Coding\main_v50_phase_batch.py'
    agent_restore = r'C:\Coding\main_restore.py'
    agent_main2 = r'C:\Users\GauravPatel\Downloads\main (2).py'
    
    seeds = [1, 2, 3, 4, 5, 42, 100, 101, 202, 303]
    
    # 1. Test v50 vs Restore
    run_bench_sync(agent_v50, agent_restore, seeds)
    # 2. Test v50 as P1 vs Restore as P0
    run_bench_sync(agent_restore, agent_v50, seeds)
