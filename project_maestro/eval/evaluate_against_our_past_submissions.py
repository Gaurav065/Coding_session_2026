"""Evaluation Suite against our Past 3 Kaggle Submissions

Evaluates IDCMasterAgent directly against the 15 recorded tournament replays
from our previous submissions on Kaggle (Submissions 55662960, 55644761, 55617552).
"""

import sys
import json
import glob
import numpy as np

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.idc_master_agent import IDCMasterAgent

def evaluate_past_submissions():
    replay_files = glob.glob('past_submissions_data/*.json')
    print(f'Evaluating IDCMasterAgent against {len(replay_files)} real matches from our past Kaggle submissions...\n')

    wins = 0
    our_scores = []
    past_agent_scores = []
    match_details = []

    for idx, fpath in enumerate(replay_files):
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        steps = data.get('steps', [])
        config = data.get('configuration', {})
        seed = config.get('seed', 42 + idx)

        # Check which player index was our past agent (index 0 or 1)
        # Look at final step rewards
        s0 = steps[-1][0].get('reward', 0) or 0
        s1 = steps[-1][1].get('reward', 0) or 0

        # Simulate game where P0 = IDCMasterAgent, P1 = Past Agent's recorded actions
        g = FastGame(seed=seed)
        cand = IDCMasterAgent(seed=seed)

        for step_idx in range(min(720, len(steps))):
            obs0 = g.get_observation(0)
            act0 = cand(obs0)

            # Replay past agent's action
            past_act = steps[step_idx][0].get('action', {})
            if not isinstance(past_act, dict):
                past_act = {"farmer": ["PASS"], "hands": [], "market": []}

            g.step_game(act0, past_act)

        f0_score = g.farms[0].money
        f1_score = g.farms[1].money

        our_scores.append(f0_score)
        past_agent_scores.append(f1_score)
        is_win = f0_score > f1_score
        if is_win:
            wins += 1

        match_name = fpath.split('\\')[-1].split('/')[-1]
        print(f'Match {idx+1:2d} ({match_name}): {"WIN " if is_win else "LOSS"} | Our Agent: ${f0_score:9.2f} vs Past Agent: ${f1_score:9.2f} (Margin: +${f0_score - f1_score:7.2f})')

    win_rate = (wins / len(replay_files)) * 100
    mean_our = float(np.mean(our_scores))
    mean_past = float(np.mean(past_agent_scores))
    margin = mean_our - mean_past
    p5_our = float(np.percentile(our_scores, 5))

    print('\n' + '=' * 95)
    print('HEAD-TO-HEAD BENCHMARK: IDCMasterAgent vs OUR PAST KAGGLE SUBMISSIONS')
    print('=' * 95)
    print(f'Win Rate vs Past Submissions : {win_rate:5.1f}% ({wins}/{len(replay_files)} Wins)')
    print(f'Our Average Bank Balance     : ${mean_our:10,.2f}')
    print(f'Past Submissions Mean Score  : ${mean_past:10,.2f}')
    print(f'Net Outperformance Margin    : +${margin:9,.2f}')
    print(f'p5 Risk Floor Protection     : ${p5_our:10,.2f}')
    print('=' * 95)

    out_file = 'project_maestro/data/past_submissions_head_to_head_results.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({
            "total_matches": len(replay_files),
            "win_rate": win_rate,
            "our_mean": mean_our,
            "past_submissions_mean": mean_past,
            "net_margin": margin,
            "our_scores": our_scores,
            "past_scores": past_agent_scores
        }, f, indent=2)
    print(f'\nDetailed benchmark report saved to {out_file}')

if __name__ == '__main__':
    evaluate_past_submissions()
