import base64
import json
import zlib
import re

with open(r"C:\Coding\project_doppelganger\ryo_standard_route_master.json", "r", encoding="utf-8") as f:
    std_data = json.load(f)

with open(r"C:\Coding\project_doppelganger\ryo_yarn_route_master.json", "r", encoding="utf-8") as f:
    yarn_data = json.load(f)

std_b85 = base64.b85encode(zlib.compress(json.dumps(std_data).encode("utf-8"), 9)).decode("utf-8")
yarn_b85 = base64.b85encode(zlib.compress(json.dumps(yarn_data).encode("utf-8"), 9)).decode("utf-8")

with open(r"C:\Coding\project_doppelganger\main.py", "r", encoding="utf-8") as f:
    code = f.read()

replacement = f'''_ACTIONS_RYO_STANDARD = json.loads(zlib.decompress(base64.b85decode('{std_b85}')).decode('utf-8'))
_ACTIONS_RYO_YARN = json.loads(zlib.decompress(base64.b85decode('{yarn_b85}')).decode('utf-8'))
'''

pattern = r'# Load Master Compressed Tapes.*?_TAPE_YARN = json\.load\(f\)'
code = re.sub(pattern, replacement.strip(), code, flags=re.DOTALL)
code = code.replace('_TAPE_STANDARD', '_ACTIONS_RYO_STANDARD').replace('_TAPE_YARN', '_ACTIONS_RYO_YARN')

with open(r"C:\Coding\project_doppelganger\main.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated project_doppelganger/main.py with embedded Base85+Zlib compressed tapes!")
