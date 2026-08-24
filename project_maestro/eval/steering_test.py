"""Does deliberately steering the day-3 shop draw net out positive vs not steering?

Real design constraint discovered while building this: occupancy can only change via
PLANT/BUILD, which always carries an economic side effect (seed cost, future yield) --
there's no way to isolate "shop draw changed" from "economy changed" in a vacuum. So this
tests the honest, real question: does an agent that deliberately accelerates some of its
OWN already-planned wheat plantings (to shift day-2 occupancy, and therefore the day-3
shop draw) score higher on net than the same agent left alone -- side effects included.

Wrapper design, chosen to be safe: only touches the farmer's action, only when it would
otherwise be PASS, only during days 0-2, and only to plant on NW_WHEAT tiles (which the
real agent already intends to plant regardless -- this accelerates timing, it does not
add new tiles the real agent wasn't already going to occupy, so it cannot conflict with
COW_PASTURES/GOOSE_COOPS animal-placement logic, which requires tile is None). Hands and
market orders are left completely untouched -- all economic decisions (buying cows,
hiring, etc.) are exactly as the unmodified agent would make them.

Self-play mirror (same override on both sides, matching every test this session). Given
today's lesson (N=15 and N=40 both produced signals that failed to replicate on an
independent 60-seed set), this uses N=100 from the start.
"""

import sys
import statistics

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame, EPISODE_STEPS
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent, NW_WHEAT, get_step_towards,
)


def make_steered_agent(extra_k):
    """extra_k=0 behaves identically to the unmodified agent (verified below).

    BUG FIXED: originally intercepted action["farmer"], but NW_WHEAT planting is
    done by dedicated crop-crew HAND units (u_idx 4 and 5 -- see
    dispatcher_agent.py's sector_tasks assignment, "if u_idx in (4, 5):
    sector_tasks = nw_wheat_tasks_p1 or nw_wheat_tasks_p2 or ..."), not the
    farmer (u_idx 0, animal-sweep crew, rarely touches NW_WHEAT). That version
    produced an exact no-op at every extra_k -- confirmed via direct
    instrumentation that the override branch did fire, but on the wrong unit,
    so it never accumulated the multi-turn control needed to complete a
    walk-then-plant sequence. This version overrides hands[3] (u_idx 4).
    """
    real = MaestroFullPortfolioAgent()
    state = {"planted": 0}

    def agent(obs):
        action = real(obs)
        if extra_k <= 0 or obs["day"] >= 3 or state["planted"] >= extra_k:
            return action
        hands = list(action["hands"])
        if len(hands) < 4 or hands[3] != ["PASS"]:
            return action  # never override a real decision, only idle PASS moments
        me = obs["farms"][obs["player"]]
        me_hands = me.get("hands", [])
        if len(me_hands) < 4:
            return action
        pos = tuple(me_hands[3])
        seeds = obs["private"]["seeds"].get("WHEAT", 0)
        if seeds <= 0:
            return action
        for tx, ty in NW_WHEAT:
            tile = me["tiles"][ty][tx]
            if tile is not None:
                continue  # already planted (by the real agent) or occupied -- skip
            if pos == (tx, ty):
                state["planted"] += 1
                hands[3] = ["PLANT", "WHEAT"]
            else:
                hands[3] = [get_step_towards(pos, (tx, ty))]
            return {"farmer": action["farmer"], "hands": hands, "market": action["market"]}
        return action  # no unplanted NW_WHEAT tile left

    return agent


def run_one(seed, extra_k):
    game = FastGame(seed=seed)
    a0 = make_steered_agent(extra_k)
    a1 = make_steered_agent(extra_k)
    while not game.done:
        act0 = a0(game.get_observation(0))
        act1 = a1(game.get_observation(1))
        game.step_game(act0, act1)
    shop3 = game.unlocked_shops[0] if game.unlocked_shops else None
    return (float(game.farms[0].money) + float(game.farms[1].money)) / 2, shop3


def verify_zero_is_noop(seeds):
    """extra_k=0 must be byte-identical to the unmodified agent -- sanity check first."""
    from project_maestro.agent.dispatcher_agent import make_spatial_dispatcher_agent
    for seed in seeds:
        game = FastGame(seed=seed)
        a0 = make_spatial_dispatcher_agent()
        a1 = make_spatial_dispatcher_agent()
        while not game.done:
            act0 = a0(game.get_observation(0))
            act1 = a1(game.get_observation(1))
            game.step_game(act0, act1)
        unmodified = (float(game.farms[0].money) + float(game.farms[1].money)) / 2
        steered0, _ = run_one(seed, 0)
        assert abs(unmodified - steered0) < 1, f"seed {seed}: {unmodified} vs {steered0} -- NOT a no-op!"
    print(f"verified extra_k=0 is a no-op on {len(seeds)} seeds")


def main():
    verify_zero_is_noop([42, 100, 777])

    seeds = list(range(40000, 40100))  # N=100, fresh range, independent of every prior test
    for extra_k in (0, 3, 5, 8, 10):
        scores = []
        shops = {}
        for s in seeds:
            score, shop = run_one(s, extra_k)
            scores.append(score)
            shops[shop] = shops.get(shop, 0) + 1
        print(f"extra_k={extra_k:>2}  mean=${statistics.mean(scores):>9,.0f}  "
              f"median=${statistics.median(scores):>9,.0f}  min=${min(scores):>9,.0f}  "
              f"max=${max(scores):>9,.0f}  day3_shops={shops}", flush=True)


if __name__ == "__main__":
    main()
