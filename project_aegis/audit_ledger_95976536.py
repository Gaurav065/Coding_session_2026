import json

with open(r'C:\Users\GauravPatel\Downloads\aegis_latest\losses\95976536.json', 'r', encoding='utf-8') as fp:
    d = json.load(fp)

steps = d['steps']

p0_inflow = 0
p0_outflow = 0
p1_inflow = 0
p1_outflow = 0

fib = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89]
p0_hire_cost = 0
p1_hire_cost = 0

for i in range(len(steps)-1):
    m0_curr = steps[i][0]['observation']['farms'][0]['money']
    m0_next = steps[i+1][0]['observation']['farms'][0]['money']
    diff0 = m0_next - m0_curr
    if diff0 > 0: p0_inflow += diff0
    else: p0_outflow += abs(diff0)

    m1_curr = steps[i][0]['observation']['farms'][1]['money']
    m1_next = steps[i+1][0]['observation']['farms'][1]['money']
    diff1 = m1_next - m1_curr
    if diff1 > 0: p1_inflow += diff1
    else: p1_outflow += abs(diff1)
    
    a0 = steps[i][0].get('action') or {}
    a1 = steps[i][1].get('action') or {}
    for m in a0.get('market', []) or []:
        if isinstance(m, list) and len(m) > 0 and m[0] == 'HIRE':
            h = steps[i][0]['observation']['farms'][0]['hires_today']
            p0_hire_cost += fib[min(h, len(fib)-1)]
    for m in a1.get('market', []) or []:
        if isinstance(m, list) and len(m) > 0 and m[0] == 'HIRE':
            h = steps[i][1]['observation']['farms'][1]['hires_today']
            p1_hire_cost += fib[min(h, len(fib)-1)]

print("=== CASH FLOW & LEDGER AUDIT (Match 95976536) ===")
print(f"P0 (Shadow Recon): Inflow=+${p0_inflow:,.0f}, Outflow=-${p0_outflow:,.0f}, Hires Cost=${p0_hire_cost:,.0f}, Final=${steps[-1][0]['observation']['farms'][0]['money']:,.0f}")
print(f"P1 (Yuyajk):      Inflow=+${p1_inflow:,.0f}, Outflow=-${p1_outflow:,.0f}, Hires Cost=${p1_hire_cost:,.0f}, Final=${steps[-1][0]['observation']['farms'][1]['money']:,.0f}")

p0_shed = steps[-1][0]['observation']['private']['shed']
print(f"\nP0 Final Shed: {p0_shed}")
