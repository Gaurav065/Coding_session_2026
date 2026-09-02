import os
import tarfile
import base64
import io
import shutil
import hashlib
from pathlib import Path

extracted_dir = r'C:\Coding\kaggriculture_architecture\extracted_notebook_agent'
submission_dir = r'C:\Coding\kaggriculture_architecture\submission'
os.makedirs(submission_dir, exist_ok=True)

# 1. Build in-memory POSIX tar.gz (strict forward slashes)
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode='w:gz') as tar:
    for root, dirs, files in os.walk(extracted_dir):
        for file in sorted(files):
            if file.endswith('.pyc') or '__pycache__' in root or file.endswith('.tar.gz'):
                continue
            full_path = os.path.join(root, file)
            rel_path = Path(os.path.relpath(full_path, extracted_dir)).as_posix()
            tar.add(full_path, arcname=rel_path)
            print(f"Added to POSIX archive: {rel_path}")

tar_bytes = buf.getvalue()
tar_path = os.path.join(submission_dir, 'submission.tar.gz')
with open(tar_path, 'wb') as f:
    f.write(tar_bytes)
print(f"\nCreated POSIX tar archive: {tar_path} ({len(tar_bytes)} bytes)")

# Also copy to root
shutil.copyfile(tar_path, r'C:\Coding\kaggriculture_architecture\submission.tar.gz')

# 2. Build standalone self-extracting single-file submission.py (hash-versioned tmp dir)
b64_payload = base64.b64encode(tar_bytes).decode('ascii')
payload_hash = hashlib.sha256(b64_payload.encode('ascii')).hexdigest()[:10]

single_file_code = f'''"""Kaggriculture God Mode v3 (Apex Strategy) - Standalone Submission."""
import base64
import io
import os
import sys
import tarfile
import tempfile
import importlib.util

_B64_PAYLOAD = """{b64_payload}"""
_PAYLOAD_HASH = "{payload_hash}"

_TMP_DIR = os.path.join(tempfile.gettempdir(), f"_kagg_apex_{{_PAYLOAD_HASH}}")
if not os.path.exists(_TMP_DIR):
    os.makedirs(_TMP_DIR, exist_ok=True)
    _TAR_BYTES = base64.b64decode(_B64_PAYLOAD.encode("ascii"))
    with tarfile.open(fileobj=io.BytesIO(_TAR_BYTES), mode="r:gz") as _archive:
        _archive.extractall(_TMP_DIR)

if _TMP_DIR not in sys.path:
    sys.path.insert(0, _TMP_DIR)
_AGENTS_DIR = os.path.join(_TMP_DIR, "agents")
if _AGENTS_DIR not in sys.path:
    sys.path.insert(0, _AGENTS_DIR)

_POLICY_FILE = os.path.join(_AGENTS_DIR, "e777a_apex_preemption.py")
_SPEC = importlib.util.spec_from_file_location("kagg_apex_policy", _POLICY_FILE)
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

def agent(obs, configuration=None):
    return _MODULE.agent(obs, configuration)
'''

single_py_path = os.path.join(submission_dir, 'submission.py')
with open(single_py_path, 'w', encoding='utf-8') as f:
    f.write(single_file_code)
print(f"Created single-file: {single_py_path} ({len(single_file_code)} bytes)")

# Also copy to root and submission/main.py
shutil.copyfile(single_py_path, r'C:\Coding\kaggriculture_architecture\submission.py')
shutil.copyfile(single_py_path, r'C:\Coding\kaggriculture_architecture\submission\main.py')
print("All submission artifacts regenerated and ready for Kaggle!")
