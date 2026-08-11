import sys
import os
import traceback
from strategy import agent, GLOBAL_PARAMS, _controller
from kaggle_environments import make

def wrapped_agent(obs):
    try:
        acts = agent(obs)
        if obs['player'] == 0:
            money = obs['farms'][0]['money']
            farm = obs['farms'][0]
            melons_planted = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('crop') == 'MELON')
            straw_planted = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('crop') == 'STRAWBERRY')
            weeds = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('kind') == 'WEED')
            
            jobs = [j.type for j in _controller.jobs.values()]
            sys.__stdout__.write(f"Day {obs['step']//24} Hour {obs['step']%24}: Money={money}, Melons={melons_planted}, Straw={straw_planted}, Weeds={weeds}, Hands={len(farm.get('hands', []))}, Farmer={acts.get('farmer')}, HandsActs={[a for a in acts.get('hands', [])]}, Actions={acts.get('market', [])}, Jobs={jobs}\n")
            if "BUY_LAND" in str(acts):
                sys.__stdout__.write(f"BOUGHT LAND on Day {obs['step']//24}\n")
        return acts
    except Exception as e:
        open('err.txt', 'w').write(traceback.format_exc())
        raise

env = make("kaggriculture", configuration={"episodeSteps": 720})
env.run([wrapped_agent, 'random'])
print(f"Final Score: {env.state[0].reward}")
