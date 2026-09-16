# SPDX-License-Identifier: Apache-2.0
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from .config import CHASSIS_SETTINGS, CLEAN_OPENING
    from .payload import load_routes
    from .router import router
    from .chassis import make_agent
    from .guards import wrap_apex_guards
except ImportError:
    from config import CHASSIS_SETTINGS, CLEAN_OPENING
    from payload import load_routes
    from router import router
    from chassis import make_agent
    from guards import wrap_apex_guards

# 1. Load routes
_ROUTES = load_routes()

# 2. Apply Clean Opening to all routes (eliminates Seat 1 bid-ask spread churn)
for _tape in _ROUTES.values():
    _tape[0] = dict(_tape[0], market=[list(o) for o in CLEAN_OPENING])

# 3. Instantiate base replay agent with scenario router
_BASE_AGENT = make_agent(_ROUTES, router=router, **CHASSIS_SETTINGS)

# 4. Wrap with full verified defensive guards
agent = wrap_apex_guards(_BASE_AGENT)
