with open('continuous_agent/main_dynamic.py', 'r') as f:
    text = f.read()

import re
idx = text.find('def scan_committed_capacity(obs):')
if idx != -1:
    text = text[:idx]

with open('market_logic.py', 'r') as f:
    market_logic = f.read()

with open('agent_logic.py', 'r') as f:
    agent_logic = f.read()

text += market_logic + '\n\n' + agent_logic

with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(text)
print("MARKET & AGENT LOGIC REPLACED")
