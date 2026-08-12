import sys
with open('main.py') as f:
    code = f.read()

old = '''    plan["buy_land"] = False
    if st.day >= 3 and dl >= 5:
        if current_hands >= 14 and current_hands >= P["max_hands"] - 2:
            plan["buy_land"] = True
        elif len(empties) < 12 and money > 3500:
            plan["buy_land"] = True'''

new = '''    plan["buy_land"] = False
    nq = len(st.unlocked) - 1
    if st.day >= 3 and dl >= 5:
        if len(empties) < 12 and money > 3500:
            plan["buy_land"] = True
        elif nq < 3 and money > (1000, 2000, 4000)[nq] + plan.get("feed_reserve", 0) + 1000:
            plan["buy_land"] = True'''

code = code.replace(old, new)

with open('main.py', 'w') as f:
    f.write(code)
