from kaggle_environments import make
import time

def run_match():
    print("Initializing full match: Phase F (Seat 0) vs Original Phase E (Seat 1)...")
    env = make("kaggriculture", debug=True)
    
    agent_f = r"C:\Coding\kaggriculture_architecture\submission_phase_f.py"
    agent_orig = r"C:\Coding\kaggriculture_architecture\submission\submission.py"
    
    start_time = time.time()
    steps = env.run([agent_f, agent_orig])
    duration = time.time() - start_time
    
    final_obs = steps[-1][0]["observation"]
    
    score_f = final_obs["farms"][0]["money"]
    score_orig = final_obs["farms"][1]["money"]
    
    print(f"Match finished in {duration:.2f} seconds!")
    print(f"Total Steps: {len(steps)}")
    print(f"Phase F Score (Seat 0): {score_f}")
    print(f"Original Agent Score (Seat 1): {score_orig}")
    
    if score_f > score_orig:
        print(f"Phase F wins by {score_f - score_orig}!")
    elif score_orig > score_f:
        print(f"Original wins by {score_orig - score_f}!")
    else:
        print("TIE!")

if __name__ == "__main__":
    run_match()
