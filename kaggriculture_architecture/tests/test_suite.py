import os
import sys
from concurrent.futures import ProcessPoolExecutor
from kaggle_environments import make

def run_single_game(args):
    agent0_path, agent1_path, seed = args
    try:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
        # Read code for both
        with open(agent0_path, 'r', encoding='utf-8') as f:
            c0 = f.read()
        with open(agent1_path, 'r', encoding='utf-8') as f:
            c1 = f.read()
        env.run([c0, c1])
        
        step0 = env.steps[-1][0]
        step1 = env.steps[-1][1]
        r0 = step0.get("reward", 0)
        r1 = step1.get("reward", 0)
        s0 = step0.get("status", "UNKNOWN")
        s1 = step1.get("status", "UNKNOWN")
        
        return {
            "seed": seed,
            "r0": r0,
            "r1": r1,
            "s0": s0,
            "s1": s1,
            "diff": r0 - r1
        }
    except Exception as e:
        return {"seed": seed, "error": str(e)}

def run_benchmark(agent0_path, agent1_path, seeds, max_workers=6):
    name0 = os.path.basename(agent0_path)
    name1 = os.path.basename(agent1_path)
    print(f"\n" + "="*80)
    print(f"BENCHMARK: {name0} (P0) vs {name1} (P1) across {len(seeds)} seeds")
    print("="*80)
    
    tasks = [(agent0_path, agent1_path, s) for s in seeds]
    results = []
    
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        for res in executor.map(run_single_game, tasks):
            results.append(res)
            if "error" in res:
                print(f"Seed {res['seed']}: ERROR -> {res['error']}")
            else:
                p0_win = "P0 WIN" if res['r0'] > res['r1'] else ("P1 WIN" if res['r1'] > res['r0'] else "TIE")
                print(f"Seed {res['seed']:<4} | P0: {res['r0']:>8.1f} ({res['s0']}) vs P1: {res['r1']:>8.1f} ({res['s1']}) | Diff: {res['diff']:>+8.1f} | {p0_win}")

    valid = [r for r in results if "error" not in r]
    if valid:
        p0_wins = sum(1 for r in valid if r['r0'] > r['r1'])
        p1_wins = sum(1 for r in valid if r['r1'] > r['r0'])
        ties = sum(1 for r in valid if r['r0'] == r['r1'])
        avg_r0 = sum(r['r0'] for r in valid) / len(valid)
        avg_r1 = sum(r['r1'] for r in valid) / len(valid)
        avg_diff = sum(r['diff'] for r in valid) / len(valid)
        print("-" * 80)
        print(f"SUMMARY: {name0} Wins: {p0_wins}/{len(valid)} ({p0_wins/len(valid)*100:.1f}%), {name1} Wins: {p1_wins}/{len(valid)}, Ties: {ties}")
        print(f"AVERAGE SCORES: P0 = {avg_r0:,.1f} | P1 = {avg_r1:,.1f} | Avg Diff = {avg_diff:+,.1f}")
        print("-" * 80)
    return results

if __name__ == '__main__':
    seeds = list(range(100, 120)) # 20 seeds
    
    agent_p50 = r'C:\Coding\main_v50_phase_batch.py'
    agent_restore = r'C:\Coding\main_restore.py'
    agent_main2 = r'C:\Users\GauravPatel\Downloads\main (2).py'
    
    print("Starting comprehensive validation suite...")
    # Test 1: v50 vs Restore
    run_benchmark(agent_p50, agent_restore, seeds, max_workers=6)
    # Test 2: Reverse seats (Restore as P0, v50 as P1)
    run_benchmark(agent_restore, agent_p50, seeds, max_workers=6)
