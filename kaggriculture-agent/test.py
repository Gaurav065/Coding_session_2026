import sys
import os
import traceback
from strategy import agent
from kaggle_environments import make

def wrapped_agent(obs):
    try:
        acts = agent(obs)
        if obs['player'] == 0:
            money = obs['farms'][0]['money']
            farm = obs['farms'][0]
            wheat_planted = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('crop') == 'WHEAT')
            melons_planted = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('crop') == 'MELON')
            straw_planted = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('crop') == 'STRAWBERRY')
            tomatoes_planted = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('crop') == 'TOMATO')
            weeds = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('kind') == 'WEED')
            geese = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('animal') == 'GOOSE')
            coops = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('kind') == 'COOP')
            
            sys.__stdout__.write(f"Day {obs['step']//24} Hour {obs['step']%24}: Money={money}, Wheat={wheat_planted}, Melons={melons_planted}, Straw={straw_planted}, Tom={tomatoes_planted}, Weeds={weeds}, Geese={geese}, Coops={coops}, Hands={len(farm.get('hands', []))}, Farmer={acts.get('farmer')}, HandsActs={[a for a in acts.get('hands', [])]}, Actions={acts.get('market', [])}\n")
            if "BUY_LAND" in str(acts):
                sys.__stdout__.write(f"BOUGHT LAND on Day {obs['step']//24}\n")
        return acts
    except Exception as e:
        open('err.txt', 'w').write(traceback.format_exc())
        raise

env = make("kaggriculture", configuration={"episodeSteps": 720})
env.run([wrapped_agent, 'random'])
print(f"Final Score: {env.state[0].reward}")