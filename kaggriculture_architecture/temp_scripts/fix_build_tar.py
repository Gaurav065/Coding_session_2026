import sys

with open(r"C:\Coding\kaggriculture_architecture\build_phase_all.py", "r") as f:
    content = f.read()

content = content.replace(
    'source_dir = r"C:\\Coding\\kaggriculture_architecture\\extracted_notebook_agent"',
    'source_dir = r"C:\\Coding\\kaggriculture_architecture"\n'
    '            if arcname.startswith("extracted_notebook_agent") or arcname.startswith("artifacts"):\n'
    '                tar.add(filepath, arcname=arcname)\n'
)

with open(r"C:\Coding\kaggriculture_architecture\build_phase_all.py", "w") as f:
    f.write(content)
