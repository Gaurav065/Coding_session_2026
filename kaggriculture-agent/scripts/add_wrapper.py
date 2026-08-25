with open('continuous_agent/final_submission.py', 'r') as f:
    text = f.read()

import re
text = text.replace('def agent(obs):', 'def internal_agent(obs):')

wrapper = """
import traceback

def agent(obs):
    try:
        return internal_agent(obs)
    except Exception as e:
        with open('agent_error.log', 'a') as f:
            f.write(traceback.format_exc() + '\\n')
        return {"farmer": ["PASS"], "hands": [], "market": []}
"""
text += wrapper

with open('continuous_agent/final_submission.py', 'w') as f:
    f.write(text)
print("WRAPPER ADDED")
