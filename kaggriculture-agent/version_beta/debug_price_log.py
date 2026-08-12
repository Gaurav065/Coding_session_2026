import test, main
original_step = main.agent

def debug_agent(obs):
    st = main.S(obs)
    res = original_step(obs)
    if st.day >= 25 and st.hour == 23:
        with open('debug_prices.log', 'a') as f:
            f.write(f'Day {st.day} MILK: {st.prices["MILK"]} (minv: {st.minv["MILK"]}) STRAWBERRY: {st.prices["STRAWBERRY"]} (minv: {st.minv["STRAWBERRY"]}) money: {st.money}\n')
    return res

main.agent = debug_agent
test.main = main
test.evaluate_agents([debug_agent, debug_agent], 108, 'test')
