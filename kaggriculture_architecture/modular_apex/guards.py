# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys

try:
    from . import chassis
except ImportError:
    import chassis

_SOURCE_FILE = Path(__file__).resolve().parent / '_guards_source.py'
_BYTECODE = compile(_SOURCE_FILE.read_text(encoding='utf-8'), str(_SOURCE_FILE), 'exec')

def wrap_apex_guards(_IMPL):
    scope = dict(chassis.__dict__)
    scope['_IMPL'] = _IMPL
    exec(_BYTECODE, scope)
    return scope['agent']
