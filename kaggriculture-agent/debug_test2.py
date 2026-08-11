from kaggle_environments import make
from strategy import agent
import sys

def wrapped_agent(obs):
    acts = agent(obs)
    if obs['player'] == 0 and obs['step'] < 60:
        money = obs['farms'][0]['money']
        farm = obs['farms'][0]
        wheat_planted = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('crop') == 'WHEAT')
        geese = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('animal') == 'GOOSE')
        coops = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('kind') == 'COOP')
        shed = obs['private']['shed']
        inv0 = obs['private']['inventories'][0]
        inv1 = obs['private']['inventories'][1] if len(obs['private']['inventories']) > 1 else {}
        print(f'Step {obs["step"]}: Day={obs["step"]//24} Hour={obs["step"]%24} Money={money} Wheat={wheat_planted} Geese={geese} Coops={coops} Shed={shed} Inv0={inv0} Inv1={inv1} Farmer={acts.get("farmer")} Hands={acts.get("hands")} Market={acts.get("market")}')
    return acts

env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True)
env.run([wrapped_agent, 'random'])
print(f'Final Score: {env.state[0].reward}')