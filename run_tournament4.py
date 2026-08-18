import json
import glob
import zlib
import base64
import importlib.util
from kaggle_environments import make

def generate_agent_code(tape_list):
    tape_str = json.dumps(tape_list)
    b64_tape = base64.b64encode(zlib.compress(tape_str.encode('utf-8'))).decode('ascii')
    code = f"""import json
import zlib
import base64

TAPE_B64 = "{b64_tape}"
_tape = None

def agent(obs, config=None):
    global _tape
    if _tape is None:
        _tape = json.loads(zlib.decompress(base64.b64decode(TAPE_B64)).decode('utf-8'))
    
    step = obs.get('step', 0) if isinstance(obs, dict) else getattr(obs, 'step', 0)
    
    if step < len(_tape):
        return _tape[step]
    return {{'farmer': ['PASS'], 'hands': [], 'market': []}}
"""
    return code

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
    our_tape = load_current_tape()
    replays = glob.glob('C:/Coding/replays4/*.json')
    
    candidates = []
    
    for rp in replays:
        with open(rp, 'r') as f:
            data = json.load(f)
            
        steps = data.get('steps', [])
        if not steps: continue
        
        final_step = steps[-1]
        rewards = [state.get('reward', 0) for state in final_step]
        winner_idx = 0 if rewards[0] > rewards[1] else 1
        
        # Extract winner's tape
        winner_tape = []
        for i in range(1, len(steps)):
            winner_tape.append(steps[i][winner_idx].get('action', {}))
            
        # Verify it matches our tape for the first 100 steps
        match = True
        for i in range(100):
            if i < len(our_tape) and i < len(winner_tape):
                if normalize_action(our_tape[i]) != normalize_action(winner_tape[i]):
                    match = False
                    break
            else:
                match = False
                break
                
        if match:
            candidates.append({
                'replay': rp,
                'tape': winner_tape,
                'original_score': rewards[winner_idx]
            })
            print(f"Candidate found from {rp} (Score: {rewards[winner_idx]})")
        else:
            print(f"Replay {rp} rejected (opening diverged).")
            
    if not candidates:
        print("No candidates matched the opening! Aborting tournament.")
        return
        
    print(f"Total candidates: {len(candidates)}")
    
    # Run tournament
    best_avg_score = -1
    best_tape = None
    best_replay = None
    
    SEEDS = [100, 200, 300, 400, 500]
    
    for i, c in enumerate(candidates):
        # Write temporary agent
        agent_code = generate_agent_code(c['tape'])
        agent_file = f'C:/Coding/candidate4_{i}.py'
        with open(agent_file, 'w') as f:
            f.write(agent_code)
            
        print(f"Evaluating candidate {i} from {c['replay']}...")
        total_score = 0
        for seed in SEEDS:
            env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
            env.run([agent_file, "random"])
            final = env.steps[-1]
            score = final[0].reward
            total_score += score
        
        avg_score = total_score / len(SEEDS)
        print(f"  Avg Score: {avg_score}")
        
        if avg_score > best_avg_score:
            best_avg_score = avg_score
            best_tape = c['tape']
            best_replay = c['replay']
            
    print(f"\nWINNER: {best_replay} with avg score {best_avg_score}")
    
    # Check baseline (our current tape)
    print("Evaluating current baseline tape...")
    baseline_total = 0
    for seed in SEEDS:
        env = make("kaggriculture", configuration={"episodeSteps": 720, "seed": seed}, debug=False)
        env.run(["C:/Coding/main.py", "random"])
        baseline_total += env.steps[-1][0].reward
    baseline_avg = baseline_total / len(SEEDS)
    print(f"Baseline Avg Score: {baseline_avg}")
    
    if best_avg_score > baseline_avg:
        # Generate final main.py
        final_code = generate_agent_code(best_tape)
        with open('C:/Coding/main.py', 'w') as f:
            f.write(final_code)
        print(f"Final main.py updated with tape from {best_replay}! (+{best_avg_score - baseline_avg} improvement)")
    else:
        print("None of the candidates beat our current baseline on average.")

if __name__ == '__main__':
    main()
