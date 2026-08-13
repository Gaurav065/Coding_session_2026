import src.main as main

# Override parameters for Balanced Cow/Sheep Player profile
main.P["max_animals"] = 16
main.P["max_geese"] = 0
main.P["res_MILK"] = 80
main.P["res_WOOL"] = 90
main.P["res_STRAWBERRY"] = 90
main.P["res_MELON"] = 180
main.P["headroom_floor_frac"] = 0.50
main.P["invest_frac"] = 0.95
main.P["max_hands"] = 11

def agent(obs):
    # Delegate to the modified main agent
    return main.agent(obs)
