import src.main as main

# Override parameters for Conservative Stable-Goods Player profile
main.P["max_animals"] = 12
main.P["max_geese"] = 8 # Goose is okay for eggs
main.P["res_WHEAT"] = 20
main.P["res_EGG"] = 35
main.P["res_STRAWBERRY"] = 110
main.P["res_MELON"] = 220
main.P["res_MILK"] = 140
main.P["res_WOOL"] = 170
main.P["headroom_floor_frac"] = 0.30
main.P["invest_frac"] = 0.90
main.P["max_hands"] = 10

def agent(obs):
    # Delegate to the modified main agent
    return main.agent(obs)
