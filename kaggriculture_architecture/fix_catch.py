import sys

with open(r"C:\Coding\kaggriculture_architecture\submission_phase_all.py", "r") as f:
    content = f.read()

content = content.replace(
    "except Exception:",
    "except Exception as e:\n        import traceback; traceback.print_exc(file=sys.stderr)"
)

with open(r"C:\Coding\kaggriculture_architecture\submission_phase_all.py", "w") as f:
    f.write(content)
