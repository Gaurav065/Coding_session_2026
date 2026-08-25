with open('continuous_agent/main_dynamic.py', 'r') as f:
    text = f.read()

text = text.replace('def load_tapes():\\n    pass\\n# def old_tapes():', 'def load_tapes():\n    pass\n')
with open('continuous_agent/main_dynamic.py', 'w') as f:
    f.write(text)
print("FIXED")
