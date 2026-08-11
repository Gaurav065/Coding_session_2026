with open('version_beta/main.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if 'effective_work_per_hand' in line and not skip:
        continue # clear out my bad patches
    if 'have = dict((k, counts[k] + st.shed.get(k, 0)) for k in ANIMALS)' in line:
        # Re-insert the proper block
        new_lines.append('    have = dict((k, counts[k] + st.shed.get(k, 0)) for k in ANIMALS)\n')
        new_lines.append('    owned = have["GOOSE"] + have["COW"] + have["SHEEP"]\n\n')
        new_lines.append('    wheat_price_buy = market_price("WHEAT", st.minv["WHEAT"] - 1)\n')
        new_lines.append('    feed_reserve = min(2600.0, owned * P["feed_reserve_days"] * wheat_price_buy)\n')
        new_lines.append('    plan["feed_reserve"] = feed_reserve\n')
        new_lines.append('    budget = max(0.0, st.money - feed_reserve) * P["invest_frac"]\n\n')
        new_lines.append('    nq = len(st.unlocked) - 1\n')
        new_lines.append('    effective_work_per_hand = P["work_per_hand"] - (nq * 1.5)\n')
        new_lines.append('    if effective_work_per_hand < 7.0: effective_work_per_hand = 7.0\n')
        skip = True
    elif skip and ('wheat_price_buy = ' in line or 'feed_reserve = ' in line or 'budget = ' in line or 'nq = len' in line or 'effective_work_per_hand = ' in line):
        continue
    elif 'P["work_per_hand"]' in line and 'effective_work_per_hand' not in line:
        if 'def build_plan' in "".join(new_lines[-50:]):  # Only replace inside build_plan
            new_lines.append(line.replace('P["work_per_hand"]', 'effective_work_per_hand'))
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)
        if skip and line.strip() == '':
            skip = False

with open('version_beta/main.py', 'w') as f:
    f.writelines(new_lines)
