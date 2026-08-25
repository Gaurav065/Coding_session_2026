"""Meta-Calibrated Tournament Opponent — Project Maestro (MAIN_PLAN.md Phase B1)

Calibrated to the empirical Phase 0 tournament winner targets (n=693 winners):
- Livestock: 8.3 Cows (Median 8.0), 6.3 Sheep (Median 4.0), 0.3 Geese (91.6% zero)
- Land Unlocks: NE Day ~5.8, SW Day ~10.4, SE ~17.7%
- Labor: ~9.5 hands/day (hires at Day 0: 4-5, scaling to 9-10 mid/late)
- Target Volumes Sold:
    * Wheat: ~227.6 units
    * Strawberry: ~55.5 units
    * Milk: ~50.5 units
    * Wool: ~36.7 units
    * Melon: ~29.6 units
    * Fertilizer: ~200.3 units (Median 123.0)
"""

from typing import Dict, List, Tuple, Optional, Any
from project_maestro.agent.dispatcher_agent import (
    MaestroFullPortfolioAgent,
    BASE_PRICES,
    ABOVE_TARGET,
    GLUT_RESISTANT,
    GLUT_PRONE,
    get_step_towards,
    dist,
    SHED_ACCESS_TILES,
    COW_PASTURES,
    SHEEP_PASTURES,
    GOOSE_COOPS,
    NW_WHEAT,
    NE_STRAWBERRY,
    NE_WHEAT,
    SW_MELON,
    SW_WHEAT
)

# Meta-calibrated pasture layout accommodating 8 Cows + 6 Sheep (14 total pastures)
META_COW_PASTURES = [
    (4, 3), (3, 4),
    (4, 2), (3, 3), (2, 4),
    (4, 1), (3, 2), (2, 3)
]  # 8 Cow Pastures

META_SHEEP_PASTURES = [
    (1, 4), (4, 0),
    (3, 1), (2, 2), (1, 3), (0, 4)
]  # 6 Sheep Pastures

META_DEFAULT_PARAMS = {
    "cow_cap_base": 8,           # Meta Winner Mean: 8.3 (Median 8.0)
    "sheep_cap": 6,              # Meta Winner Mean: 6.3 (Median 4.0)
    "goose_cap": 0,              # Meta Winner Mean: 0.3 (91.6% zero)
    "strawberry_target": 18,     # Meta Winner Strawberry Volume: 55.5 units
    "melon_seed_target": 6,      # Meta Winner Melon Volume: 29.6 units
    "crew_mid": 9,               # Meta Winner Labor: ~9.5 hands/day
    "crew_late": 10,
    "cow_gate_day_early": 99,    # Unsteered / Standard Meta behavior
    "cow_gate_day_mid": 99,
}


class MetaCalibratedOpponent(MaestroFullPortfolioAgent):
    """Opponent agent calibrated strictly to tournament winner empirical observables."""
    def __init__(self, params=None, kw_early: Optional[int] = 10, seed: Optional[int] = None):
        merged_params = {**META_DEFAULT_PARAMS, **(params or {})}
        super().__init__(params=merged_params, kw_early=kw_early, seed=seed)
        self.cow_pastures = list(META_COW_PASTURES)
        self.sheep_pastures = list(META_SHEEP_PASTURES)
        self.goose_coops = list(GOOSE_COOPS)

    def __call__(self, obs: Dict[str, Any]) -> Dict[str, Any]:
        # Emits actions adhering to the 8 Cow / 6 Sheep / 18 Strawberry / 6 Melon meta portfolio
        return super().__call__(obs)


def make_meta_calibrated_opponent(params=None, seed: Optional[int] = None, kw_early: Optional[int] = 10):
    agent_instance = MetaCalibratedOpponent(params=params, seed=seed, kw_early=kw_early)
    return lambda obs: agent_instance(obs)
