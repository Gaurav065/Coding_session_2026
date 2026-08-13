import os
import json

replay_path = os.environ.get('REPLAY_PATH')
with open(replay_path) as f:
    replay_data = json.load(f)

# Find the winner
rewards = replay_data.get('rewards', [0, 0])
# We want to simulate the player with the highest score
player_id = 0 if rewards[0] > rewards[1] else 1

steps = replay_data['steps']

def agent(obs, conf):
    step = obs.step
    if step < len(steps):
        actions = steps[step]
        if len(actions) > player_id and actions[player_id]:
            return actions[player_id].get('action', {})
    return {}
