import sys, os
sys.path.insert(0, r'C:/Coding')
from kaggle_environments import make
from project_maestro.agent.master_counter_agent import MasterCounterAgent
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent

seed = int(sys.argv[1]) if len(sys.argv) > 1 else 42
opp_type = sys.argv[2] if len(sys.argv) > 2 else 'meta_calibrated'

our_agent = MasterCounterAgent(seed=seed)

if opp_type == 'meta_calibrated':
    opp_agent = make_meta_calibrated_opponent(seed=seed)
elif opp_type == 'dominant_meta':
    opp_inst = MaestroFullPortfolioAgent(params={'cow_cap_base': 10, 'sheep_cap': 4, 'strawberry_target': 18, 'melon_seed_target': 6, 'enable_3b': False}, seed=seed)
    opp_agent = lambda obs: opp_inst(obs)
else:
    opp_agent = 'random'

print(f'Running match for seed {seed} with MasterCounterAgent vs {opp_type}...')
env = make('kaggriculture', configuration={'episodeSteps': 720, 'seed': seed}, debug=True)
env.run([lambda obs: our_agent(obs), opp_agent])

p0_score = env.steps[-1][0]['reward']
p1_score = env.steps[-1][1]['reward']
winner = 'Player 0 (MasterCounterAgent)' if p0_score > p1_score else 'Player 1 (Opponent)'
print(f'Match Result: {winner} (P0: ${p0_score:,.2f} vs P1: ${p1_score:,.2f})')

html = env.render(mode='html', width=1280, height=760)
out_path = 'project_maestro/visualizer/match_visualizer.html'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'SUCCESS: Visualizer rendered to {out_path}')