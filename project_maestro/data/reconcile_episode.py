"""Step-by-step Revenue & Volume Reconciliation on 93924742.json"""

import json

def analyze_full_replay(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    steps = data["steps"]
    print(f"Total steps: {len(steps)}")
    
    p0_final = steps[-1][0]["reward"]
    p1_final = steps[-1][1]["reward"]
    print(f"Final Rewards: P0 = ${p0_final:,.2f} | P1 = ${p1_final:,.2f}")

    for p_idx in (0, 1):
        print(f"\n==================== PLAYER {p_idx} RECONSTRUCTION ====================")
        # Track true money deltas step-by-step
        money_history = []
        actual_sells = {}
        actual_revenue_by_prod = {}
        
        # Bounded logic from phase0_analysis.py:
        extractor_sells = {}
        extractor_rev = {}
        
        # Raw orders logic:
        raw_sells = {}
        raw_rev = {}

        total_hires_cost = 0.0
        total_seeds_cost = 0.0
        total_animals_cost = 0.0
        total_land_cost = 0.0

        for s_idx, step_data in enumerate(steps):
            obs = step_data[p_idx].get("observation", {})
            act = step_data[p_idx].get("action", {})
            
            # Pre-step state
            cur_money = obs.get("farms", [{}, {}])[p_idx].get("money", 3000.0)
            money_history.append(cur_money)
            step_shed = dict((obs.get("private", {}) or {}).get("shed", {}) or {})
            market_prices = obs.get("market", {}).get("prices", {})
            
            # Orders in action
            mkt_orders = act.get("market", []) if isinstance(act, dict) else []
            
            # Post-step money (from next step's observation or final reward)
            if s_idx + 1 < len(steps):
                next_obs = steps[s_idx + 1][p_idx].get("observation", {})
                next_money = next_obs.get("farms", [{}, {}])[p_idx].get("money", cur_money)
                next_shed = dict((next_obs.get("private", {}) or {}).get("shed", {}) or {})
            else:
                next_money = steps[-1][p_idx]["reward"]
                next_shed = {}

            delta_m = next_money - cur_money
            
            # Let's inspect what happened in this step:
            for o in mkt_orders:
                if not isinstance(o, list) or len(o) < 1:
                    continue
                cmd = o[0]
                if cmd == "SELL":
                    item = o[1]
                    qty = int(o[2]) if len(o) > 2 else 1
                    price = float(market_prices.get(item, 1))
                    
                    raw_sells[item] = raw_sells.get(item, 0) + qty
                    raw_rev[item] = raw_rev.get(item, 0.0) + qty * price
                    
                    # Extractor bounded logic:
                    avail = step_shed.get(item, 0) if step_shed else qty
                    act_fill = min(qty, avail)
                    extractor_sells[item] = extractor_sells.get(item, 0) + act_fill
                    extractor_rev[item] = extractor_rev.get(item, 0.0) + act_fill * price
                    
                    # True delta shed for this item:
                    shed_before = step_shed.get(item, 0)
                    shed_after = next_shed.get(item, 0)
                    # Note: if a worker harvested or dropped in the same turn, shed_after could be different

        print(f"Starting Cash: $3,000.00")
        print(f"Ending Cash (True Reward): ${steps[-1][p_idx]['reward']:,.2f}")
        print("\n--- EXTRACTOR BOUNDED SUMMARY (What phase0_analysis extracted) ---")
        total_ext_rev = sum(extractor_rev.values())
        print(f"Total Extracted Revenue: ${total_ext_rev:,.2f}")
        for k in sorted(extractor_sells.keys()):
            print(f"  {k:<12}: {extractor_sells[k]:>5} units | ${extractor_rev[k]:>10,.2f}")

        print("\n--- RAW ORDER SUMMARY (If every SELL order was counted in full) ---")
        total_raw_rev = sum(raw_rev.values())
        print(f"Total Raw Order Revenue: ${total_raw_rev:,.2f}")
        for k in sorted(raw_sells.keys()):
            print(f"  {k:<12}: {raw_sells[k]:>5} units | ${raw_rev[k]:>10,.2f}")

if __name__ == "__main__":
    analyze_full_replay(r"C:\Coding\kaggriculture-agent\replays\93924742.json")
