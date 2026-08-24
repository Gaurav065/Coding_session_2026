"""Bounded random search over the dispatcher's key knobs, via the fast engine.

Phase 2, done for real this time: earlier attempts (see solver/NOTES.md) used an
analytical valuation model that was rejected twice for miscalibration. This instead
searches by direct simulation -- self-play (same params both sides, matching every
benchmark this session), fast engine (verified 20/20 exact vs the reference engine).

Bounded scope for a first pass: random sample of the joint parameter space (not
exhaustive -- 3*2*3*3*3*3*3 = 1,458 combinations is too large), each candidate evaluated
on a moderate seed sample. This directly tests what three single-variable tests this
session could NOT see: interaction/opportunity-cost effects between knobs (2e and 2f both
regressed for reasons a one-variable test could not detect).
"""

import sys
import random
import statistics

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame, EPISODE_STEPS
from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent, DEFAULT_PARAMS

GRID = {
    "cow_cap_low": [4, 6, 8],
    "cow_cap_base": [10],       # held fixed -- upward scaling already rejected (2b)
    "sheep_cap": [4, 6],
    "goose_cap": [2, 4, 6],
    "melon_seed_target": [4, 6, 8],
    "strawberry_target": [12, 16, 20],
    "crew_late": [11, 13, 15],
    "crew_mid": [7, 9, 11],
}

N_CANDIDATES = 24
SEEDS = list(range(20000, 20015))  # 15 seeds/candidate, distinct from the 10000s diagnostic range


def run_one(seed, params):
    game = FastGame(seed=seed)
    a0 = make_spatial_dispatcher_agent(params)
    a1 = make_spatial_dispatcher_agent(params)
    while not game.done:
        act0 = a0(game.get_observation(0))
        act1 = a1(game.get_observation(1))
        game.step_game(act0, act1)
    return (float(game.farms[0].money) + float(game.farms[1].money)) / 2


def eval_params(params, seeds=SEEDS):
    return [run_one(s, params) for s in seeds]


def sample_params(rng):
    return {k: rng.choice(v) for k, v in GRID.items()}


def main():
    rng = random.Random(42)

    print("=== baseline (current defaults) ===", flush=True)
    base_scores = eval_params(DEFAULT_PARAMS)
    base_mean = statistics.mean(base_scores)
    print(f"baseline mean=${base_mean:,.0f} min=${min(base_scores):,.0f} "
          f"max=${max(base_scores):,.0f}", flush=True)

    results = [(DEFAULT_PARAMS, base_scores)]
    for i in range(N_CANDIDATES):
        p = sample_params(rng)
        scores = eval_params(p)
        m = statistics.mean(scores)
        print(f"[{i+1}/{N_CANDIDATES}] mean=${m:,.0f} min=${min(scores):,.0f} "
              f"params={p}", flush=True)
        results.append((p, scores))

    print("\n=== ranked by mean ===")
    ranked = sorted(results, key=lambda r: -statistics.mean(r[1]))
    for p, scores in ranked[:6]:
        m = statistics.mean(scores)
        delta = m - base_mean
        print(f"mean=${m:,.0f} (delta {delta:+,.0f}, {100*delta/base_mean:+.1f}%) "
              f"min=${min(scores):,.0f} params={p}")


if __name__ == "__main__":
    main()
