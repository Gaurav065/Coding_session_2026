"""Specialist Variant Candidate vs Full Archetype Matrix

Evaluates a Wool/Melon-empowered specialist variant of our own agent against the full archetype matrix:
1. Dominant Meta (10C / 4S / 0G)
2. Wool-Heavy (6C / 12S / 0G)
3. Balanced Pasture (6C / 8S / 0G)
4. Meta-Calibrated Opponent (8C / 6S / 0G)
5. Ahmad Ali Specialist Opponent (14S / 33M / 0C)

Judged strictly on HEAD-TO-HEAD WIN RATE across 100 Disjoint Seeds (n=200 matches each),
not self-play mean.
"""

import sys
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Any

sys.path.insert(0, r"C:\Coding")
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent, make_spatial_dispatcher_agent
from project_maestro.agent.specialist_opponent import SpecialistOpponent, make_specialist_opponent
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent

DISJOINT_100 = list(range(10000, 10100))
OFFICIAL_20 = [10, 20, 30, 42, 55, 77, 99, 100, 123, 200,
               250, 300, 333, 404, 500, 600, 700, 777, 888, 999]


class WoolMelonSpecialistAgent(MaestroFullPortfolioAgent):
    """Specialist variant: 8 Sheep on YARN_STORE, 8 Melons, 8 Cows base."""
    def __init__(self, params=None, kw_early: int = 10, seed: int = None):
        spec_params = {
            "cow_cap_base": 8,           # 8 Cows (balances capital and feed)
            "sheep_cap": 8,              # 8 Sheep (scales wool when yarn store active)
            "melon_seed_target": 8,      # 8 Melons
            "strawberry_target": 20,
            "crew_late": 10,
            "crew_mid": 9,
            "cow_gate_day_early": 10,
            "cow_cap_zero": 4,
            "cow_gate_day_mid": 10,
            "cow_cap_low": 6,
        }
        if params:
            spec_params.update(params)
        super().__init__(params=spec_params, kw_early=kw_early, seed=seed)
        # Allocate 8 sheep pastures dynamically
        self.cow_pastures = [
            (4, 3), (3, 4),
            (4, 2), (3, 3), (2, 4),
            (4, 1), (3, 2), (2, 3)
        ]
        self.sheep_pastures = [
            (1, 4), (4, 0),
            (3, 1), (2, 2), (1, 3), (0, 4),
            (0, 3), (1, 2)
        ]


def run_match(agent0, agent1, seed: int):
    g = FastGame(seed=seed)
    while not g.done:
        g.step_game(agent0(g.get_observation(0)), agent1(g.get_observation(1)))
    return g.farms[0].money, g.farms[1].money


def eval_candidate_against_archetypes(cand_builder, cand_label: str):
    print("=" * 105)
    print(f"EVALUATING CANDIDATE: {cand_label}")
    print("=" * 105)

    archetypes = [
        ("Dominant Meta (10C / 4S / 0G)", lambda: make_spatial_dispatcher_agent(params={"cow_cap_base": 10, "sheep_cap": 4, "goose_cap": 0, "cow_gate_day_early": 99, "cow_gate_day_mid": 99})),
        ("Wool-Heavy (6C / 12S / 0G)", lambda: make_spatial_dispatcher_agent(params={"cow_cap_base": 6, "sheep_cap": 12, "goose_cap": 0, "cow_gate_day_early": 99, "cow_gate_day_mid": 99})),
        ("Balanced Pasture (6C / 8S / 0G)", lambda: make_spatial_dispatcher_agent(params={"cow_cap_base": 6, "sheep_cap": 8, "goose_cap": 0, "cow_gate_day_early": 99, "cow_gate_day_mid": 99})),
        ("Meta-Calibrated Opponent (8C / 6S / 0G)", lambda: make_meta_calibrated_opponent()),
        ("Ahmad Ali Specialist (14S / 33M / 0C)", lambda: make_specialist_opponent()),
    ]

    for opp_name, opp_builder in archetypes:
        wins, losses, ties = 0, 0, 0
        deltas = []
        cand_rewards = []
        opp_rewards = []

        for s in DISJOINT_100:
            # Seat 0
            r0, r1 = run_match(cand_builder(), opp_builder(), s)
            cand_rewards.append(r0)
            opp_rewards.append(r1)
            deltas.append(r0 - r1)
            if r0 > r1: wins += 1
            elif r1 > r0: losses += 1
            else: ties += 1
            
            # Seat 1
            r0, r1 = run_match(opp_builder(), cand_builder(), s)
            cand_rewards.append(r1)
            opp_rewards.append(r0)
            deltas.append(r1 - r0)
            if r1 > r0: wins += 1
            elif r0 > r1: losses += 1
            else: ties += 1

        wr = (wins + 0.5 * ties) / (wins + losses + ties)
        mean_delta = np.mean(deltas)
        t_stat, p_val = stats.ttest_1samp(deltas, 0.0)

        print(f"vs {opp_name:40s} | WR: {wr*100:5.1f}% ({wins:3d}W/{losses:3d}L/{ties:2d}T) | Delta: ${mean_delta:>+9,.2f} | Cand: ${np.mean(cand_rewards):>8,.0f} vs Opp: ${np.mean(opp_rewards):>8,.0f} | t={t_stat:>+5.2f}, p={p_val:.4e}")
    print("=" * 105 + "\n")


if __name__ == "__main__":
    # 1. Baseline Production Agent
    eval_candidate_against_archetypes(lambda: make_spatial_dispatcher_agent(), "Baseline Production Agent (9C / 4S / 0G)")
    
    # 2. Wool/Melon Specialist Candidate Agent
    eval_candidate_against_archetypes(lambda: WoolMelonSpecialistAgent(), "Wool/Melon Specialist Candidate (8C / 8S / 0G, 8 Melons)")
