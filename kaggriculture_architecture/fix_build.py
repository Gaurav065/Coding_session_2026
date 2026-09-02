import sys

with open(r"C:\Coding\kaggriculture_architecture\build_phase_all.py", "r") as f:
    content = f.read()

content = content.replace(
    "if not os.path.exists(_TMP_DIR):",
    "if True:"
)

with open(r"C:\Coding\kaggriculture_architecture\build_phase_all.py", "w") as f:
    f.write(content)
