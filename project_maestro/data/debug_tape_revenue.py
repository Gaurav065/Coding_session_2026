"""Inspect Replay Tapes & SELL Reconciliation

Verifies how SELL orders and farm money change step-by-step in actual Kaggle replay tapes.
"""

import json
import os
import glob

def check_tape(tape_path):
    print("=" * 80)
    print(f"Inspecting: {os.path.basename(tape_path)}")
    print("=" * 80)
    with open(tape_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if isinstance(data, dict):
        steps = data.get("steps", [])
    elif isinstance(data, list):
        steps = data
    else:
        print("Unknown format")
        return
    print(f"Total steps: {len(steps)}")
    
    # Check final reward
    p0_reward = steps[-1][0].get("reward", 0)
    p1_reward = steps[-1][1].get("reward", 0)
    print(f"Final Rewards: P0 = ${p0_reward:,.2f} | P1 = ${p1_reward:,.2f}")
    
    # Inspect step 0 and step 1 observations
    obs0_p0 = steps[0][0].get("observation", {})
    obs0_p1 = steps[0][1].get("observation", {})
    print(f"Step 0 obs keys: {list(obs0_p0.keys())}")
    print(f"Step 0 private keys P0: {list(obs0_p0.get('private', {}).keys()) if obs0_p0.get('private') else None}")
    print(f"Step 0 private keys P1: {list(obs0_p1.get('private', {}).keys()) if obs0_p1.get('private') else None}")
    
    # Check if observation has 'farms'
    farms0 = obs0_p0.get("farms", [])
    print(f"Farms count: {len(farms0)}")
    if farms0:
        print(f"Farm 0 starting money: {farms0[0].get('money')}")
        print(f"Farm 1 starting money: {farms0[1].get('money')}")
        
    # Track money changes across steps
    # In kaggriculture: farm money is in obs['farms'][p]['money']
    # And reward at step t is farm['money']!
    
    # Let's trace all SELL actions and money deltas for P0 and P1
    for p_idx in [0, 1]:
        p_reward = p0_reward if p_idx == 0 else p1_reward
        print(f"\n--- PLAYER {p_idx} TRACE (Final Reward: ${p_reward:,.2f}) ---")
        
        running_calc_rev = 0.0
        sells_raw = {}
        sells_bounded = {}
        
        # Let's track delta money across steps
        prev_money = 3000.0
        total_money_inflows = 0.0
        total_money_outflows = 0.0
        
        for step_idx in range(len(steps)):
            s_data = steps[step_idx][p_idx]
            obs = s_data.get("observation", {})
            act = s_data.get("action", {})
            
            farm = obs.get("farms", [{}, {}])[p_idx]
            cur_money = farm.get("money", 3000.0)
            
            # Action taken at this step
            mkt_orders = act.get("market", []) if isinstance(act, dict) else []
            
            # Let's see what happens to money in the next step
            next_step_idx = step_idx + 1
            if next_step_idx < len(steps):
                next_obs = steps[next_step_idx][p_idx].get("observation", {})
                next_farm = next_obs.get("farms", [{}, {}])[p_idx]
                next_money = next_farm.get("money", cur_money)
            else:
                next_money = p_reward
                
            delta_m = next_money - cur_money
            if delta_m > 0:
                total_money_inflows += delta_m
            elif delta_m < 0:
                total_money_outflows += (-delta_m)
                
            # Check market orders
            step_shed = dict((obs.get("private", {}) or {}).get("shed", {}) or {})
            market_prices = obs.get("market", {}).get("prices", {})
            
            for o in mkt_orders:
                if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL":
                    item = o[1]
                    qty = int(o[2]) if len(o) > 2 else 1
                    sells_raw[item] = sells_raw.get(item, 0) + qty
                    
                    # What price was quoted?
                    cur_p = market_prices.get(item, 1)
                    
                    # Bounded check from phase0_analysis.py:
                    avail = step_shed.get(item, 0) if step_shed else qty
                    actual_fill = min(qty, avail)
                    sells_bounded[item] = sells_bounded.get(item, 0) + actual_fill
                    
                    if delta_m > 0:
                        # Market orders generated revenue this step
                        pass
                        
        print(f"Total Money Inflows (Revenue):  ${total_money_inflows:,.2f}")
        print(f"Total Money Outflows (Costs):    ${total_money_outflows:,.2f}")
        print(f"Net Money (Starting + In - Out): ${3000.0 + total_money_inflows - total_money_outflows:,.2f}")
        print(f"Raw Orders:     {sells_raw}")
        print(f"Bounded Orders: {sells_bounded}")

if __name__ == "__main__":
    tapes = glob.glob(r"C:\Coding\kaggriculture-agent\*.json") + glob.glob(r"C:\Coding\kaggriculture-agent\archive\*.json")
    for t in tapes[:5]:
        check_tape(t)
