        empty_pastures = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "PASTURE" and t.get("animal") is None)
        empty_coops = sum(1 for row in state.tiles for t in row if isinstance(t, dict) and t.get("kind") == "COOP" and t.get("animal") is None)
        
        buy_cows = min(cows_need, empty_pastures)
        empty_pastures -= buy_cows
        buy_sheep = min(sheep_need, empty_pastures)
        buy_geese = min(geese_need, empty_coops)
        
        min_animal_budget = buy_cows * 400 + buy_sheep * 300 + buy_geese * 300
        
        animal_budget = min_animal_budget