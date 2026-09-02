import json
import base64
import tarfile
import io
import os
import sys

nb_path = r'C:\Users\GauravPatel\Downloads\shape-the-shop-work-the-pasture-kaggriculture.ipynb'
out_dir = r'C:\Coding\kaggriculture_architecture\extracted_notebook_agent'
os.makedirs(out_dir, exist_ok=True)

with open(nb_path, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Find SUBMISSION_PAYLOAD in code cells
globs = {}
for i, cell in enumerate(nb.get('cells', [])):
    src = ''.join(cell.get('source', []))
    if 'SUBMISSION_PAYLOAD' in src:
        print(f"Found SUBMISSION_PAYLOAD in cell {i}!")
        # Execute cell to get SUBMISSION_PAYLOAD
        try:
            exec(src, globs)
        except Exception as e:
            print(f"Exec cell {i} notice: {e}")

if 'SUBMISSION_PAYLOAD' in globs:
    payload = globs['SUBMISSION_PAYLOAD']
    print(f"SUBMISSION_PAYLOAD extracted! Length: {len(payload)} bytes")
    archive_path = os.path.join(out_dir, 'submission.tar.gz')
    with open(archive_path, 'wb') as f:
        f.write(payload)
    
    with tarfile.open(archive_path, 'r:gz') as archive:
        for member in archive.getmembers():
            archive.extract(member, path=out_dir)
            print(f"  Extracted: {member.name} ({member.size} bytes)")
else:
    print("SUBMISSION_PAYLOAD not directly found in globals, searching variables...")
