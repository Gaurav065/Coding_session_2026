import sys, json, time, os, numpy as np
sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent

PORTFOLIO_ARMS = [
    ('9C_4S_Balanced', {'cow_cap_base': 9, 'sheep_cap': 4, 'strawberry_target': 18, 'melon_seed_target': 6, 'crew_mid': 10}),
    ('4C_10S_YarnBurst', {'cow_cap_base': 4, 'sheep_cap': 10, 'strawberry_target': 16, 'melon_seed_target': 4, 'crew_mid': 10}),
    ('6C_8S_WoolHybrid', {'cow_cap_base': 6, 'sheep_cap': 8, 'strawberry_target': 18, 'melon_seed_target': 4, 'crew_mid': 10}),
    ('11C_3S_DairyPower', {'cow_cap_base': 11, 'sheep_cap': 3, 'strawberry_target': 18, 'melon_seed_target': 6, 'crew_mid': 10}),
    ('6C_4S_SmoothieRush', {'cow_cap_base': 6, 'sheep_cap': 4, 'strawberry_target': 22, 'melon_seed_target': 4, 'crew_mid': 10}),
    ('8C_6S_MetaCalibrated', {'cow_cap_base': 8, 'sheep_cap': 6, 'strawberry_target': 18, 'melon_seed_target': 6, 'crew_mid': 10}),
    ('14S_0C_AhmadSpecialist', {'cow_cap_base': 0, 'sheep_cap': 14, 'strawberry_target': 14, 'melon_seed_target': 0, 'crew_mid': 10}),
    ('12C_0C_PureDairy', {'cow_cap_base': 12, 'sheep_cap': 0, 'strawberry_target': 18, 'melon_seed_target': 6, 'crew_mid': 10})
]

TEST_SEEDS = list(range(20000, 20050))

print(f'Running Combinatorial Profit Surface Search across {len(PORTFOLIO_ARMS)} strategic arms on N={len(TEST_SEEDS)} seeds...')
results = {}

for arm_name, params in PORTFOLIO_ARMS:
    scores = []
    for s in TEST_SEEDS:
        g = FastGame(seed=s)
        a0 = MaestroFullPortfolioAgent(params=params, seed=s)
        a1 = make_meta_calibrated_opponent(seed=s)
        while not g.done:
            g.step_game(a0(g.get_observation(0)), a1(g.get_observation(1)))
        scores.append(g.farms[0].money)

    mean_s = float(np.mean(scores))
    med_s = float(np.median(scores))
    p5_s = float(np.percentile(scores, 5))
    min_s = float(np.min(scores))
    max_s = float(np.max(scores))

    results[arm_name] = {
        'params': params,
        'mean_profit': round(mean_s, 2),
        'median_profit': round(med_s, 2),
        'p5_floor': round(p5_s, 2),
        'min_profit': round(min_s, 2),
        'max_profit': round(max_s, 2)
    }
    print(f'  {arm_name:<25} | Mean:  | Median:  | p5:  | Min:  | Max: ')

# Find global bests
best_mean_arm = max(results.items(), key=lambda kv: kv[1]['mean_profit'])
best_floor_arm = max(results.items(), key=lambda kv: kv[1]['p5_floor'])

output_payload = {
    'metadata': {
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'num_seeds': len(TEST_SEEDS),
        'opponent': 'MetaCalibratedOpponent(8C/6S)',
        'best_mean_pathway': best_mean_arm[0],
        'best_p5_floor_pathway': best_floor_arm[0]
    },
    'pathways': results
}

out_path = 'project_maestro/data/realistic_profit_surface.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(output_payload, f, indent=2)
print(f'SUCCESS: Realistic profit surface saved to {out_path}')