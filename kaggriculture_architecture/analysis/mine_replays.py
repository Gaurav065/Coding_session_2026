import os
import json
import glob
from collections import defaultdict

def analyze_replays(replay_dir):
    replay_files = glob.glob(os.path.join(replay_dir, "*.json"))
    print(f"Found {len(replay_files)} replays in {replay_dir}")
    
    results = []
    player_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0, "scores": [], "rewards": []})
    
    for rf in replay_files:
        try:
            with open(rf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check info / players
            info = data.get("info", {})
            agents = data.get("agents", [])
            steps = data.get("steps", [])
            if not steps:
                continue
                
            final_step = steps[-1]
            p0_res = final_step[0]
            p1_res = final_step[1]
            
            p0_reward = p0_res.get("reward", 0)
            p1_reward = p1_res.get("reward", 0)
            p0_status = p0_res.get("status", "UNKNOWN")
            p1_status = p1_res.get("status", "UNKNOWN")
            
            # Names if available in description or agents
            p0_name = agents[0] if len(agents) > 0 else "Player 0"
            p1_name = agents[1] if len(agents) > 1 else "Player 1"
            
            results.append({
                "file": os.path.basename(rf),
                "p0_name": p0_name,
                "p1_name": p1_name,
                "p0_reward": p0_reward,
                "p1_reward": p1_reward,
                "p0_status": p0_status,
                "p1_status": p1_status,
                "total_steps": len(steps)
            })
            
            player_stats[p0_name]["scores"].append(p0_reward)
            player_stats[p1_name]["scores"].append(p1_reward)
            if p0_reward > p1_reward:
                player_stats[p0_name]["wins"] += 1
                player_stats[p1_name]["losses"] += 1
            elif p1_reward > p0_reward:
                player_stats[p1_name]["wins"] += 1
                player_stats[p0_name]["losses"] += 1
            else:
                player_stats[p0_name]["ties"] += 1
                player_stats[p1_name]["ties"] += 1
                
        except Exception as e:
            print(f"Error parsing {rf}: {e}")

    print("\n" + "="*80)
    print(f"PROCESSED {len(results)} REPLAYS")
    print("="*80)
    
    # Sort results by max score
    results.sort(key=lambda x: max(x['p0_reward'] or 0, x['p1_reward'] or 0), reverse=True)
    
    print("\nTOP 25 HIGHEST SCORING MATCHES:")
    for r in results[:25]:
        print(f"{r['file']:<25} | P0: {r['p0_reward']:>8.1f} ({r['p0_status']:<4}) vs P1: {r['p1_reward']:>8.1f} ({r['p1_status']:<4}) | {r['p0_name']} vs {r['p1_name']}")

    print("\nLOWEST / MOST ANOMALOUS MATCHES:")
    for r in results[-15:]:
        print(f"{r['file']:<25} | P0: {r['p0_reward']:>8.1f} ({r['p0_status']:<4}) vs P1: {r['p1_reward']:>8.1f} ({r['p1_status']:<4}) | {r['p0_name']} vs {r['p1_name']}")

    # Save summary
    with open(r'C:\Coding\kaggriculture_architecture\replay_summary.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    analyze_replays(r'C:\Users\GauravPatel\Downloads\new_data_replays_31st_aug')
