import os
import json
import pandas as pd
from kaggle_environments import make

def evaluate():
    print("Initializing Local Kaggle Environment...")
    # Initialize the official Kaggle environment for Kaggriculture
    # (Assuming the environment name is 'kaggriculture' or similar. If not installed in kaggle-envs, 
    # we can use our FastGame to generate a log, but kaggle_environments gives the beautiful HTML visualizer!)
    try:
        env = make("kaggriculture", debug=True)
    except Exception as e:
        print(f"Failed to load Kaggle environment: {e}")
        print("Please ensure 'kaggle-environments' is installed and supports Kaggriculture.")
        return

    print("Running match: PPO_ResNet_Agent vs Heuristic_Agent...")
    
    # Run the episode
    steps = env.run(["submission_agent.py", "hrl_heuristic_agent.py"])
    
    print("Match Complete! Generating HTML Visualizer...")
    # Render to HTML
    html_out = env.render(mode="html")
    with open("local_evaluation.html", "w", encoding="utf-8") as f:
        f.write(html_out)
    print("✅ Saved visualizer to 'local_evaluation.html'. Open this in your browser!")

    # Analyze the logs for liquidation and economy
    print("\n--- Match Analysis ---")
    log_data = []
    
    for i, step in enumerate(steps):
        # We only log at the end of every day (every 24 steps) and the very last step
        if i % 24 == 0 or i == len(steps) - 1:
            obs = step[0].observation
            farm = obs["farms"][0]
            money = farm["money"]
            shed = obs.get("private", {}).get("shed", {})
            inventory_count = sum(shed.values())
            
            day = i // 24
            log_data.append({
                "Step": i,
                "Day": day,
                "Bank_Balance": money,
                "Items_in_Shed": inventory_count,
                "Reward": step[0].reward
            })
            
    df = pd.DataFrame(log_data)
    df.to_csv("match_economy_log.csv", index=False)
    
    print("\nEconomy Trajectory (End of every 3 Days):")
    print(df[df['Day'] % 3 == 0].to_string(index=False))
    
    final_step = df.iloc[-1]
    print(f"\nFinal Bank Balance: {final_step['Bank_Balance']}")
    print(f"Final Unsold Inventory Items: {final_step['Items_in_Shed']}")
    
    if final_step['Items_in_Shed'] > 0:
        print("⚠️ WARNING: The agent did NOT liquidate its inventory on the final step!")
    else:
        print("✅ SUCCESS: The agent perfectly liquidated its inventory for maximum cash!")

if __name__ == "__main__":
    evaluate()
