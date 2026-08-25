import shutil
import os

src = r'C:\Coding\project_aegis\submission\main.py'
dst = r'C:\Coding\main.py'
shutil.copyfile(src, dst)
print(f"Copied standalone submission to {dst} ({os.path.getsize(dst) / 1024:.1f} KB)")
