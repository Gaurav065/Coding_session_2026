import sys

out_path = r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\agents\e749a_niklita_consensus_network.py"

files = [
    r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\job_board.py",
    r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\phase_f_dispatcher.py",
    r"C:\Coding\kaggriculture_architecture\phase_f_dynamic_agent\agent_core.py"
]

combined = ""
for fpath in files:
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith("from phase_f_dispatcher") or line.startswith("from job_board"):
                    continue
                combined += line
            combined += "\n\n"
    except FileNotFoundError:
        pass

with open(out_path, "w", encoding="utf-8") as f:
    f.write(combined)
print(f"Combined into {out_path}")
