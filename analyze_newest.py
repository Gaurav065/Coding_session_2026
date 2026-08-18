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

def main():
    rp = 'C:/Users/GauravPatel/Downloads/93924742.json'
    with open(rp, 'r') as f:
        data = json.load(f)
        
    steps = data.get('steps', [])
    if not steps: return
    
    final_step = steps[-1]
    rewards = [state.get('reward', 0) for state in final_step]
    winner_idx = 0 if rewards[0] > rewards[1] else 1
    
    print(f"P0: {data['info']['TeamNames'][0]} ({rewards[0]})")
    print(f"P1: {data['info']['TeamNames'][1]} ({rewards[1]})")
    print(f"Winner is Player {winner_idx}")
    
    our_tape = load_current_tape()
    winner_tape = []
    for i in range(1, len(steps)):
        winner_tape.append(steps[i][winner_idx].get('action', {}))
        
    i = 0
    while i < min(len(our_tape), len(winner_tape)) and our_tape[i] == winner_tape[i]:
        i += 1
        
    print(f'Winner tape matches CURRENT main.py tape for first {i} steps.')
    if i < min(len(our_tape), len(winner_tape)):
        print(f"Our tape step {i}: {our_tape[i]}")
        print(f"Winner tape step {i}: {winner_tape[i]}")

if __name__ == '__main__':
    main()
