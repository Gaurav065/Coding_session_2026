from kaggle_environments import make
import continuous_agent.final_submission as fs
_old_agent = fs.agent
def wrapped_agent(obs):
    act = _old_agent(obs)
    if act['market']:
        print("Step", obs["step"], "market", act["market"])
    return act
fs.agent = wrapped_agent
env = make('kaggriculture', configuration={'episodeSteps': 720}, debug=True)
env.run([fs.agent, 'random'])
