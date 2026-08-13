import src.main as main

# Override parameters for Aggressive Crops Dumper profile
main.P["max_animals"] = 0
main.P["max_geese"] = 0
main.P["res_STRAWBERRY"] = 20
main.P["res_MELON"] = 40
main.P["res_TOMATO"] = 15
main.P["headroom_floor_frac"] = 1.50 # Overproduce and ignore opponent production completely
main.P["invest_frac"] = 0.99
main.P["max_hands"] = 11

def agent(obs):
    # Delegate to the modified main agent
    return main.agent(obs)
