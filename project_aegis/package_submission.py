import os
import re
import tarfile
import zipfile

os.makedirs(r'C:\Coding\project_aegis\submission', exist_ok=True)

with open(r'C:\Coding\project_aegis\core.py', 'r', encoding='utf-8') as f:
    core_src = f.read()

with open(r'C:\Coding\project_aegis\predator.py', 'r', encoding='utf-8') as f:
    predator_src = f.read()

with open(r'C:\Coding\project_aegis\river.py', 'r', encoding='utf-8') as f:
    river_src = f.read()

with open(r'C:\Coding\project_aegis\ghost.py', 'r', encoding='utf-8') as f:
    ghost_src = f.read()

with open(r'C:\Coding\project_aegis\guards.py', 'r', encoding='utf-8') as f:
    guards_src = f.read()

with open(r'C:\Coding\project_aegis\tape_loader.py', 'r', encoding='utf-8') as f:
    tape_loader_src = f.read()

with open(r'C:\Coding\project_aegis\main.py', 'r', encoding='utf-8') as f:
    main_src = f.read()

def strip_internal_imports(code: str) -> str:
    # Remove multi-line from project_aegis... import (...)
    code = re.sub(r'from\s+project_aegis\.\w+\s+import\s*\([^)]*\)', '', code, flags=re.MULTILINE)
    # Remove single-line from project_aegis... import ...
    code = re.sub(r'from\s+project_aegis\.\w+\s+import\s+[^\n]+', '', code)
    # Remove import project_aegis...
    code = re.sub(r'import\s+project_aegis\.\w+', '', code)
    return code

header = '''"""Project Aegis: Self-Contained Master Submission for Kaggle Kaggriculture Competition

Standalone bundle containing Core AMM Engine, The Predator Forensics, The River Scaled Trickle,
The Ghost Protocol, Base Tape Oracle Selector, and Execution Guards.
"""

import base64
import copy
import json
import math
import zlib
from typing import Dict, List, Any, Optional, Tuple, Set

'''

combined_source = (
    header + "\n"
    + "# ==================== CORE FOUNDATION & AMM ENGINE ====================\n"
    + strip_internal_imports(core_src) + "\n\n"
    + "# ==================== PREDATOR FORENSICS ENGINE ====================\n"
    + strip_internal_imports(predator_src) + "\n\n"
    + "# ==================== RIVER SCALED TRICKLE ENGINE ====================\n"
    + strip_internal_imports(river_src) + "\n\n"
    + "# ==================== GHOST PROTOCOL & SCAVENGER ====================\n"
    + strip_internal_imports(ghost_src) + "\n\n"
    + "# ==================== EXECUTION & WEED/FEED GUARDS ====================\n"
    + strip_internal_imports(guards_src) + "\n\n"
    + "# ==================== BASE TAPE ORACLE LOADER ====================\n"
    + strip_internal_imports(tape_loader_src) + "\n\n"
    + "# ==================== MASTER AGENT SYNTHESIS ====================\n"
    + strip_internal_imports(main_src) + "\n"
)

submission_main_path = r'C:\Coding\project_aegis\submission\main.py'
with open(submission_main_path, 'w', encoding='utf-8') as f:
    f.write(combined_source)

print(f"Created standalone submission file: {submission_main_path}")

# Bundle into tar.gz
for tar_target in [r'C:\Coding\submission.tar.gz', r'C:\Coding\project_aegis\submission\submission.tar.gz']:
    with tarfile.open(tar_target, 'w:gz') as tar:
        tar.add(submission_main_path, arcname='main.py')
    print(f"Created tar.gz: {tar_target}")

# Bundle into zip
for zip_target in [r'C:\Coding\submission.zip', r'C:\Coding\project_aegis\submission\submission.zip']:
    with zipfile.ZipFile(zip_target, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipf.write(submission_main_path, arcname='main.py')
    print(f"Created zip: {zip_target}")
