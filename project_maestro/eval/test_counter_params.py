import sys
import numpy as np
sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.master_counter_agent import MasterCounterAgent
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

test_seeds = list(range(30000, 30050)) # 50 seeds

def test_config(c_cap, s_cap, straw_cap, melon_cap):
    wins = 0
    c_sc = []
    o_sc = []
    for s in test_seeds:
        g = FastGame(seed=s)
        a0 = MasterCounterAgent(params={'cow_cap_base': c_cap, 'sheep_cap': s_cap, 'strawberry_target': straw_cap, 'melon_seed_target': melon_cap}, seed=s)
        a1 = MaestroFullPortfolioAgent(params={'cow_cap_base': 10, 'sheep_cap': 4, 'strawberry_target': 18, 'melon_seed_target': 6}, seed=s)
        while not g.done:
            g.step_game(a0(g.get_observation(0)), a1(g.get_observation(1)))
        sc0 = g.farms[0].money
        sc1 = g.farms[1].money
        c_sc.append(sc0)
        o_sc.append(sc1)
        if sc0 > sc1:
            wins += 1
    wr = wins / len(test_seeds) * 100
    margin = np.mean(c_sc) - np.mean(o_sc)
    print(f'Params (C={c_cap}, S={s_cap}, Straw={straw_cap}, M={melon_cap}) -> Win Rate: {wr:5.1f}% | Cand Mean: ${np.mean(c_sc):7.0f} vs Opp: ${np.mean(o_sc):7.0f} | Margin: +${margin:6.0f}')

print('Testing Counter Configurations vs Dominant_Dairy_Meta (10C/4S)...')
test_config(9, 4, 22, 6)
test_config(10, 4, 22, 6)
test_config(10, 4, 24, 6)
test_config(11, 4, 22, 6)
test_config(10, 3, 24, 6)
