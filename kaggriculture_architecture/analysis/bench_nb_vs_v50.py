import os
import sys
import time
from kaggle_environments import make

def test_notebook_agent_vs_v50(seeds):
    agent_nb = r'C:\Coding\kaggriculture_architecture\extracted_notebook_agent\main.py'
    agent_v50 = r'C:\Coding\kaggriculture_architecture\submission\main.py'
    
    print("="*80)
    print("BENCHMARKING EXTRACTED NOTEBOOK AGENT (e776) VS CURRENT SUBMISSION (v50)")
    print("="*80)
    
    # Run both seat positions
    for s in seeds:
        envA = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        envA.run([agent_nb, agent_v50])
        rA_nb = envA.steps[-1][0].get("reward", 0)
        rA_v50 = envA.steps[-1][1].get("reward", 0)
        
        envB = make("kaggriculture", configuration={"episodeSteps": 720, "seed": s})
        envB.run([agent_v50, agent_nb])
        rB_v50 = envB.steps[-1][0].get("reward", 0)
        rB_nb = envB.steps[-1][1].get("reward", 0)
        
        diffA = rA_nb - rA_v50 # nb advantage as P0
        diffB = rB_nb - rB_v50 # nb advantage as P1
        net_adv = (diffA + diffB) / 2.0
        
        print(f"Seed {s:<6} | Seat A (e776 as P0): {diffA:>+8.1f} | Seat B (e776 as P1): {diffB:>+8.1f} | Net e776 Adv: {net_adv:>+8.1f}")

if __name__ == '__main__':
    test_notebook_agent_vs_v50([42, 7, 1234, 555, 100, 202])
