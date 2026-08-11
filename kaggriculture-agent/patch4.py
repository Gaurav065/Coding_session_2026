with open('version_beta/main.py', 'r') as f:
    text = f.read()

# Dynamic Weed value
text = text.replace(
'''            if kind == "WEED":
                if dl >= 2:
                    add(T(P["dig_value"], pos, ["DIG"], ("D", x, y)))
                continue''',
'''            if kind == "WEED":
                if dl >= 2:
                    usable = len(plan.get("empties", [])) + len(plan.get("weeds", []))
                    dig_val = 15.0 if usable > 15 else 180.0
                    add(T(dig_val, pos, ["DIG"], ("D", x, y)))
                continue'''
)

# Fix HARVEST
text = text.replace(
'''                        add(T(yu * price * urgency, pos, ["HARVEST"], ("H", x, y)))''',
'''                        add(T(max(yu * price * urgency, 180.0), pos, ["HARVEST"], ("H", x, y)))'''
)

# Fix FEED
text = text.replace(
'''                    v = price * (1.0 + a["interval"]) / float(a["interval"])''',
'''                    v = max(price * (1.0 + a["interval"]) / float(a["interval"]), 200.0)'''
)

# Fix CARE
text = text.replace(
'''                        add(T(price * 0.92, pos, ["CARE"], ("R", x, y)))''',
'''                        add(T(max(price * 0.92, 190.0), pos, ["CARE"], ("R", x, y)))'''
)

with open('version_beta/main.py', 'w') as f:
    f.write(text)
