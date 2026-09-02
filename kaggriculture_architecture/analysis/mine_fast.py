import os
import json
import glob
from concurrent.futures import ProcessPoolExecutor

def parse_single_replay(rf):
    try:
        with open(rf, 'r', encoding='utf-8') as f:
            data = json.load(f)
        steps = data.get("steps", [])
        if not steps:
            return None
        final_step = steps[-1]
        p0_res = final_step[0]
        p1_res = final_step[1]
        
        agents = data.get("agents", ["P0", "P1"])
        p0_name = agents[0] if len(agents) > 0 else "Player 0"
        p1_name = agents[1] if len(agents) > 1 else "Player 1"
        
        # Check starting money and progression at turn 100, 300, 500, 715, 718
        p0_curve = []
        p1_curve = []
        for t in [0, 100, 300, 500, 700, 715, len(steps)-1]:
            if t < len(steps):
                st = steps[t]
                # farm money
                obs0 = st[0].get("observation", {})
                farms = obs0.get("farms", [{}, {}])
                m0 = farms[0].get("money", 0) if len(farms) > 0 else 0
                m1 = farms[1].get("money", 0) if len(farms) > 1 else 0
                p0_curve.append((t, m0))
                p1_curve.append((t, m1))

        return {
            "file": os.path.basename(rf),
            "p0_name": str(p0_name),
            "p1_name": str(p1_name),
            "p0_reward": p0_res.get("reward", 0),
            "p1_reward": p1_res.get("reward", 0),
            "p0_status": p0_res.get("status", "UNKNOWN"),
            "p1_status": p1_res.get("status", "UNKNOWN"),
            "total_steps": len(steps),
            "p0_curve": p0_curve,
            "p1_curve": p1_curve
        }
    except Exception as e:
        return {"file": os.path.basename(rf), "error": str(e)}

def main():
    replay_dir = r'C:\Users\GauravPatel\Downloads\new_data_replays_31st_aug'
    replay_files = glob.glob(os.path.join(replay_dir, "*.json"))
    print(f"Parsing {len(replay_files)} files using multiprocessing...")
    
    results = []
    with ProcessPoolExecutor(max_workers=6) as executor:
        for res in executor.map(parse_single_replay, replay_files):
            if res and "error" not in res:
                results.append(res)
    
    results.sort(key=lambda x: max(x['p0_reward'] or 0, x['p1_reward'] or 0), reverse=True)
    
    out_path = r'C:\Coding\kaggriculture_architecture\replay_summary.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
        
    print(f"Successfully processed {len(results)} replays!")
    print("\nTop 20 matches:")
    for r in results[:20]:
        print(f"{r['file']:<25} | P0: {r['p0_reward']:>8.1f} ({r['p0_status']:<4}) vs P1: {r['p1_reward']:>8.1f} ({r['p1_status']:<4})")
    print("\nBottom 10 matches:")
    for r in results[-10:]:
        print(f"{r['file']:<25} | P0: {r['p0_reward']:>8.1f} ({r['p0_status']:<4}) vs P1: {r['p1_reward']:>8.1f} ({r['p1_status']:<4})")

if __name__ == '__main__':
    main()
