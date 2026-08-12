import test, main
import sys

original_step = main.agent

def debug_agent(obs):
    res = original_step(obs)
    st = main.S(obs)
    m = main._mem(st.pid)
    plan = m.get("plan", {})
    if st.day == 13 and (obs['step'] % 24) in (0, 1, 2, 22):
        with open("debug_alloc.log", "a") as f:
            f.write(f"Hour {obs['step'] % 24} want: {plan.get('want')} build: {plan.get('build_pastures')} st.seeds: {st.seeds} money: {st.money}\n")
    return res

main.agent = debug_agent
test.main = main

import builtins
test.evaluate_agents([debug_agent, debug_agent], 108, 'test')
