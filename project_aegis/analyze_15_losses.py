import json
import os
from collections import defaultdict

base_downloads = r'C:\Users\GauravPatel\Downloads\aegis_latest\wins'
files = [
    '95994870.json', '96001740.json', '96004023.json', '96008620.json',
    '96013184.json', '96020030.json', '96024609.json', '96029185.json',
    '96036058.json', '96038361.json', '96072351.json', '96186476.json',
    '96234378.json', '96378247.json', '96540014.json'
]

print("=" * 80)
print(f"DEEP MACRO FORENSIC AUDIT OF 15 LOSS MATCHES")
print("=" * 80)

opp_melon_totals = []
opp_straw_totals = []
opp_wheat_totals = []
opp_milk_totals = []
opp_wool_totals = []
opp_carrot_totals = []
opp_tomato_totals = []
opp_fert_totals = []

shadow_melon_totals = []
shadow_straw_totals = []
shadow_wheat_totals = []
shadow_milk_totals = []
shadow_wool_totals = []
shadow_carrot_totals = []
shadow_tomato_totals = []
shadow_fert_totals = []

for f in sorted(files):
    p = os.path.join(base_downloads, f)
    with open(p, 'r', encoding='utf-8') as fp:
        data = json.load(fp)

    info = data.get('info', {})
    teams = info.get('TeamNames', ['P0', 'P1'])
    steps = data['steps']
    p0_final = steps[-1][0]['reward']
    p1_final = steps[-1][1]['reward']
    shops = steps[-1][0]['observation']['town']['unlocked_shops']

    my_seat = 1 if teams[1] == 'Shadow Recon' else 0
    opp_seat = 1 - my_seat
    my_score = p1_final if my_seat == 1 else p0_final
    opp_score = p0_final if my_seat == 1 else p1_final
    opp_name = teams[opp_seat]

    my_sells = defaultdict(int)
    opp_sells = defaultdict(int)
    my_rev = defaultdict(float)
    opp_rev = defaultdict(float)

    for step_idx, step in enumerate(steps):
        obs0 = step[0]['observation']
        prices = obs0['market']['prices']
        act_my = step[my_seat].get('action') or {}
        act_opp = step[opp_seat].get('action') or {}

        for m in act_my.get('market', []) or []:
            if isinstance(m, list) and len(m) >= 3 and m[0] == 'SELL':
                item = m[1]
                qty = int(m[2]) if str(m[2]).isdigit() else 1
                my_sells[item] += qty
                my_rev[item] += qty * prices.get(item, 1)

        for m in act_opp.get('market', []) or []:
            if isinstance(m, list) and len(m) >= 3 and m[0] == 'SELL':
                item = m[1]
                qty = int(m[2]) if str(m[2]).isdigit() else 1
                opp_sells[item] += qty
                opp_rev[item] += qty * prices.get(item, 1)

    print(f"\n[{f}] Shadow ({my_score:,.0f}) vs {opp_name} ({opp_score:,.0f}) | Margin: {my_score - opp_score:+,.0f}")
    print(f"  Shops: {shops}")
    print(f"  Opp Sells:    MELON={opp_sells['MELON']:3d} (${opp_rev['MELON']:6.0f}), STRAW={opp_sells['STRAWBERRY']:3d} (${opp_rev['STRAWBERRY']:6.0f}), WHEAT={opp_sells['WHEAT']:4d} (${opp_rev['WHEAT']:6.0f}), MILK={opp_sells['MILK']:3d} (${opp_rev['MILK']:6.0f}), WOOL={opp_sells['WOOL']:3d} (${opp_rev['WOOL']:6.0f}), CARROT={opp_sells['CARROT']:3d}, TOMATO={opp_sells['TOMATO']:3d}")
    print(f"  Shadow Sells: MELON={my_sells['MELON']:3d} (${my_rev['MELON']:6.0f}), STRAW={my_sells['STRAWBERRY']:3d} (${my_rev['STRAWBERRY']:6.0f}), WHEAT={my_sells['WHEAT']:4d} (${my_rev['WHEAT']:6.0f}), MILK={my_sells['MILK']:3d} (${my_rev['MILK']:6.0f}), WOOL={my_sells['WOOL']:3d} (${my_rev['WOOL']:6.0f}), CARROT={my_sells['CARROT']:3d}, TOMATO={my_sells['TOMATO']:3d}")

    opp_melon_totals.append(opp_sells['MELON'])
    shadow_melon_totals.append(my_sells['MELON'])
    opp_straw_totals.append(opp_sells['STRAWBERRY'])
    shadow_straw_totals.append(my_sells['STRAWBERRY'])
    opp_wheat_totals.append(opp_sells['WHEAT'])
    shadow_wheat_totals.append(my_sells['WHEAT'])
    opp_milk_totals.append(opp_sells['MILK'])
    shadow_milk_totals.append(my_sells['MILK'])
    opp_wool_totals.append(opp_sells['WOOL'])
    shadow_wool_totals.append(my_sells['WOOL'])

print("\n" + "=" * 80)
print("AGGREGATE COMMODITY COMPARISON ACROSS ALL 15 LOSSES:")
print(f"Average Opponent Melons Sold: {sum(opp_melon_totals)/len(opp_melon_totals):.1f}  vs  Shadow: {sum(shadow_melon_totals)/len(shadow_melon_totals):.1f}")
print(f"Average Opponent Strawberries:{sum(opp_straw_totals)/len(opp_straw_totals):.1f}  vs  Shadow: {sum(shadow_straw_totals)/len(shadow_straw_totals):.1f}")
print(f"Average Opponent Wheat Sold:  {sum(opp_wheat_totals)/len(opp_wheat_totals):.1f} vs  Shadow: {sum(shadow_wheat_totals)/len(shadow_wheat_totals):.1f}")
print(f"Average Opponent Milk Sold:   {sum(opp_milk_totals)/len(opp_milk_totals):.1f}  vs  Shadow: {sum(shadow_milk_totals)/len(shadow_milk_totals):.1f}")
print(f"Average Opponent Wool Sold:   {sum(opp_wool_totals)/len(opp_wool_totals):.1f}  vs  Shadow: {sum(shadow_wool_totals)/len(shadow_wool_totals):.1f}")
print("=" * 80)
