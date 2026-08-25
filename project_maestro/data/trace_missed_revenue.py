"""Find where the money came from in 93924742.json step-by-step"""

import json

def trace_money_sources(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    steps = data["steps"]
    
    for p_idx in [0]:
        print(f"=== DETAILED STEP TRACE FOR PLAYER {p_idx} ===")
        cum_delta_m = 0.0
        
        missed_revenue_steps = 0
        total_missed_rev = 0.0

        for s_idx in range(len(steps) - 1):
            obs = steps[s_idx][p_idx].get("observation", {})
            next_obs = steps[s_idx + 1][p_idx].get("observation", {})
            act = steps[s_idx][p_idx].get("action", {})
            
            cur_money = obs.get("farms", [{}, {}])[p_idx].get("money", 3000.0)
            next_money = next_obs.get("farms", [{}, {}])[p_idx].get("money", cur_money)
            delta_m = next_money - cur_money
            
            step_shed = dict((obs.get("private", {}) or {}).get("shed", {}) or {})
            next_shed = dict((next_obs.get("private", {}) or {}).get("shed", {}) or {})
            mkt_orders = act.get("market", []) if isinstance(act, dict) else []
            prices = obs.get("market", {}).get("prices", {})
            
            # Let's compute extractor's credited revenue for this step:
            extractor_step_rev = 0.0
            temp_shed = dict(step_shed)
            for o in mkt_orders:
                if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL":
                    item = o[1]
                    qty = int(o[2]) if len(o) > 2 else 1
                    avail = temp_shed.get(item, 0)
                    fill = min(qty, avail)
                    if fill > 0:
                        p = float(prices.get(item, 1))
                        extractor_step_rev += fill * p
                        temp_shed[item] -= fill
                        
            # If delta_m > 0 (player gained money):
            if delta_m > 0:
                if abs(delta_m - extractor_step_rev) > 1.0:
                    missed_revenue_steps += 1
                    diff = delta_m - extractor_step_rev
                    total_missed_rev += diff
                    if missed_revenue_steps <= 15:
                        print(f"Step {s_idx:3d} (Day {s_idx//24:2d} Hr {s_idx%24:2d}): Delta Money = +${delta_m:>7.2f} | Extractor Credited = ${extractor_step_rev:>7.2f} | Diff = +${diff:>7.2f}")
                        print(f"   Pre-shed:  {step_shed}")
                        print(f"   Post-shed: {next_shed}")
                        print(f"   Market Orders: {mkt_orders}")
                        print(f"   Farmer Action: {act.get('farmer')}")
                        print(f"   Hands Actions: {act.get('hands', [])[:4]}")
                        
        print(f"\nTotal Missed Revenue Steps: {missed_revenue_steps}")
        print(f"Total Missed Revenue: ${total_missed_rev:,.2f}")

if __name__ == "__main__":
    trace_money_sources(r"C:\Coding\kaggriculture-agent\replays\93924742.json")
