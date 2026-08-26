"""Replay-Based Real-World Match Evaluation Suite for Project Maestro

Plays MasterCounterAgent directly against the historical action trajectories of
top-tier tournament matches mined from the official Kaggle dataset.
"""

import os
import glob
import json
import numpy as np
from typing import Dict, List, Any
import sys

sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.master_counter_agent import MasterCounterAgent

def evaluate_against_real_replays(max_matches: int = 50):
    files = glob.glob('kaggle_top_tier_data/*.json')
    print(f'Found {len(files)} top-tier replay files. Selecting top {max_matches} elite matches...\n')

    # Filter for matches where the winner scored >= $70,000
    elite_files = []
    for fpath in files:
        if os.path.getsize(fpath) < 10000:
            continue
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                d = json.load(f)
            steps = d.get('steps', [])
            if len(steps) >= 720:
                s0 = steps[-1][0].get('reward', 0) or 0
                s1 = steps[-1][1].get('reward', 0) or 0
                if max(s0, s1) >= 70000:
                    elite_files.append((fpath, max(s0, s1), 0 if s0 > s1 else 1))
        except Exception:
            continue
        if len(elite_files) >= max_matches:
            break

    print(f'Evaluating MasterCounterAgent against {len(elite_files)} Grandmaster replays...\n')

    wins = 0
    our_scores = []
    opp_replay_scores = []
    results = []

    for idx, (fpath, recorded_score, winning_p_idx) in enumerate(elite_files):
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        steps = data.get('steps', [])
        # Extract seed from configuration
        config = data.get('configuration', {})
        seed = config.get('seed', 42 + idx)

        # Initialize game with the same seed
        g = FastGame(seed=seed)
        our_agent = MasterCounterAgent(seed=seed)

        # Replay the opponent's exact recorded actions step-by-step
        for step_idx in range(min(720, len(steps))):
            obs0 = g.get_observation(0)
            act0 = our_agent(obs0)

            # Opponent recorded action
            opp_recorded_act = steps[step_idx][winning_p_idx].get('action', {})
            if not isinstance(opp_recorded_act, dict):
                opp_recorded_act = {"farmer": ["PASS"], "hands": [], "market": []}

            g.step_game(act0, opp_recorded_act)

        final_our = g.farms[0].money
        final_opp = g.farms[1].money

        is_win = final_our > final_opp
        if is_win:
            wins += 1

        our_scores.append(final_our)
        opp_replay_scores.append(final_opp)

        ep_id = os.path.basename(fpath).replace('.json', '')
        results.append({
            'episode_id': ep_id,
            'our_score': round(final_our, 2),
            'opp_score': round(final_opp, 2),
            'recorded_opp_original': recorded_score,
            'win': is_win,
            'margin': round(final_our - final_opp, 2)
        })

        if (idx + 1) % 10 == 0 or (idx + 1) == len(elite_files):
            print(f'Completed {idx + 1}/{len(elite_files)} replays... Current Win Rate: {wins/(idx+1)*100:5.1f}% | Mean Margin: +${np.mean(our_scores) - np.mean(opp_replay_scores):6.0f}')

    wr = wins / len(elite_files) * 100
    mean_our = float(np.mean(our_scores))
    mean_opp = float(np.mean(opp_replay_scores))
    p5_floor = float(np.percentile(our_scores, 5))

    print('\n' + '=' * 95)
    print(f'GRANDMASTER REPLAY BENCHMARK SUMMARY (N={len(elite_files)} Real Tournament Matches)')
    print('=' * 95)
    print(f'Win Rate vs Real Replays : {wr:5.1f}% ({wins}/{len(elite_files)} Wins)')
    print(f'Our Average Score        : ${mean_our:,.2f}')
    print(f'Opponent Average Score   : ${mean_opp:,.2f}')
    print(f'Average Net Margin       : +${mean_our - mean_opp:,.2f}')
    print(f'p5 Risk Floor Protection : ${p5_floor:,.2f}')
    print('=' * 95)

    out_file = 'project_maestro/data/replay_benchmark_results.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump({'total_matches': len(elite_files), 'win_rate': wr, 'results': results}, f, indent=2)
    print(f'\nReplay benchmark output saved to {out_file}')

if __name__ == '__main__':
    evaluate_against_real_replays(50)
