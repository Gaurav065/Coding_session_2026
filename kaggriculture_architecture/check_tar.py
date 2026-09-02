import sys
import tarfile
import io
import base64

with open(r"C:\Coding\kaggriculture_architecture\submission_phase_all.py", "r", encoding="utf-8") as f:
    code = f.read()
    
# Extract the base64 tar
b64_str = code.split('_TAR_B64 = b"""')[1].split('"""')[0]
tar_bytes = base64.b64decode(b64_str)

with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
    policy_member = tar.getmember("agents/e777a_apex_preemption.py")
    f = tar.extractfile(policy_member)
    content = f.read().decode('utf-8')
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if "def get_dynamic_action" in line:
            print("\n".join(lines[i-5:i+20]))
            break
