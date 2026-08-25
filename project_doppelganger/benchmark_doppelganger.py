import sys
import os

sys.path.insert(0, r'C:\Coding\project_doppelganger')
from kaggle_environments import make
from main import agent as doppelganger_agent

test_seeds = [1, 7, 13, 24, 42, 55, 100, 144, 2024, 65536]

print("=" * 80)
print("BENCHMARKING PROJECT DOPPELGANGER STANDALONE MAIN.PY")
print("=" * 80)

scores_starter = []
margins_starter = []

for seed in test_seeds:
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed, "runTimeout": 60})
    env.run([doppelganger_agent, "starter"])
    p0 = env.steps[-1][0]["reward"]
    p1 = env.steps[-1][1]["reward"]
    status = env.steps[-1][0]["status"]
    scores_starter.append(p0)
    margins_starter.append(p0 - p1)
    print(f"Seed {seed:05d} vs Starter: Doppelganger = ${p0:>8,.0f} | Starter = ${p1:>5,.0f} | Margin = +${p0-p1:>8,.0f} | Status = {status}")

avg_score = sum(scores_starter) / len(scores_starter)
peak_score = max(scores_starter)
avg_margin = sum(margins_starter) / len(margins_starter)

print("=" * 80)
print(f"PROJECT DOPPELGANGER AVERAGE VS STARTER: ${avg_score:>10,.0f}")
print(f"PROJECT DOPPELGANGER PEAK SCORE:         ${peak_score:>10,.0f}")
print(f"PROJECT DOPPELGANGER AVERAGE WIN MARGIN: +${avg_margin:>10,.0f}")
print("=" * 80)
