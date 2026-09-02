"""Frozen E776 latent-pasture submission entry point."""
from __future__ import annotations

from e776_pkg.entry import policy as _policy


# Kaggle's raw loader selects the final callable in insertion order.
def kaggriculture_e776_agent(obs, configuration=None):
    return _policy(obs, configuration)
