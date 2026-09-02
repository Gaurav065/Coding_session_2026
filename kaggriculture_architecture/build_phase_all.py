import os
import tarfile
import base64

source_dir1 = r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent"
source_dir2 = r"C:\Coding\kaggriculture_architecture\artifacts"
tar_path = r"C:\Coding\kaggriculture_architecture\submission_phase_all.tar.gz"

with tarfile.open(tar_path, "w:gz") as tar:
    for root, dirs, files in os.walk(source_dir1):
        if "__pycache__" in root: continue
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                arcname = os.path.relpath(filepath, source_dir1)
                tar.add(filepath, arcname=arcname)
    
    for root, dirs, files in os.walk(source_dir2):
        if "__pycache__" in root: continue
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                arcname = "artifacts/" + os.path.relpath(filepath, source_dir2).replace("\\", "/")
                tar.add(filepath, arcname=arcname)

with open(tar_path, "rb") as f:
    tar_bytes = f.read()

tar_b64 = base64.b64encode(tar_bytes).decode('utf-8')

single_file_code = f'''import base64
import tarfile
import io
import os
import sys
import importlib.util

_TAR_B64 = "{tar_b64}"
_TAR_BYTES = base64.b64decode(_TAR_B64)
_TMP_DIR = "/tmp/phase_all_agent_v2"

if True: # Always extract for now
    os.makedirs(_TMP_DIR, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(_TAR_BYTES), mode="r:gz") as _archive:
        _archive.extractall(_TMP_DIR)

if _TMP_DIR not in sys.path:
    sys.path.insert(0, _TMP_DIR)

_POLICY_FILE = os.path.join(_TMP_DIR, "agents", "e777a_apex_preemption.py")
_SPEC = importlib.util.spec_from_file_location("phase_all_agent", _POLICY_FILE)
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

def agent(obs, configuration=None):
    return _MODULE.agent(obs, configuration)
'''

single_py_path = r"C:\Coding\kaggriculture_architecture\submission_phase_all.py"
with open(single_py_path, "w", encoding="utf-8") as f:
    f.write(single_file_code)
print(f"Created single-file: {single_py_path} ({len(single_file_code)} bytes)")
