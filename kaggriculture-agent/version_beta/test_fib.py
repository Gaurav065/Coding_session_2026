import math

def smooth_fib_cost(n):
    if n <= 0: return 0.0
    n_int = int(math.floor(n))
    frac = n - n_int
    
    s, a, b = 0.0, 1.0, 1.0
    for _ in range(n_int):
        s += a
        a, b = b, a + b
        
    # a is now the cost of the (n_int + 1)th hand
    s += a * frac
    return s

for n in [10.0, 10.2, 10.8, 11.0, 11.5]:
    print(f'n={n}, cost={smooth_fib_cost(n)}')
