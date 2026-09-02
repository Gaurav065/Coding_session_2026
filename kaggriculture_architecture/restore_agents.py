import tarfile
import os

tar_path = r"C:\Coding\kaggriculture_architecture\submission\submission.tar.gz"
dest_dir = r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent"

with tarfile.open(tar_path, "r:gz") as tar:
    tar.extractall(dest_dir)
print("Restored original agents.")
