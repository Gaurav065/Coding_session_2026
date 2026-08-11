from kaggle_environments import make
from strategy import agent
import sys

def wrapped_agent(obs):
    acts = agent(obs)
    if obs['player'] == 0 and obs['step'] < 20:
        money = obs['farms'][0]['money']
        farm = obs['farms'][0]
        wheat_planted = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('crop') == 'WHEAT')
        geese = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('animal') == 'GOOSE')
        coops = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('kind') == 'COOP')
        shed = obs['private']['shed']
        seeds = obs['private']['seeds']
        inv = obs['private']['inventories'][0]
        print(f'Step {obs["step"]}: Money={money}, Wheat={wheat_planted}, Geese={geese}, Coops={coops}, Hands={len(farm.get("hands", []))}, Shed={shed}, Seeds={seeds}, Inv={inv}, Farmer={acts.get("farmer")}, HandsActs={acts.get("hands")}, Market={acts.get("market")}')
    return acts

env = make('kaggriculture', configuration={'episodeSteps': 50}, debug=True)
env.run([wrapped_agent, 'random'])
print(f'Score: {env.state[0].reward}')