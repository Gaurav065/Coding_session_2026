#!/usr/bin/env python3
"""
Package RSNA Knee code for Kaggle.
Run this locally, then upload the output zip to Kaggle or copy files.
"""
import os
import shutil
from pathlib import Path

SRC = Path(r"C:\Coding\rsna_knee")
DST = Path(r"C:\Coding\rsna_knee_kaggle")

# Files/dirs to include
INCLUDE = [
    "src/",
    "configs/",
    "kaggle_train.ipynb",
    "requirements.txt",
]

# Clean destination
if DST.exists():
    shutil.rmtree(DST)
DST.mkdir(parents=True)

# Copy included items
for item in INCLUDE:
    src_path = SRC / item
    dst_path = DST / item
    if src_path.is_dir():
        shutil.copytree(src_path, dst_path)
    else:
        shutil.copy2(src_path, dst_path)

# Create dataset-metadata.json for kaggle datasets CLI
meta = {
    "title": "RSNA Knee Abnormality Detection - Code",
    "id": "yourusername/rsna-knee-code",
    "licenses": [{"name": "MIT"}],
}
import json
(DST / "dataset-metadata.json").write_text(json.dumps(meta, indent=2))

print(f"Packaged to {DST}")
print("Upload with: kaggle datasets create -p", DST, "--dir-mode zip")
print("Or copy files from this folder to Kaggle notebook")