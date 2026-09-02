import os
import tarfile
import base64
import io
import shutil
import hashlib
from pathlib import Path

submission_dir = r"C:\Coding\kaggriculture_architecture"
phase_f_dir = Path(r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent")
ROOT = Path(r"C:\Coding\kaggriculture_architecture")

# 1. Build in-memory POSIX tar.gz
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tar:
    # 1. Include the Phase F dynamic scripts
    tar.add(phase_f_dir / "agent_core.py", arcname="main.py")
    tar.add(phase_f_dir / "phase_f_dispatcher.py", arcname="phase_f_dispatcher.py")
    
    # 2. Include the entire legacy stack
    # We rename main.py to legacy_main.py to avoid collision with our Phase F main.py
    tar.add(ROOT / "extracted_notebook_agent" / "main.py", arcname="legacy/legacy_main.py")
    
    # Legacy original submission
    extracted_dir = r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent"
    for root, dirs, files in os.walk(extracted_dir):
        for file in sorted(files):
            if file == 'main.py': continue
            if file.endswith('.pyc') or '__pycache__' in root or file.endswith('.tar.gz'):
                continue
            full_path = os.path.join(root, file)
            rel_path = Path(os.path.relpath(full_path, extracted_dir)).as_posix()
            # We add it under legacy/ directory
            tar.add(full_path, arcname=f"legacy/{rel_path}")

tar_bytes = buf.getvalue()

# 2. Build standalone self-extracting single-file submission
b64_payload = base64.b64encode(tar_bytes).decode("ascii")
payload_hash = hashlib.sha256(b64_payload.encode("ascii")).hexdigest()[:10]

single_file_code = f'''"""Kaggriculture God Mode v4 (Phase F Dynamic Dispatcher)."""
import base64
import io
import os
import sys
import tarfile
import tempfile
import importlib.util

_B64_PAYLOAD = """{b64_payload}"""
_PAYLOAD_HASH = "{payload_hash}"

_TMP_DIR = os.path.join(tempfile.gettempdir(), f"_kagg_phase_f_{{_PAYLOAD_HASH}}")
if not os.path.exists(_TMP_DIR):
    os.makedirs(_TMP_DIR, exist_ok=True)
    _TAR_BYTES = base64.b64decode(_B64_PAYLOAD.encode("ascii"))
    with tarfile.open(fileobj=io.BytesIO(_TAR_BYTES), mode="r:gz") as _archive:
        _archive.extractall(_TMP_DIR)

if _TMP_DIR not in sys.path:
    sys.path.insert(0, _TMP_DIR)

_POLICY_FILE = os.path.join(_TMP_DIR, "main.py")
_SPEC = importlib.util.spec_from_file_location("phase_f_agent", _POLICY_FILE)
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

def agent(obs, configuration=None):
    return _MODULE.agent(obs, configuration)
'''

single_py_path = os.path.join(submission_dir, "submission_phase_f.py")
with open(single_py_path, "w", encoding="utf-8") as f:
    f.write(single_file_code)
print(f"Created single-file: {single_py_path} ({len(single_file_code)} bytes)")
