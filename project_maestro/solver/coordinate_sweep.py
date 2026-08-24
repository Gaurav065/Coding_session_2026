"""Coordinate sweep over the dispatcher's knobs, with a properly-sized seed sample.

param_search.py's random joint search (24 candidates x 15 seeds) found "winners" that
were actually worse than baseline when validated on an independent 60-seed set -- pure
overfitting to too small a sample (see solver/NOTES.md). This redoes the search properly:
vary ONE parameter at a time from the known-good baseline (matches this project's
one-variable-at-a-time discipline, and is more interpretable than random joint sampling),
each evaluated on N=40 seeds -- enough for the seed-to-seed variance already observed
(individual seeds range roughly $12k-$97k) to average out.

Self-play (same params both sides), fast engine (verified 20/20 exact vs the reference
engine). Seeds distinct from both param_search.py's search set (20000s) and the
cluster-diagnostic set (10000s), to keep this evidence independent of prior runs.
"""

import sys
import statistics

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame, EPISODE_STEPS
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent, DEFAULT_PARAMS

SWEEP_GRID = {
    "cow_cap_low": [4, 8],          # baseline 6
    "sheep_cap": [6],                # baseline 4
    "goose_cap": [2, 6],             # baseline 4
    "melon_seed_target": [4, 8],     # baseline 6
    "strawberry_target": [12, 20],   # baseline 16
    "crew_late": [11, 15],           # baseline 13
    "crew_mid": [7, 11],             # baseline 9
}

N_SEEDS = 40
SEEDS = list(range(30000, 30000 + N_SEEDS))


def run_one(seed, params):
    game = FastGame(seed=seed)
    a0 = make_spatial_dispatcher_agent(params)
    a1 = make_spatial_dispatcher_agent(params)
    while not game.done:
        act0 = a0(game.get_observation(0))
        act1 = a1(game.get_observation(1))
        game.step_game(act0, act1)
    return (float(game.farms[0].money) + float(game.farms[1].money)) / 2


def eval_params(params):
    return [run_one(s, params) for s in SEEDS]


def main():
    print(f"=== baseline, N={N_SEEDS} seeds ===", flush=True)
    base_scores = eval_params(DEFAULT_PARAMS)
    base_mean = statistics.mean(base_scores)
    print(f"baseline mean=${base_mean:,.0f} median=${statistics.median(base_scores):,.0f} "
          f"min=${min(base_scores):,.0f} max=${max(base_scores):,.0f}", flush=True)

    print("\n=== coordinate sweep (one param varied at a time from baseline) ===")
    results = []
    for param, values in SWEEP_GRID.items():
        for v in values:
            p = dict(DEFAULT_PARAMS)
            p[param] = v
            scores = eval_params(p)
            m = statistics.mean(scores)
            delta = m - base_mean
            results.append((param, v, m, min(scores), delta))
            print(f"{param}={v:<3} mean=${m:>9,.0f} (delta {delta:+8,.0f}, "
                  f"{100*delta/base_mean:+5.1f}%) min=${min(scores):>9,.0f}", flush=True)

    print("\n=== ranked by mean delta ===")
    for param, v, m, mn, delta in sorted(results, key=lambda r: -r[4]):
        print(f"{param}={v:<3} delta={delta:+8,.0f} ({100*delta/base_mean:+5.1f}%) min=${mn:>9,.0f}")


if __name__ == "__main__":
    main()
