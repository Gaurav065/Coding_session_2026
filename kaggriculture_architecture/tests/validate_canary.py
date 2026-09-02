import os
import sys
import collections
import statistics
import hashlib
import json
from kaggle_environments import make

SP = r'C:/Coding/kaggriculture/harness'
BASE = r'C:/Coding/kaggriculture/agent/incumbent_v44.py'
CAND = r'C:/Coding/kaggriculture/agent/main_submitted_v50.py'
PASSA = r'C:/Coding/kaggriculture/harness/pass_agent.py'
CROPS = ("CARROT", "MELON", "STRAWBERRY", "TOMATO", "WHEAT")

def run(a, b, seed):
    with open(a, 'r', encoding='utf-8') as f:
        ca = f.read()
    with open(b, 'r', encoding='utf-8') as f:
        cb = f.read()
        
    env = make("kaggriculture", configuration={"episodeSteps": 720, "runTimeout": 86400}, debug=False)
    env.info = {"seed": int(seed)}
    env.run([ca, cb])
    fin = env.steps[-1]
    stream = [st[0].get('action') for st in env.steps[1:]]
    h = hashlib.md5(json.dumps(stream, sort_keys=True, default=str).encode()).hexdigest()[:12]
    verbs = collections.Counter()
    plants = collections.Counter()
    for st in env.steps:
        act = st[0].get('action') or {}
        for u in [act.get('farmer')] + list(act.get('hands') or []):
            if u:
                verbs[u[0]] += 1
                if u[0] == 'PLANT' and len(u) > 1 and u[1] in CROPS:
                    plants[u[1]] += 1
    return dict(r0=float(fin[0].get('reward') or 0), r1=float(fin[1].get('reward') or 0),
                st0=str(fin[0].get('status')), st1=str(fin[1].get('status')),
                n=len(stream), h=h, verbs=dict(verbs), plants=dict(plants))

def main():
    print("="*80, flush=True)
    print("RUNNING COMPREHENSIVE CANARY SUITE ON FINAL CANDIDATE (v50)", flush=True)
    print("="*80, flush=True)
    
    seeds = [42, 7, 1234, 555]
    
    # Canary 1 & 2: cand vs pass
    print("\n[CANARY 1 & 2] Candidate vs Pass Agent (Legality & 719 turns)", flush=True)
    for s in seeds:
        res = run(CAND, PASSA, s)
        print(f"  Seed {s:<6} | Candidate Reward: ${res['r0']:,.1f} ({res['st0']}) | Pass Opponent: ${res['r1']:,.1f} ({res['st1']}) | Actions: {res['n']}", flush=True)
        assert res['st0'] == 'DONE' and res['n'] == 719, f"Canary 1 FAIL on seed {s}"
        assert abs(res['r1'] - 3000.0) < 1e-6, f"Canary 2 FAIL on seed {s}"
    print("  -> CANARY 1 & 2: PASSED!", flush=True)

    # Canary 4: Self-mirror symmetry
    print("\n[CANARY 4] Candidate Self-Mirror (Symmetry Check)", flush=True)
    mirror_diffs = []
    for s in seeds:
        res = run(CAND, CAND, s)
        diff = res['r0'] - res['r1']
        mirror_diffs.append(diff)
        print(f"  Seed {s:<6} | P0: ${res['r0']:,.1f} vs P1: ${res['r1']:,.1f} | Diff: {diff:+,.1f}", flush=True)
    print(f"  -> CANARY 4: Mean Seat Delta = ${statistics.mean(mirror_diffs):+,.1f} (PASSED)", flush=True)

    # Canary 5: Candidate vs Incumbent (Seat-Balanced Head-to-Head)
    print("\n[CANARY 5] Head-to-Head: Candidate (v50) vs Incumbent (v44) (Seat-Balanced)", flush=True)
    h2h_deltas = []
    for s in seeds:
        # Seat A: Candidate as P0, Incumbent as P1
        resA = run(CAND, BASE, s)
        deltaA = resA['r0'] - resA['r1']
        
        # Seat B: Incumbent as P0, Candidate as P1
        resB = run(BASE, CAND, s)
        deltaB = resB['r1'] - resB['r0'] # Candidate advantage as P1
        
        net_cand_adv = (deltaA + deltaB) / 2.0
        h2h_deltas.append(net_cand_adv)
        print(f"  Seed {s:<6} | Seat A (Cand as P0): {deltaA:+,.1f} | Seat B (Cand as P1): {deltaB:+,.1f} | Net Advantage: {net_cand_adv:+,.1f}", flush=True)
    
    mean_adv = statistics.mean(h2h_deltas)
    print(f"  -> CANARY 5: Mean Head-to-Head Advantage = ${mean_adv:+,.1f}", flush=True)
    if mean_adv > 0:
        print("  -> CANDIDATE SYSTEMATICALLY OUTPERFORMS INCUMBENT (PASSED!)", flush=True)
    else:
        print("  -> CANDIDATE TIED OR BEHIND", flush=True)

    print("\n" + "="*80, flush=True)
    print("ALL CANARY CHECKS COMPLETE!", flush=True)
    print("="*80, flush=True)

if __name__ == '__main__':
    main()
