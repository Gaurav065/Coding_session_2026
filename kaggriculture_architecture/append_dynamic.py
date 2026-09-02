import sys

out_path = r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\agents\e749a_niklita_consensus_network.py"

files = [
    r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\phase_f_dispatcher.py",
    r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py"
]

combined = ""
for fpath in files:
    with open(fpath, "r", encoding="utf-8") as f:
        lines = f.readlines()
        for line in lines:
            if line.startswith("from phase_f_dispatcher"):
                continue
            if "def agent(obs, config=None):" in line:
                line = line.replace("def agent(obs, config=None):", "def get_dynamic_action(obs, step_ignored):")
            combined += line
        combined += "\n\n"

with open(out_path, "a", encoding="utf-8") as f:
    f.write("\n# --- DYNAMIC PHASE F EXTENSION ---\n")
    f.write(combined)

print("Appended dynamic agent code.")
