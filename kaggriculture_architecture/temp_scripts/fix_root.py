import sys
import re

with open(r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\agents\e749a_niklita_consensus_network.py", "r") as f:
    content = f.read()

content = content.replace(
    "ROOT = Path(__file__).resolve().parent.parent.parent",
    "ROOT = Path(__file__).resolve().parent.parent"
)

with open(r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\agents\e749a_niklita_consensus_network.py", "w") as f:
    f.write(content)
