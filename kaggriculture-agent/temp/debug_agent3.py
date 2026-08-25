from kaggle_environments import make
import continuous_agent.final_submission as fs
_old_agent = fs.agent
def wrapped_agent(obs):
    act = _old_agent(obs)
    step = obs['step']
    if step in [24, 25, 26, 48, 49, 50, 72, 73, 74]:
        farm = obs['farms'][0]
        plants = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('kind') == 'PLANT')
        weeds = sum(1 for row in farm['tiles'] for t in row if isinstance(t, dict) and t.get('kind') == 'WEED')
        num_hands = len(farm.get('hands') or [])
        print("Step", step, "money=", farm.get('money'), "hands=", num_hands, "plants=", plants, "weeds=", weeds, "shed=", obs['private'].get('shed'))
    return act
fs.agent = wrapped_agent
env = make('kaggriculture', configuration={'episodeSteps': 100}, debug=True)
env.run([fs.agent, 'random'])
