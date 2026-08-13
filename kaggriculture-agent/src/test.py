"""Local evaluation harness.  Not part of the submission.

    python test.py                 # 3 seeds vs the built-in starter
    python test.py -n 6            # 6 seeds
    python test.py -o self         # opponent: starter | random | pass | self
    python test.py -v              # per-day trace of player 0
"""
import argparse
import statistics
import sys
import time
import traceback

from kaggle_environments import make

import main

TRACE = False
_timing = []


def wrap(fn, pid_watch=0):
    def inner(obs):
        t0 = time.time()
        try:
            acts = fn(obs)
        except Exception:
            sys.__stdout__.write(traceback.format_exc())
            raise
        _timing.append(time.time() - t0)
        if TRACE and obs["player"] == pid_watch and obs["hour"] == 23:
            f = obs["farms"][pid_watch]
            priv = obs["private"]
            cnt = {}
            for row in f["tiles"]:
                for t in row:
                    if isinstance(t, dict):
                        k = t.get("crop") or t.get("animal") or t.get("kind")
                        cnt[k] = cnt.get(k, 0) + 1
            mk = obs["market"]["prices"]
            sys.__stdout__.write(
                "d%02d $%8.0f | %-50s | shed %s | hand %2d land %d | "
                "wh%3d eg%3d mi%3d wo%3d st%3d me%3d fe%3d\n"
                % (obs["day"], f["money"],
                   " ".join("%s=%d" % (k[:4], v) for k, v in sorted(cnt.items())),
                   " ".join("%s%d" % (k[:2], v)
                            for k, v in sorted(priv["shed"].items()) if v),
                   len(f["hands"]), len(f["unlocked_quadrants"]),
                   mk["WHEAT"], mk["EGG"], mk["MILK"], mk["WOOL"],
                   mk["STRAWBERRY"], mk["MELON"], mk["FERTILIZER"]))
            sys.__stdout__.flush()
        return acts
    return inner


def run(seed, opponent):
    env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed})
    me = wrap(main.agent)
    opp = wrap(main.agent, -1) if opponent == "self" else opponent
    env.run([me, opp])
    final = env.steps[-1]
    return float(final[0].reward or 0), float(final[1].reward or 0)


def cli():
    global TRACE
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=3)
    ap.add_argument("-o", default="starter")
    ap.add_argument("-v", action="store_true")
    ap.add_argument("--seed0", type=int, default=101)
    a = ap.parse_args()
    TRACE = a.v

    mine, wins = [], 0
    for i in range(a.n):
        seed = a.seed0 + i * 7
        t0 = time.time()
        s0, s1 = run(seed, a.o)
        mine.append(s0)
        wins += s0 > s1
        print("seed %-6d  me %9.0f   opp %9.0f   %s   (%.1fs)"
              % (seed, s0, s1, "WIN " if s0 > s1 else "loss", time.time() - t0))

    print("-" * 62)
    print("mean %.0f   median %.0f   min %.0f   max %.0f   wins %d/%d"
          % (statistics.mean(mine), statistics.median(mine),
             min(mine), max(mine), wins, a.n))
    if _timing:
        t = sorted(_timing)
        print("agent step time: mean %.1fms  p99 %.1fms  max %.1fms"
              % (1000 * statistics.mean(t), 1000 * t[int(len(t) * .99)],
                 1000 * t[-1]))


if __name__ == "__main__":
    cli()
