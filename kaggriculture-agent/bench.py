"""Measurement harness. Not part of the submission.

Runs our agent vs every replay in `Performance test/` for N seeds each.
Reports per-opponent win rate + aggregate win rate + score variance.

Optimizes for the ladder objective (P(win)), not mean score.

Usage:
    python bench.py                    # default: 3 seeds x all opponents
    python bench.py -n 8               # 8 seeds x all opponents
    python bench.py --pool replays     # different opponent folder
    python bench.py -q                 # quiet (aggregate only)

Notes:
- Runs in-process; resets replay_opponent and main state between games so
  cached _MEM / _REPLAY globals do not bleed across games.
- Reports both raw scores and the more important number: win rate.
"""
import argparse
import glob
import os
import statistics
import sys
import time

from kaggle_environments import make
import agent_aegis as main
import importlib.util
_MAIN_PATH = os.path.abspath(main.__file__)
_EXPECTED = os.path.abspath("main.py")


def _load_replay_module():
    spec = importlib.util.spec_from_file_location(
        "replay_opp", "replay_opponent.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _reset(replay_mod):
    """Clear cached state so seed N does not inherit anything from seed N-1."""
    replay_mod._REPLAY = None
    replay_mod._WINNER_ID = None
    main._MEM.clear()


def run_one(seed, replay_path, replay_mod):
    _reset(replay_mod)
    os.environ["REPLAY_PATH"] = replay_path
    env = make(
        "kaggriculture",
        configuration={"episodeSteps": 720, "seed": seed})
    env.run([main.agent, replay_mod.agent])
    s0 = float(env.steps[-1][0].reward or 0)
    s1 = float(env.steps[-1][1].reward or 0)
    return s0, s1


def run_pool(replays, seeds, verbose=True):
    replay_mod = _load_replay_module()
    per_opp = []           # [(name, wins, n, my_mean, my_std, opp_mean, deltas)]
    total_games = 0
    total_wins = 0
    all_my = []
    all_opp = []
    all_deltas = []
    started = time.time()

    for path in replays:
        name = os.path.basename(path).replace(".json", "")
        my_scores = []
        opp_scores = []
        for seed in seeds:
            t0 = time.time()
            s0, s1 = run_one(seed, os.path.abspath(path), replay_mod)
            my_scores.append(s0)
            opp_scores.append(s1)
            total_games += 1
            won = s0 > s1
            total_wins += 1 if won else 0
            all_my.append(s0)
            all_opp.append(s1)
            all_deltas.append(s0 - s1)
            if verbose:
                tag = "WIN " if won else "loss"
                sys.stdout.write(
                    f"  seed {seed:<4d} me {s0:9.0f}  opp {s1:9.0f}  "
                    f"{tag}  d{s0-s1:+8.0f}  ({time.time()-t0:.1f}s)\n")
                sys.stdout.flush()
        wins = sum(1 for a, b in zip(my_scores, opp_scores) if a > b)
        per_opp.append((
            name, wins, len(seeds),
            statistics.mean(my_scores),
            statistics.pstdev(my_scores) if len(my_scores) > 1 else 0.0,
            statistics.mean(opp_scores),
            [a - b for a, b in zip(my_scores, opp_scores)],
        ))
        if verbose:
            wr = wins / len(seeds) * 100
            sys.stdout.write(
                f"  -> {name}  wins {wins}/{len(seeds)} ({wr:.0f}%)  "
                f"me mean={statistics.mean(my_scores):.0f}  "
                f"opp mean={statistics.mean(opp_scores):.0f}\n\n")
            sys.stdout.flush()

    elapsed = time.time() - started
    return per_opp, total_wins, total_games, all_my, all_opp, all_deltas, elapsed


def report(per_opp, total_wins, total_games, all_my, all_opp, all_deltas, elapsed):
    print("=" * 74)
    print(f"{'opponent':<14} {'wins':>6} {'wr%':>5} "
          f"{'me mean':>8} {'me std':>7} {'opp mean':>8} {'d_mean':>8}")
    print("-" * 74)
    for (name, w, n, m_mu, m_sd, o_mu, deltas) in per_opp:
        wr = w / n * 100
        d_mu = statistics.mean(deltas)
        print(f"{name[:14]:<14} {w:>3}/{n:<2} {wr:>4.0f}% "
              f"{m_mu:>8.0f} {m_sd:>7.0f} {o_mu:>8.0f} {d_mu:>+8.0f}")
    print("=" * 74)
    agg_wr = total_wins / total_games * 100 if total_games else 0
    m_mu = statistics.mean(all_my) if all_my else 0
    m_sd = statistics.pstdev(all_my) if len(all_my) > 1 else 0
    o_mu = statistics.mean(all_opp) if all_opp else 0
    d_mu = statistics.mean(all_deltas) if all_deltas else 0
    print(f"AGGREGATE      {total_wins:>3}/{total_games:<2} {agg_wr:>4.0f}% "
          f"{m_mu:>8.0f} {m_sd:>7.0f} {o_mu:>8.0f} {d_mu:>+8.0f}")
    print(f"                                                            ({elapsed:.0f}s)")


def cli():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=3, help="seeds per opponent")
    ap.add_argument("--pool", default="Performance test",
                    help="folder containing opponent replay JSONs")
    ap.add_argument("--seeds", type=int, nargs="*",
                    help="explicit seed list (overrides -n)")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="only aggregate report, no per-game lines")
    args = ap.parse_args()

    if args.seeds:
        seeds = args.seeds
    else:
        # spread across the standard sweep base
        base = [101, 108, 115, 122, 129, 136, 143, 150, 157, 164, 171, 178]
        seeds = base[:args.n]

    replays = sorted(glob.glob(os.path.join(args.pool, "*.json")))
    if not replays:
        print(f"no replays found in {args.pool!r}", file=sys.stderr)
        sys.exit(1)

    print(f"pool: {args.pool} ({len(replays)} opponents)")
    print(f"seeds: {seeds}")
    print(f"total games: {len(replays) * len(seeds)}")
    print()

    result = run_pool(replays, seeds, verbose=not args.quiet)
    report(*result)


if __name__ == "__main__":
    cli()
