
import json

with open(r"C:\Users\GauravPatel\Downloads\94447374 (1).json", "r") as f:
    replay = json.load(f)

with open("blind_hybrid_tape.json", "r") as f:
    tape = json.load(f)

mutations = 0
for i in range(1, len(replay["steps"])):
    step_obs = replay["steps"][i][0]["observation"]
    obs_step = step_obs.get("step", 0)
    
    if obs_step >= len(tape): break
    
    p0_action = replay["steps"][i][0]["action"]
    if p0_action is None: continue
    
    tape_market = tape[obs_step].get("market", [])
    p0_market = p0_action.get("market", [])
    
    if tape_market != p0_market:
        print(f"Step {obs_step}:")
        print(f"  Tape: {tape_market}")
        print(f"  P0:   {p0_market}")
        mutations += 1

print(f"Total mutations: {mutations}")

