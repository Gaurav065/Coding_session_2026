"""Offline tape generation: play ONE full game with the smart (land-dev) agent
against a realistic sparring opponent (our own verified baseline), record the smart
agent's own per-step actions, and save that recording as a new candidate tape.

Run once, in a fresh process -- this is exactly the kind of one-shot offline
generation that has no runtime budget, unlike running the smart logic live.
"""
import os
import sys
import json
import time
import importlib.util

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import smart_agent

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
smart_agent.TAPE_FILE = os.path.join(BASE_DIR, "blind_hybrid_tape.json")

spec = importlib.util.spec_from_file_location(
    "sparring_opp", os.path.join(BASE_DIR, "..", "..", "draft_main_v4.py"))
sparring = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sparring)
sparring.TAPE_FILE = os.path.abspath(os.path.join(BASE_DIR, "..", "..", "blind_hybrid_tape.json"))

from kaggle_environments import make

env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": 101})
env.reset()

recorded = []
t0 = time.time()
for i in range(720):
    obs0 = dict(env.state[0].observation)
    obs1 = dict(env.state[1].observation)
    a0 = smart_agent.agent(obs0)
    a1 = sparring.agent(obs1)
    recorded.append(a0)
    env.step([a0, a1])
    if i % 100 == 0:
        print(f"step {i}: elapsed={time.time()-t0:.1f}s  score={env.state[0].observation['farms'][0]['money']:.0f}"
              f"  tracked_tiles={len(smart_agent._LAND_DEV['tiles'])}")

final_score = env.state[0].observation["farms"][0]["money"]
opp_score = env.state[1].observation["farms"][1]["money"]
print(f"\nGeneration run complete. Smart agent score={final_score:.0f}  sparring opp score={opp_score:.0f}")
print(f"Total wall time: {time.time()-t0:.1f}s")

out_path = os.path.join(BASE_DIR, "..", "god_tape_v1.json")
with open(out_path, "w") as f:
    json.dump(recorded, f)
print(f"Recorded {len(recorded)} steps to {out_path}")
