"""Detailed Observational Dissection of the Last 3 Matches (Submission 55793820)"""

import json
import glob
from collections import defaultdict

MATCHES = [
    ("Match 1 (Public Ladder)", "replays/episode-100043350-replay.json"),
    ("Match 2 (Public Ladder)", "replays/episode-100041068-replay.json"),
    ("Match 3 (Validation Match)", "replays/episode-100036837-replay.json"),
]

def analyze_matches():
    print('=' * 115)
    print('DETAILED OBSERVATIONAL ANALYSIS OF THE LAST 3 MATCHES (SUBMISSION 55793820)')
    print('=' * 115)

    for title, fpath in MATCHES:
        print(f'\n--- {title} [{fpath}] ---')
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        steps = data.get('steps', [])
        config = data.get('configuration', {})
        seed = config.get('seed', 'Unknown')

        final_step = steps[-1]
        s0 = final_step[0].get('reward', 0) or 0
        s1 = final_step[1].get('reward', 0) or 0
        status0 = final_step[0].get('status', 'UNKNOWN')
        status1 = final_step[1].get('status', 'UNKNOWN')

        # Determine which player is our agent
        # Our agent executes specific actions like BUY_PRODUCT WHEAT 10, BUY_ANIMAL COW 4 on Step 0
        act0_0 = steps[0][0].get('action', {})
        act1_0 = steps[0][1].get('action', {})
        
        # Check market orders on step 0
        p0_orders = act0_0.get('market', []) if isinstance(act0_0, dict) else []
        p1_orders = act1_0.get('market', []) if isinstance(act1_0, dict) else []

        our_idx = 0 if ['BUY_ANIMAL', 'COW', 4] in p0_orders else 1
        opp_idx = 1 - our_idx

        our_score = s0 if our_idx == 0 else s1
        opp_score = s1 if our_idx == 0 else s0
        our_status = status0 if our_idx == 0 else status1
        opp_status = status1 if our_idx == 0 else status0

        outcome = "WON" if our_score > opp_score else ("TIED" if our_score == opp_score else "LOST")

        print(f'Seed: {seed} | Our Player Index: Player {our_idx}')
        print(f'Result: {outcome} | Our Score: ${our_score:8,.2f} vs Opponent: ${opp_score:8,.2f} (Lead Margin: +${our_score - opp_score:8,.2f})')
        print(f'Status: Our: {our_status} | Opponent: {opp_status}')

        # Telemetry across turns
        our_sales = defaultdict(int)
        our_actions = defaultdict(int)
        opp_actions = defaultdict(int)

        for s_idx, step_data in enumerate(steps):
            # Our action
            our_act = step_data[our_idx].get('action', {})
            if isinstance(our_act, dict):
                # Market
                for m in our_act.get('market', []):
                    if m and m[0] == 'SELL' and len(m) >= 3:
                        our_sales[m[1]] += int(m[2])
                # Unit
                all_u = [our_act.get('farmer', ['PASS'])] + our_act.get('hands', [])
                for u in all_u:
                    if u:
                        our_actions[u[0]] += 1

            # Opp action
            opp_act = step_data[opp_idx].get('action', {})
            if isinstance(opp_act, dict):
                all_u_opp = [opp_act.get('farmer', ['PASS'])] + opp_act.get('hands', [])
                for u in all_u_opp:
                    if u:
                        opp_actions[u[0]] += 1

        print('\n  Our Produce Sold:')
        for item, qty in sorted(our_sales.items(), key=lambda x: x[1], reverse=True):
            print(f'    • {item:<12}: {qty:4d} units')

        print('\n  Our Core Field Actions:')
        print(f'    • WATER Actions     : {our_actions["WATER"]:,}')
        print(f'    • CARE Actions      : {our_actions["CARE"]:,}')
        print(f'    • FEED Actions      : {our_actions["FEED"]:,}')
        print(f'    • HARVEST Actions   : {our_actions["HARVEST"]:,}')
        print(f'    • BUILD_PASTURE     : {our_actions["BUILD_PASTURE"]:,}')
        print(f'    • DROP Actions      : {our_actions["DROP"]:,}')

if __name__ == '__main__':
    analyze_matches()
