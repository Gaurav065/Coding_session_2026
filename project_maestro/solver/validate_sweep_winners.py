"""Validate coordinate_sweep.py's two real signals on the independent 60-seed set.

coordinate_sweep.py (N=40, seeds 30000-30039) found crew_mid=7 as the clearest dominant
improvement (better mean AND floor) and melon_seed_target=8 as a real but floor-worsening
mean improvement. Per this session's own established lesson (param_search.py's winners
were pure overfitting to a 15-seed sample), nothing gets adopted without independent
validation. Uses the 10000-10059 range already established throughout this session with
a known baseline (mean $49,708, min $23,077 at N=60).
"""

import sys
import statistics

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame, EPISODE_STEPS
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent, DEFAULT_PARAMS

VALIDATION_SEEDS = list(range(10000, 10060))

CANDIDATES = {
    "baseline": DEFAULT_PARAMS,
    "crew_mid_7": {**DEFAULT_PARAMS, "crew_mid": 7},
    "melon_8": {**DEFAULT_PARAMS, "melon_seed_target": 8},
    "crew_mid_7_and_melon_8": {**DEFAULT_PARAMS, "crew_mid": 7, "melon_seed_target": 8},
}


def run_one(seed, params):
    game = FastGame(seed=seed)
    a0 = make_spatial_dispatcher_agent(params)
    a1 = make_spatial_dispatcher_agent(params)
    while not game.done:
        act0 = a0(game.get_observation(0))
        act1 = a1(game.get_observation(1))
        game.step_game(act0, act1)
    return (float(game.farms[0].money) + float(game.farms[1].money)) / 2


def main():
    for name, params in CANDIDATES.items():
        scores = [run_one(s, params) for s in VALIDATION_SEEDS]
        print(f"{name:<24} mean=${statistics.mean(scores):>9,.0f}  median=${statistics.median(scores):>9,.0f}  "
              f"min=${min(scores):>9,.0f}  max=${max(scores):>9,.0f}", flush=True)


if __name__ == "__main__":
    main()
