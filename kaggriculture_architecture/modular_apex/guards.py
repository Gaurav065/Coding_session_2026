import os
from pathlib import Path
import sys

try:
    from . import chassis
except ImportError:
    import chassis

_ROOT = Path(globals().get("__file__") or os.getcwd()).resolve()
if _ROOT.is_file():
    _ROOT = _ROOT.parent

_CANDIDATES = [
    _ROOT / '_guards_source.py',
    Path('.') / '_guards_source.py',
    Path('/kaggle_simulations/agent/_guards_source.py'),
]
_SOURCE_FILE = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[0])
_BYTECODE = compile(_SOURCE_FILE.read_text(encoding='utf-8'), str(_SOURCE_FILE), 'exec')

def wrap_apex_guards(_IMPL):
    scope = dict(chassis.__dict__)
    scope['_IMPL'] = _IMPL
    exec(_BYTECODE, scope)
    return scope['agent']
