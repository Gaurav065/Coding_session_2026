with open('continuous_agent/main_dynamic.py', 'r') as f:
    text = f.read()

import re
idx = text.find('def agent(obs')
if idx != -1:
    text = text[:idx]

with open('agent_logic.py', 'r') as f:
    agent_logic = f.read()

text += agent_logic

with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(text)
print("AGENT LOGIC REPLACED")
