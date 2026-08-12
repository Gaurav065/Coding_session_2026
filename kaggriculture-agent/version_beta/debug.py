import test, main
import sys

original_step = main.agent

def debug_agent(obs):
    res = original_step(obs)
    if obs['step'] % 24 == 0:
        print(f"Day {obs['step']//24} orders: {res['market']}")
    return res

main.agent = debug_agent
test.main = main

# Patch test.py print
original_print = print
def new_print(*args, **kwargs):
    if len(args) > 0 and isinstance(args[0], str) and args[0].startswith("d"):
        original_print(*args, **kwargs)
    elif len(args) > 0 and isinstance(args[0], str) and args[0].startswith("Day"):
        original_print(*args, **kwargs)

import builtins
builtins.print = new_print

test.evaluate_agents([debug_agent, debug_agent], 108, 'test')
