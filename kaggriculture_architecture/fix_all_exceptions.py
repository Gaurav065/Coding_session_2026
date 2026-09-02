import os
import glob

agent_dir = r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\agents"
for fpath in glob.glob(os.path.join(agent_dir, "*.py")):
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    content = content.replace("except Exception:", "except Exception as e:\n        import traceback, sys\n        traceback.print_exc(file=sys.stderr)")
    content = content.replace("except Exception as e:\n        import traceback, sys\n        traceback.print_exc(file=sys.stderr)\n        return", "except Exception as e:\n        import traceback, sys\n        traceback.print_exc(file=sys.stderr)\n        return")
    
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)

print("Replaced all exceptions.")
