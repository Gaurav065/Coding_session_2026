"""Tournament Benchmarking Suite for Project Aegis

Evaluates Project Aegis over 10 matches across diverse random seeds against:
1. Starter Baseline Agent
2. Random Agent
3. Decoded Top-100 Agent
"""

import sys
sys.path.insert(0, r'C:\Coding')
sys.path.insert(0, r'C:\Users\GauravPatel\Downloads\multi_route_agent_files')

from kaggle_environments import make
from project_aegis.main import agent as aegis_agent
from decoded_agent import agent as decoded_agent

SEEDS = [1, 7, 13, 24, 42, 100, 2024, 7777, 9999, 12345]

def run_tournament():
    print("=== PROJECT AEGIS BENCHMARK TOURNAMENT (10 MATCHES) ===")
    
    # 1. Aegis vs Starter
    print("\n--- 1. AEGIS vs STARTER ---")
    starter_scores = []
    for seed in SEEDS[:5]:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
        env.run([aegis_agent, "starter"])
        p0 = env.steps[-1][0]["reward"]
        p1 = env.steps[-1][1]["reward"]
        starter_scores.append(p0)
        print(f"Seed {seed:5d}: Aegis = {p0:10,.0f} | Starter = {p1:6,.0f} | Margin = +{p0-p1:10,.0f}")
    print(f"Aegis Average vs Starter: {sum(starter_scores)/len(starter_scores):,.0f}")

    # 2. Aegis vs Random
    print("\n--- 2. AEGIS vs RANDOM ---")
    random_scores = []
    for seed in SEEDS[:5]:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
        env.run([aegis_agent, "random"])
        p0 = env.steps[-1][0]["reward"]
        p1 = env.steps[-1][1]["reward"]
        random_scores.append(p0)
        print(f"Seed {seed:5d}: Aegis = {p0:10,.0f} | Random  = {p1:6,.0f} | Margin = +{p0-p1:10,.0f}")
    print(f"Aegis Average vs Random: {sum(random_scores)/len(random_scores):,.0f}")

    # 3. Aegis vs Decoded Top-100 Agent (Sparring Match)
    print("\n--- 3. AEGIS vs DECODED TOP-100 (HEAD-TO-HEAD) ---")
    h2h_scores = []
    for seed in SEEDS[:5]:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=True)
        env.run([aegis_agent, decoded_agent])
        p0 = env.steps[-1][0]["reward"]
        p1 = env.steps[-1][1]["reward"]
        winner = "AEGIS" if p0 > p1 else ("DECODED" if p1 > p0 else "TIE")
        h2h_scores.append((p0, p1))
        print(f"Seed {seed:5d}: Aegis = {p0:10,.0f} | Decoded = {p1:10,.0f} | Winner: {winner}")

if __name__ == "__main__":
    run_tournament()
