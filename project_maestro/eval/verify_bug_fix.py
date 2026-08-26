"""Verify Bug Fix Impact on Dominant Dairy Meta & All-In Sheep"""

import sys
import numpy as np

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.master_production_agent import MasterProductionAgent
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

def verify_fix(seeds=list(range(700, 750))):
    print(f'Verifying Bug Fix across N={len(seeds)} Seeds vs Dominant Dairy Meta & All-In Sheep...\n')

    opp_dairy = lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 10, "sheep_cap": 4, "strawberry_target": 18, "melon_seed_target": 6, "enable_3b": False
    }, seed=s)

    opp_sheep = lambda s: MaestroFullPortfolioAgent(params={
        "cow_cap_base": 0, "sheep_cap": 14, "strawberry_target": 28, "melon_seed_target": 0, "crew_mid": 11, "crew_late": 13
    }, seed=s)

    wins_d = 0
    scores_d = []
    opp_d_scores = []

    wins_s = 0
    scores_s = []
    opp_s_scores = []

    for s in seeds:
        # vs Dairy
        g_d = FastGame(seed=s)
        agent_d = MasterProductionAgent(seed=s)
        opp_d_agent = opp_dairy(s)
        while not g_d.done:
            g_d.step_game(agent_d(g_d.get_observation(0)), opp_d_agent(g_d.get_observation(1)))
        s0_d = g_d.farms[0].money
        s1_d = g_d.farms[1].money
        scores_d.append(s0_d)
        opp_d_scores.append(s1_d)
        if s0_d > s1_d:
            wins_d += 1

        # vs Sheep
        g_s = FastGame(seed=s)
        agent_s = MasterProductionAgent(seed=s)
        opp_s_agent = opp_sheep(s)
        while not g_s.done:
            g_s.step_game(agent_s(g_s.get_observation(0)), opp_s_agent(g_s.get_observation(1)))
        s0_s = g_s.farms[0].money
        s1_s = g_s.farms[1].money
        scores_s.append(s0_s)
        opp_s_scores.append(s1_s)
        if s0_s > s1_s:
            wins_s += 1

    wr_d = (wins_d / len(seeds)) * 100
    wr_s = (wins_s / len(seeds)) * 100

    print('=' * 85)
    print('BUG FIX VERIFICATION SCORECARD')
    print('=' * 85)
    print(f'1. vs Dominant Dairy Meta : {wr_d:5.1f}% ({wins_d}/{len(seeds)} Wins) | Our Mean: ${np.mean(scores_d):8,.2f} vs Opp: ${np.mean(opp_d_scores):8,.2f} | Margin: +${np.mean(scores_d) - np.mean(opp_d_scores):8,.2f}')
    print(f'2. vs All-In Sheep        : {wr_s:5.1f}% ({wins_s}/{len(seeds)} Wins) | Our Mean: ${np.mean(scores_s):8,.2f} vs Opp: ${np.mean(opp_s_scores):8,.2f} | Margin: +${np.mean(scores_s) - np.mean(opp_s_scores):8,.2f}')
    print('=' * 85)

if __name__ == '__main__':
    verify_fix()
