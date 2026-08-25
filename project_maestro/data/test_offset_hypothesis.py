"""Test Replay Step Offset Hypothesis

Validates whether steps[s_idx].action executes on steps[s_idx-1].observation vs steps[s_idx].observation.
"""

import json

def test_offset_hypothesis(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    steps = data["steps"]

    p0_final = steps[-1][0]["reward"]
    print(f"P0 Final Reward: ${p0_final:,.2f}")

    for p_idx in [0]:
        # Method A: Previous extractor (bounding on current step observation)
        ext_rev_A = 0.0
        ext_sells_A = {}

        # Method B: Bounding on PREVIOUS step observation (s_idx - 1)
        ext_rev_B = 0.0
        ext_sells_B = {}

        # Method C: Tracking shed balance with inflow/outflow from interpreter
        # Method D: Exact simulation with FastGame / Engine
        
        for s_idx, step_data in enumerate(steps):
            obs = step_data[p_idx].get("observation", {})
            act = step_data[p_idx].get("action", {})
            mkt = act.get("market", []) if isinstance(act, dict) else []
            
            # Pre-obs from s_idx - 1:
            pre_obs = steps[s_idx - 1][p_idx].get("observation", {}) if s_idx > 0 else obs
            pre_shed = dict((pre_obs.get("private", {}) or {}).get("shed", {}) or {})
            cur_shed = dict((obs.get("private", {}) or {}).get("shed", {}) or {})
            
            prices = obs.get("market", {}).get("prices", {})
            
            for o in mkt:
                if isinstance(o, list) and len(o) >= 2 and o[0] == "SELL":
                    item = o[1]
                    qty = int(o[2]) if len(o) > 2 else 1
                    p = float(prices.get(item, 1))

                    # Method A (Buggy: checked post-step shed)
                    avail_A = cur_shed.get(item, 0)
                    fill_A = min(qty, avail_A)
                    ext_sells_A[item] = ext_sells_A.get(item, 0) + fill_A
                    ext_rev_A += fill_A * p
                    cur_shed[item] -= fill_A

                    # Method B (Checked pre-step shed from s_idx - 1)
                    avail_B = pre_shed.get(item, 0)
                    fill_B = min(qty, avail_B)
                    ext_sells_B[item] = ext_sells_B.get(item, 0) + fill_B
                    ext_rev_B += fill_B * p
                    pre_shed[item] -= fill_B

        print(f"\nMethod A (Current Extractor): Total Revenue = ${ext_rev_A:,.2f}")
        print(f"  Sales: {ext_sells_A}")
        print(f"\nMethod B (Pre-step Shed):   Total Revenue = ${ext_rev_B:,.2f}")
        print(f"  Sales: {ext_sells_B}")

if __name__ == "__main__":
    test_offset_hypothesis(r"C:\Coding\kaggriculture-agent\replays\93924742.json")
