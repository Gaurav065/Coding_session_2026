import sys, json, time, os, numpy as np
sys.path.insert(0, r'C:/Coding')
from project_maestro.engine.fast_engine import FastGame
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent
from project_maestro.agent.meta_calibrated_opponent import make_meta_calibrated_opponent

PORTFOLIO_ARMS = {
    '9C_4S_Balanced': {'cow_cap_base': 9, 'sheep_cap': 4, 'strawberry_target': 18, 'melon_seed_target': 6, 'crew_mid': 10},
    '4C_10S_YarnBurst': {'cow_cap_base': 4, 'sheep_cap': 10, 'strawberry_target': 16, 'melon_seed_target': 4, 'crew_mid': 10},
    '6C_8S_WoolHybrid': {'cow_cap_base': 6, 'sheep_cap': 8, 'strawberry_target': 18, 'melon_seed_target': 4, 'crew_mid': 10},
    '11C_3S_DairyPower': {'cow_cap_base': 11, 'sheep_cap': 3, 'strawberry_target': 18, 'melon_seed_target': 6, 'crew_mid': 10},
    '6C_4S_SmoothieRush': {'cow_cap_base': 6, 'sheep_cap': 4, 'strawberry_target': 22, 'melon_seed_target': 4, 'crew_mid': 10},
    '8C_6S_MetaCalibrated': {'cow_cap_base': 8, 'sheep_cap': 6, 'strawberry_target': 18, 'melon_seed_target': 6, 'crew_mid': 10},
    '14S_0C_AhmadSpecialist': {'cow_cap_base': 0, 'sheep_cap': 14, 'strawberry_target': 14, 'melon_seed_target': 0, 'crew_mid': 10}
}

TEST_SEEDS = list(range(20000, 20100))
match_records = []

print(f'Gathering conditional shop-draw records across N={len(TEST_SEEDS)} seeds...')
for s in TEST_SEEDS:
    g = FastGame(seed=s)
    shops = list(g.unlocked_shops)
    # Record scores for each arm on this exact seed
    seed_arm_scores = {}
    for arm_name, params in PORTFOLIO_ARMS.items():
        gm = FastGame(seed=s)
        a0 = MaestroFullPortfolioAgent(params=params, seed=s)
        a1 = make_meta_calibrated_opponent(seed=s)
        while not gm.done:
            gm.step_game(a0(gm.get_observation(0)), a1(gm.get_observation(1)))
        seed_arm_scores[arm_name] = gm.farms[0].money
    match_records.append({'seed': s, 'shops': gm.unlocked_shops, 'scores': seed_arm_scores})

# Conditional Slice Analysis
def analyze_slice(name, filter_fn):
    filtered = [m for m in match_records if filter_fn(m['shops'])]
    print(f'\n=== CONDITIONAL SCENARIO: {name} (N={len(filtered)} seeds) ===')
    if not filtered: return {}
    arm_means = {}
    for arm_name in PORTFOLIO_ARMS:
        sc = [m['scores'][arm_name] for m in filtered]
        mean_val = float(np.mean(sc))
        p5_val = float(np.percentile(sc, 5))
        arm_means[arm_name] = {'mean': round(mean_val, 2), 'p5': round(p5_val, 2)}
        print(f'  {arm_name:<25} | Mean:  | p5: ')
    best_arm = max(arm_means.items(), key=lambda kv: kv[1]['mean'])
    print(f'  >>> OPTIMAL POLICY: {best_arm[0]} (Mean: )')
    return {'best_policy': best_arm[0], 'best_mean': best_arm[1]['mean'], 'portfolio_breakdown': arm_means}

cond_surface = {
    'yarn_store_present': analyze_slice('YARN STORE ACTIVE (>= 1 Yarn Store)', lambda s: 'YARN_STORE' in s),
    'zero_yarn_store': analyze_slice('ZERO YARN STORE (Worst-Case Wool)', lambda s: 'YARN_STORE' not in s),
    'smoothie_or_brunch_active': analyze_slice('SMOOTHIE OR BRUNCH ACTIVE (High Berry/Milk Demand)', lambda s: 'SMOOTHIE_SHOP' in s or 'BRUNCH_SPOT' in s),
    'pizza_or_bakery_active': analyze_slice('PIZZA OR BAKERY ACTIVE (High Wheat/Tomato Demand)', lambda s: 'PIZZA_SHOP' in s or 'BAKERY' in s),
    'unconditional_global': analyze_slice('UNCONDITIONAL ALL SEEDS', lambda s: True)
}

out_path = 'project_maestro/data/conditional_shop_surface.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(cond_surface, f, indent=2)
print(f'SUCCESS: Saved conditional shop surface to {out_path}')