"""Benchmark NW Clustering alone (no §3b) vs all 5 ladder archetypes at n=200.

Protocol canaries 1-2 verified before reporting.
"""

import sys
import json
import numpy as np
from scipy import stats

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent,
    make_spatial_dispatcher_agent
)
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent

DISJOINT_100 = list(range(10000, 10100))
OFFICIAL_20 = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
               250, 300, 333, 404, 500, 600, 700, 777, 888, 999]

d = json.load(open('replays/episode-99064717-replay.json', encoding='utf-8'))
steps = d.get('steps', [])
ahmad_actions = [steps[t][0].get('action', {}) for t in range(1, len(steps))]

class ReplayAhmadAliAgent:
    def __init__(self):
        self.step_idx = 0
    def __call__(self, obs):
        if self.step_idx < len(ahmad_actions):
            act = ahmad_actions[self.step_idx]
            self.step_idx += 1
            return act
        return {"farmer": ["PASS"], "hands": [], "market": []}

NW_CLUSTERED_COW_PASTURES = [
    (4, 3), (3, 4),
    (4, 2), (3, 3), (2, 4),
    (4, 1), (3, 2), (2, 3), (1, 4),
    (3, 1), (2, 2), (1, 3), (0, 4), (4, 0)
]
NW_CLUSTERED_SHEEP_PASTURES = [
    (3, 1), (2, 2), (1, 3), (0, 4)
]

class AgentNWClusteredOnly(MaestroFullPortfolioAgent):
    """NW Clustering alone — no feed protection changes."""
    def __init__(self, params=None, kw_early=10, seed=None):
        super().__init__(params=params, kw_early=kw_early, seed=seed)
        self.cow_pastures = list(NW_CLUSTERED_COW_PASTURES)
        self.sheep_pastures = list(NW_CLUSTERED_SHEEP_PASTURES)


class AgentNWClusteredWithFeedProtection(MaestroFullPortfolioAgent):
    """NW Clustering + §3b Feed Protection."""
    def __init__(self, params=None, kw_early=10, seed=None):
        super().__init__(params=params, kw_early=kw_early, seed=seed)
        self.cow_pastures = list(NW_CLUSTERED_COW_PASTURES)
        self.sheep_pastures = list(NW_CLUSTERED_SHEEP_PASTURES)

    def __call__(self, obs):
        hour = obs["hour"]
        day = obs["day"]
        player = obs["player"]
        me = obs["farms"][player]
        private = obs["private"]
        shed = private.get("shed", {})
        money = me["money"]
        act = super().__call__(obs)
        filtered_market = []
        num_animals = self.params.get("cow_cap_base", 9) + self.params.get("sheep_cap", 4)
        feed_reserve = max(10, num_animals * 2)
        for o in act.get("market", []):
            if isinstance(o, list) and len(o) >= 3 and o[0] == "SELL" and o[1] == "WHEAT":
                wheat_avail = shed.get("WHEAT", 0)
                if wheat_avail > feed_reserve:
                    filtered_market.append(["SELL", "WHEAT", min(o[2], wheat_avail - feed_reserve)])
            else:
                filtered_market.append(o)
        if hour == 0 and day < 29 and shed.get("WHEAT", 0) < feed_reserve and money >= 100:
            buy_qty = min(feed_reserve - shed.get("WHEAT", 0), int(money // 25), 8)
            if buy_qty > 0 and len(filtered_market) < 10:
                filtered_market.append(["BUY_PRODUCT", "WHEAT", buy_qty])
        act["market"] = filtered_market[:10]
        return act


def run_canaries(cand_builder, label):
    print(f"  Running Canaries for: {label}")
    # Canary 1: Candidate vs all-PASS. Pass opponent must end with exactly $3,000.00.
    g = FastGame(seed=123)
    pass_agent = lambda obs: {"farmer": ["PASS"], "hands": [], "market": []}
    cand_inst = cand_builder()
    while not g.done:
        g.step_game(cand_inst(g.get_observation(0)), pass_agent(g.get_observation(1)))
    c1_opp_score = g.farms[1].money
    c1_ok = abs(c1_opp_score - 3000.0) < 1e-6
    # Canary 2: Identity (same agent vs itself). Must be 50.0% WR and mean delta = $0.00.
    deltas, wins, losses, ties = [], 0, 0, 0
    for s in OFFICIAL_20:
        for flip in [False, True]:
            a0, a1 = cand_builder(), cand_builder()
            g2 = FastGame(seed=s)
            while not g2.done:
                g2.step_game(a0(g2.get_observation(0)), a1(g2.get_observation(1)))
            if not flip:
                d = g2.farms[0].money - g2.farms[1].money
            else:
                d = g2.farms[1].money - g2.farms[0].money
            deltas.append(d)
            if d > 0: wins += 1
            elif d < 0: losses += 1
            else: ties += 1
    wr = (wins + 0.5 * ties) / (wins + losses + ties)
    mean_d = np.mean(deltas)
    c2_ok = abs(mean_d) < 1e-6 and abs(wr - 0.5) < 1e-6
    print(f"  Canary 1 (Pass opp = $3,000.00): {'PASS' if c1_ok else 'FAIL'} (opp=${c1_opp_score:.2f})")
    print(f"  Canary 2 (Identity 50%/D=$0): {'PASS' if c2_ok else 'FAIL'} (WR={wr*100:.1f}%, D=${mean_d:.2f})")
    assert c1_ok, f"Canary 1 FAIL (opp=${c1_opp_score:.2f}) -- abort"
    assert c2_ok, f"Canary 2 FAIL (WR={wr*100:.1f}%, D=${mean_d:.2f}) -- abort"


def run_ladder_eval(cand_builder, label):
    archetypes = [
        ("Ahmad Ali Specialist (14S / 0C)", lambda: ReplayAhmadAliAgent()),
        ("Dominant Meta (10C / 4S)", lambda: make_spatial_dispatcher_agent(params={"cow_cap_base": 10, "sheep_cap": 4, "goose_cap": 0, "cow_gate_day_early": 99, "cow_gate_day_mid": 99})),
        ("Gould Research Pastoral (12C / 6S)", lambda: make_spatial_dispatcher_agent(params={"cow_cap_base": 12, "sheep_cap": 6, "goose_cap": 0, "cow_gate_day_early": 99, "cow_gate_day_mid": 99})),
        ("Ayushk Empire Diversified (3C / 13S)", lambda: make_spatial_dispatcher_agent(params={"cow_cap_base": 3, "sheep_cap": 13, "goose_cap": 0, "cow_gate_day_early": 99, "cow_gate_day_mid": 99})),
        ("Meta-Calibrated Opponent (8C / 6S)", lambda: make_meta_calibrated_opponent()),
    ]
    print(f"\n{'=' * 105}")
    print(f"BENCHMARK: {label}")
    print(f"{'=' * 105}")
    for opp_name, opp_builder in archetypes:
        wins, losses, ties = 0, 0, 0
        deltas, cand_rewards, opp_rewards = [], [], []
        for s in DISJOINT_100:
            for seat in [0, 1]:
                g = FastGame(seed=s)
                a = [cand_builder(), opp_builder()] if seat == 0 else [opp_builder(), cand_builder()]
                while not g.done:
                    g.step_game(a[0](g.get_observation(0)), a[1](g.get_observation(1)))
                r_cand = g.farms[seat].money
                r_opp = g.farms[1 - seat].money
                cand_rewards.append(r_cand)
                opp_rewards.append(r_opp)
                deltas.append(r_cand - r_opp)
                if r_cand > r_opp: wins += 1
                elif r_opp > r_cand: losses += 1
                else: ties += 1
        wr = (wins + 0.5 * ties) / (wins + losses + ties)
        mean_delta = np.mean(deltas)
        t_stat, p_val = stats.ttest_1samp(deltas, 0.0)
        print(f"vs {opp_name:40s} | WR: {wr*100:5.1f}% ({wins:3d}W/{losses:3d}L/{ties:2d}T) | Delta: ${mean_delta:>+9,.2f} | Cand: ${np.mean(cand_rewards):>8,.0f} vs Opp: ${np.mean(opp_rewards):>8,.0f} | t={t_stat:>+5.2f}, p={p_val:.4e}")


def run_floor_check(cand_builder, label):
    """Disjoint-100 floor + Official-20 check."""
    print(f"\n--- Floor Check: {label} ---")
    scores = []
    for s in DISJOINT_100:
        g = FastGame(seed=s)
        a0 = cand_builder()
        a1 = make_spatial_dispatcher_agent()
        while not g.done:
            g.step_game(a0(g.get_observation(0)), a1(g.get_observation(1)))
        scores.append(g.farms[0].money)
    scores.sort()
    print(f"  Disjoint-100 (vs Baseline) | Mean: ${np.mean(scores):>9,.2f} | Median: ${np.median(scores):>9,.2f} | Floor (Min): ${scores[0]:>9,.2f} | p5: ${np.percentile(scores, 5):>9,.2f}")

    off20 = []
    for s in OFFICIAL_20:
        g = FastGame(seed=s)
        a0 = cand_builder()
        a1 = make_spatial_dispatcher_agent()
        while not g.done:
            g.step_game(a0(g.get_observation(0)), a1(g.get_observation(1)))
        off20.append(g.farms[0].money)
    print(f"  Official-20 (vs Baseline)  | Mean: ${np.mean(off20):>9,.2f} | Min: ${min(off20):>9,.2f}")


if __name__ == "__main__":
    # --- NW Clustering Only ---
    run_canaries(AgentNWClusteredOnly, "NW Clustering Only")
    run_ladder_eval(AgentNWClusteredOnly, "NW Clustering Only (no §3b)")

    # --- NW + §3b (already run, verify canaries again formally) ---
    run_canaries(AgentNWClusteredWithFeedProtection, "NW Clustering + §3b Feed Protection")
    run_ladder_eval(AgentNWClusteredWithFeedProtection, "NW Clustering + §3b Feed Protection")

    # --- Floor checks for both ---
    run_floor_check(make_spatial_dispatcher_agent, "Baseline (current production agent)")
    run_floor_check(AgentNWClusteredOnly, "NW Clustering Only")
    run_floor_check(AgentNWClusteredWithFeedProtection, "NW Clustering + §3b")
