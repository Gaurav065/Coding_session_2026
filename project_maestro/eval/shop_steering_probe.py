"""Prototype: is the town-shop draw steerable via controlled tile occupancy?

Verified mechanism (this session, both against the real engine and fast_engine.py):
`_end_of_day` builds one RNG per day (`Random((seed*1_000_003)^day)`), consumes it via
`rng.random()` once per EMPTY tile across BOTH farms during weed-spawn, THEN calls
`rng.choice(SHOP_NAMES)` for the shop draw. So how many empty tiles exist (ours AND the
opponent's) at that moment determines which shop gets picked. This directly tests: can we
reliably choose which shop unlocks by controlling how many tiles we leave empty?

Locked tiles are the string "LOCKED", not None, and are excluded from the weed-spawn
RNG loop -- confirmed by reading kaggriculture.py:145-158. Before any land purchase, each
farm's controllable empty/occupied set is the 24 non-shed-access NW tiles (COW_PASTURES +
GOOSE_COOPS + NW_WHEAT from dispatcher_agent.py, already verified as the real farmable set).

Holds the opponent at all-PASS (0 planted, fully deterministic and known) and sweeps our
own planted-tile-count K from 0 to 24, recording the shop drawn at end of day 2 (the first
draw, next_day=3). If the mapping is real and exploitable, different K values should
reliably map to different shops for a fixed seed.
"""

import sys

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame, EPISODE_STEPS
from project_maestro.agent.dispatcher_agent import COW_PASTURES, GOOSE_COOPS, NW_WHEAT, get_step_towards

NW_ALL = list(dict.fromkeys(COW_PASTURES + GOOSE_COOPS + NW_WHEAT))  # 24 distinct tiles, dedup-safe


def make_planter(k):
    """Plants WHEAT on the first k tiles of NW_ALL, then PASSes forever."""
    state = {"bought": False, "idx": 0}

    def agent(obs):
        farm = obs["farms"][obs["player"]]
        pos = tuple(farm["farmer"])
        seeds = obs["private"]["seeds"].get("WHEAT", 0)
        market = []
        if not state["bought"] and k > 0:
            market.append(["BUY_SEED", "WHEAT", k])
            state["bought"] = True
        if state["idx"] >= k:
            return {"farmer": ["PASS"], "hands": [], "market": market}
        target = NW_ALL[state["idx"]]
        if pos == target:
            tile = farm["tiles"][target[1]][target[0]]
            if tile is None and seeds > 0:
                state["idx"] += 1
                return {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": market}
            state["idx"] += 1  # already occupied or no seed; skip
            return {"farmer": ["PASS"], "hands": [], "market": market}
        step = get_step_towards(pos, target)
        return {"farmer": [step], "hands": [], "market": market}
    return agent


def all_pass(obs):
    return {"farmer": ["PASS"], "hands": [], "market": []}


def run_to_day3(seed, k):
    game = FastGame(seed=seed)
    planter = make_planter(k)
    while game.day < 3:
        act0 = planter(game.get_observation(0))
        act1 = all_pass(game.get_observation(1))
        game.step_game(act0, act1)
    return list(game.unlocked_shops), sum(1 for row in game.farms[0].tiles for t in row if t is None)


def main():
    for seed in (42, 100, 777):
        print(f"\n=== seed {seed} ===")
        seen = {}
        for k in range(0, 25):
            shops, empty_count = run_to_day3(seed, k)
            first_shop = shops[0] if shops else None
            seen.setdefault(first_shop, []).append(k)
            print(f"k={k:>2} planted (empty NW after={empty_count:>2})  -> first shop: {first_shop}", flush=True)
        print(f"  shop -> [k values that produce it]: {seen}")


if __name__ == "__main__":
    main()
