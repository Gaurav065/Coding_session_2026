"""Validate top param_search.py candidates on an INDEPENDENT seed set.

param_search.py used seeds 20000-20014 (15 seeds) -- small enough that random search
could overfit to that specific sample. This re-scores the top candidates on the 60-seed
10000-10059 range already used throughout this session (eval/cluster_diagnostic.py,
agent/NOTES.md 2d/2e/2f), which is independent of the search set and has a known
baseline to compare against.
"""

import sys
import statistics

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame, EPISODE_STEPS
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent, DEFAULT_PARAMS

VALIDATION_SEEDS = list(range(10000, 10060))

CANDIDATES = {
    "baseline": DEFAULT_PARAMS,
    "top_by_mean": {'cow_cap_low': 4, 'cow_cap_base': 10, 'sheep_cap': 4, 'goose_cap': 4,
                     'melon_seed_target': 8, 'strawberry_target': 20, 'crew_late': 13, 'crew_mid': 7},
    "best_floor_and_mean": {'cow_cap_low': 6, 'cow_cap_base': 10, 'sheep_cap': 4, 'goose_cap': 2,
                              'melon_seed_target': 6, 'strawberry_target': 16, 'crew_late': 11, 'crew_mid': 7},
    "third": {'cow_cap_low': 8, 'cow_cap_base': 10, 'sheep_cap': 4, 'goose_cap': 4,
               'melon_seed_target': 6, 'strawberry_target': 20, 'crew_late': 13, 'crew_mid': 11},
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
        print(f"{name:<22} mean=${statistics.mean(scores):>9,.0f}  median=${statistics.median(scores):>9,.0f}  "
              f"min=${min(scores):>9,.0f}  max=${max(scores):>9,.0f}", flush=True)


if __name__ == "__main__":
    main()
