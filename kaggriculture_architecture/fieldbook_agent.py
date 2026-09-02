import sys
import copy
import fieldbook_routes

ROUTE_CACHE = {}

def get_best_route_id(current_sig):
    if current_sig in ROUTE_CACHE:
        return ROUTE_CACHE[current_sig]
        
    best_match = None
    for sig, route_id in fieldbook_routes.ROUTE_MAP.items():
        match = True
        for i in range(5):
            if current_sig[i] is not None and current_sig[i] != sig[i]:
                match = False
                break
        if match:
            best_match = route_id
            break
            
    if best_match is None:
        best_match = 0
        
    ROUTE_CACHE[current_sig] = best_match
    return best_match

class FieldbookAgent:
    def __init__(self):
        self.default_shops = None
        self.shop_sig = [None, None, None, None, None]
        
    def __call__(self, obs, conf=None):
        step = obs.get("step", 0)
        player_idx = obs.get("player", 0)
        if "player" not in obs: player_idx = 0
        self.shop_sig[0] = player_idx
        
        if self.default_shops is None:
            self.default_shops = set(obs.get("town", {}).get("unlocked_shops", []))
            
        current_shops = set(obs.get("town", {}).get("unlocked_shops", []))
        new_shops = list(current_shops - self.default_shops)
        
        if step >= 72 and new_shops: self.shop_sig[1] = list(set(new_shops))[0]
        if step >= 144:
            n = list(set(new_shops) - {self.shop_sig[1]})
            if n: self.shop_sig[2] = n[0]
        if step >= 216:
            n = list(set(new_shops) - {self.shop_sig[1], self.shop_sig[2]})
            if n: self.shop_sig[3] = n[0]
        if step >= 288:
            n = list(set(new_shops) - {self.shop_sig[1], self.shop_sig[2], self.shop_sig[3]})
            if n: self.shop_sig[4] = n[0]
            
        route_id = get_best_route_id(tuple(self.shop_sig))
        
        # VERY IMPORTANT: If step >= 720, return PASS to avoid IndexError
        if step >= 720:
            return {"farmer": ["PASS"], "hands": [], "market": []}
            
        action = copy.deepcopy(fieldbook_routes.ROUTES[route_id][step])
        
        own_hands = len(obs.get("farms", [{}, {}])[player_idx].get("hands", []))
        hands = list(action.get("hands", []))
        
        if len(hands) > own_hands: hands = hands[:own_hands]
        elif len(hands) < own_hands: hands.extend([["PASS"]] * (own_hands - len(hands)))
            
        action["hands"] = hands
        return action

agent_instance = FieldbookAgent()
def agent(obs, conf=None):
    if obs.get("step", 0) == 0:
        agent_instance.default_shops = None
        agent_instance.shop_sig = [None, None, None, None, None]
    return agent_instance(obs, conf)
