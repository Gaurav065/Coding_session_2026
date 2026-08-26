"""Master Adaptive Counter-Agent for Project Maestro

Combines:
1. Concentric Radial Pasture & Crop Spatial Packing (Min-Distance Ring 1 & 2).
2. Real-time Opponent Footprint Sensing (Classifying opponent build by Day 4).
3. Dynamic Market-Niche Portfolio Adaptation (Exploiting opponent market blindspots).
"""

from typing import Dict, List, Any, Optional
from project_maestro.agent.dispatcher_agent import MaestroFullPortfolioAgent
from project_maestro.agent.counter_strategy import OpponentPerceptionEngine
from project_maestro.agent.meta_calibrated_opponent import META_COW_PASTURES, META_SHEEP_PASTURES

class MasterCounterAgent(MaestroFullPortfolioAgent):
    def __init__(self, params=None, kw_early: Optional[int] = None, seed: Optional[int] = None):
        super().__init__(params=params, kw_early=kw_early, seed=seed)
        self.perception = OpponentPerceptionEngine()
        # Adopt concentric min-distance pasture layouts
        self.cow_pastures = list(META_COW_PASTURES) + [(3, 1), (2, 2)]
        self.sheep_pastures = list(META_SHEEP_PASTURES)

    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        player = obs["player"]
        day = obs.get("day", 0)

        # 1. Update Opponent Sensing
        self.perception.update(obs, player)

        # 2. Dynamic Niche Adaptation
        if day >= 4:
            adapted_params = self.perception.compute_counter_portfolio(obs, self.params)
            for k, v in adapted_params.items():
                self.params[k] = v

        # 3. Execute Core Full Portfolio Dispatch
        action_dict = super().__call__(obs)

        return action_dict
