import sys
import os
from kaggle_environments import make

# Setup agent paths
agent_dir = r'C:\Coding\kaggriculture_architecture\extracted_notebook_agent\agents'
if agent_dir not in sys.path:
    sys.path.insert(0, agent_dir)

import e777a_apex_preemption as e777
import e776a_engine_exact_latent_pasture as e776

agent_v50_path = r'C:\Coding\kaggriculture_architecture\submission\main.py'
with open(agent_v50_path, 'r', encoding='utf-8') as f:
    v50_code = f.read()

globs = {}
exec(v50_code, globs)
agent_v50 = globs['agent']

def run_head_to_head(agentA, agentB, seeds, labelA, labelB):
    print(f"\n{'='*75}")
    print(f"HEAD-TO-HEAD: {labelA} vs {labelB}")
    print(f"{'='*75}")
    
    winsA = 0
    winsB = 0
    total_marginA = 0.0
    
    for s in seeds:
        # Match 1: A as P0, B as P1
        env1 = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env1.run([agentA, agentB])
        r1_A = env1.steps[-1][0].get("reward", 0)
        r1_B = env1.steps[-1][1].get("reward", 0)
        
        # Match 2: B as P0, A as P1
        env2 = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        env2.run([agentB, agentA])
        r2_B = env2.steps[-1][0].get("reward", 0)
        r2_A = env2.steps[-1][1].get("reward", 0)
        
        diff1 = r1_A - r1_B
        diff2 = r2_A - r2_B
        net_adv = (diff1 + diff2) / 2.0
        total_marginA += net_adv
        
        if net_adv > 0: winsA += 1
        elif net_adv < 0: winsB += 1
        
        print(f"Seed {s:<6} | P0 Adv: {diff1:>+8.1f} | P1 Adv: {diff2:>+8.1f} | Net {labelA} Adv: {net_adv:>+8.1f}")
        
    avg_margin = total_marginA / len(seeds)
    print(f"\nSummary: {labelA} Won {winsA}/{len(seeds)} Seeds | Average Margin: {avg_margin:>+8.1f}")

if __name__ == '__main__':
    seeds = [42, 7, 1234, 555, 100, 202]
    run_head_to_head(e777.agent, e776.agent, seeds, "God Mode v3 (e777)", "Notebook (e776)")
    run_head_to_head(e777.agent, agent_v50, seeds, "God Mode v3 (e777)", "Incumbent (v50)")
