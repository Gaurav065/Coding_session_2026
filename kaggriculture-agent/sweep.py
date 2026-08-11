"""Parameter sweep. Not part of the submission.

    python sweep.py KEY v1 v2 v3 ...        # sweep one tunable
    python sweep.py --seeds 8               # change seed count for baseline
"""
import sys
import statistics
from concurrent.futures import ProcessPoolExecutor

from kaggle_environments import make
import main

SEEDS = [101,108,115,122,129,136,143,150,157,164,171,178]


def one(args):
    key, val, seed = args
    if key is not None:
        main.P[key] = val
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    env.run([main.agent, "pass"])
    return float(env.steps[-1][0].reward or 0)


def evaluate(key, val, seeds):
    with ProcessPoolExecutor(max_workers=8) as ex:
        scores = list(ex.map(one, [(key, val, s) for s in seeds]))
    return scores


def main_cli():
    args = sys.argv[1:]
    n = 8
    if args and args[0] == "--seeds":
        n = int(args[1])
        args = args[2:]
    seeds = SEEDS[:n]

    if not args:
        scores = evaluate(None, None, seeds)
        print("baseline  mean %.0f  median %.0f  min %.0f  max %.0f"
              % (statistics.mean(scores), statistics.median(scores),
                 min(scores), max(scores)))
        return

    key = args[0]
    vals = [float(v) if ("." in v or "e" in v) else int(v) for v in args[1:]]
    base = main.P.get(key)
    print("sweeping %s (base=%s) over %d seeds" % (key, base, len(seeds)))
    for v in vals:
        scores = evaluate(key, v, seeds)
        print("  %-10s mean %7.0f  median %7.0f  min %6.0f  max %6.0f"
              % (v, statistics.mean(scores), statistics.median(scores),
                 min(scores), max(scores)))


if __name__ == "__main__":
    main_cli()
