import json
import os

def extract_tape(replay_path, output_path, seat):
    with open(replay_path, encoding='utf-8') as f:
        d = json.load(f)
    
    actions = []
    for step in d['steps']:
        # step[seat] is the player's info for that step.
        # However, the action recorded in step[seat] is what they did PREVIOUSLY.
        # Actually, in Kaggriculture replay format, step[i][seat]['action'] is the action taken AT step i.
        action = step[seat].get('action', {})
        actions.append(action)
    
    # Write to a python file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("TRACE_ACTIONS = [\n")
        for a in actions:
            f.write(f"    {json.dumps(a)},\n")
        f.write("]\n")

extract_tape('episode-104541031-replay.json', 'artifacts/e780_nator_tape/nator_x_seat0.py', 0)
print("Tape extracted successfully.")
