import json
import os
from kaggle_environments import make

# 1. Load realistic opponent replay from Downloads
replay_path = r'C:\Users\GauravPatel\Downloads\aegis_latest\wins\96036058.json'
with open(replay_path, 'r', encoding='utf-8') as f:
    replay_data = json.load(f)

info = replay_data.get('info', {})
teams = info.get('TeamNames', ['P0', 'P1'])
steps = replay_data['steps']

# Determine opponent seat
opp_seat = 0 if teams[1] == 'Shadow Recon' else 1
opp_name = teams[opp_seat]
print(f"Loaded Replay Sparring Partner: {opp_name} (Seat {opp_seat}) from 96036058.json")

# 2. Build Replay Playback Agent
def replay_opponent_agent(obs):
    step = obs.get('step', 0)
    if step < len(steps):
        act = steps[step][opp_seat].get('action')
        if act:
            return act
    return {"farmer": ["PASS"], "hands": [], "market": []}

print("Replay playback agent successfully constructed!")
