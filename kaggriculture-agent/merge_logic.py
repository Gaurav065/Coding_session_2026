import re

with open(r'C:\Coding\kaggriculture-agent\strategy.py', 'r') as f:
    strategy_content = f.read()

with open(r'C:\Coding\kaggriculture-agent\strategy_recovered_full.py', 'r') as f:
    recovered_content = f.read()

# 1. Extract Hand Scaling and Crop Target from strategy.py
match = re.search(r'(# 2\. Hand Scaling Logic.*?)(# 4\. Animal Target Logic)', strategy_content, re.DOTALL)
if match:
    new_logic = match.group(1)
    
    # 2. Replace in recovered_full
    recovered_content = re.sub(r'# 2\. Hand Scaling Logic.*?# 4\. Animal Target Logic', new_logic + '# 4. Animal Target Logic', recovered_content, flags=re.DOTALL)

with open(r'C:\Coding\kaggriculture-agent\strategy_recovered_full.py', 'w') as f:
    f.write(recovered_content)
