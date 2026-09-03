import sys
import glob
from pathlib import Path

replays_path = r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e751_current_top10_tapes"
files = glob.glob(f"{replays_path}/*.py")
print(f"Found {len(files)} replays in e751")

replays_path2 = r"C:\Coding\kaggriculture_architecture\extracted_notebook_agent\artifacts\e706_top10_tapes"
files2 = glob.glob(f"{replays_path2}/*.py")
print(f"Found {len(files2)} replays in e706")
