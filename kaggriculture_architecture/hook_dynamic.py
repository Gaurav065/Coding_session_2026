import sys

with open(r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\agents\e749a_niklita_consensus_network.py", "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace("action = _source_action(step)", "action = get_dynamic_action(obs, step)")

with open(r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\agents\e749a_niklita_consensus_network.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Injected dynamic action hook.")
