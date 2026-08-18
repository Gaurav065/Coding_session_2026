import json
import zlib
import base64
import importlib.util

def load_current_tape():
    spec = importlib.util.spec_from_file_location("main", "C:/Coding/main.py")
    main_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(main_mod)
    tape_json = zlib.decompress(base64.b64decode(main_mod.TAPE_B64)).decode('utf-8')
    return json.loads(tape_json)

def normalize_action(action):
    # Remove trailing PASS actions from hands since they are implicit
    if 'hands' in action:
        hands = action['hands']
        while len(hands) > 0 and hands[-1] == ['PASS']:
            hands.pop()
    return action

def main():
    rp = 'C:/Users/GauravPatel/Downloads/93924742.json'
    with open(rp, 'r') as f:
        data = json.load(f)
        
    steps = data.get('steps', [])
    if not steps: return
    
    final_step = steps[-1]
    rewards = [state.get('reward', 0) for state in final_step]
    winner_idx = 0 if rewards[0] > rewards[1] else 1
    
    our_tape = load_current_tape()
    winner_tape = []
    for i in range(1, len(steps)):
        winner_tape.append(steps[i][winner_idx].get('action', {}))
        
    i = 0
    while i < min(len(our_tape), len(winner_tape)) and normalize_action(our_tape[i]) == normalize_action(winner_tape[i]):
        i += 1
        
    print(f'Winner tape matches CURRENT main.py tape for first {i} steps.')

if __name__ == '__main__':
    main()
