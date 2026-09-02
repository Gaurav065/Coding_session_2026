import os
import tarfile
import shutil

extracted_dir = r'C:\Coding\kaggriculture_architecture\extracted_notebook_agent'
submission_dir = r'C:\Coding\kaggriculture_architecture\submission'
os.makedirs(submission_dir, exist_ok=True)

# 1. Create collision-safe and __file__-safe main.py in extracted_dir
main_code = '''"""Collision-safe and __file__-safe loader for frozen E777."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

if "__file__" in globals() and __file__:
    _ROOT = Path(__file__).resolve().parent
else:
    _ROOT = Path(os.getcwd()).resolve()

if not (_ROOT / "agents").exists():
    for p in sys.path:
        if (Path(p) / "agents" / "e777a_apex_preemption.py").exists():
            _ROOT = Path(p)
            break

_AGENTS = _ROOT / "agents"
if str(_AGENTS) not in sys.path:
    sys.path.insert(0, str(_AGENTS))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_POLICY = _AGENTS / "e777a_apex_preemption.py"
_SPEC = importlib.util.spec_from_file_location("e777_packaged_policy", str(_POLICY))
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("cannot load packaged E777 policy")
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

def agent(obs, configuration=None):
    return _MODULE.agent(obs, configuration)
'''

with open(os.path.join(extracted_dir, 'main.py'), 'w', encoding='utf-8') as f:
    f.write(main_code)

# 2. Package all files into submission.tar.gz
tar_path = os.path.join(submission_dir, 'submission.tar.gz')
with tarfile.open(tar_path, 'w:gz') as tar:
    for root, dirs, files in os.walk(extracted_dir):
        for file in files:
            if file.endswith('.pyc') or '__pycache__' in root or file.endswith('.tar.gz'):
                continue
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, extracted_dir)
            tar.add(full_path, arcname=rel_path)
            print(f"Added to tar: {rel_path}")

print(f"\nCreated: {tar_path} (Size: {os.path.getsize(tar_path)} bytes)")
