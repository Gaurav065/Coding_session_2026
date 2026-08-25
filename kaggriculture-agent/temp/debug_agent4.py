from kaggle_environments import make
import continuous_agent.final_submission as fs
_old_agent = fs.agent
def wrapped_agent(obs):
    act = _old_agent(obs)
    if obs['step'] < 10:
        print("Step", obs['step'], act['farmer'], act.get('hands'))
        farm = obs['farms'][0]
        tiles = farm['tiles']
        pos = farm['farmer']
        print("Farmer tile:", tiles[pos[1]][pos[0]])
    return act
fs.agent = wrapped_agent
env = make('kaggriculture', configuration={'episodeSteps': 100}, debug=True)
env.run([fs.agent, 'random'])
