from kaggle_environments import make
import continuous_agent.final_submission as fs
_old_agent = fs.agent
def wrapped_agent(obs):
    act = _old_agent(obs)
    if obs['step'] < 3:
        print("Step", obs['step'], "farmer=", act['farmer'], "hands=", act.get('hands'))
    return act
fs.agent = wrapped_agent
env = make('kaggriculture', configuration={'episodeSteps': 10}, debug=True)
env.run([fs.agent, 'random'])
