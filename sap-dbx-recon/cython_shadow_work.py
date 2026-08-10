# Databricks notebook source
import os
import glob

# Your framework source path
src_path = "/Workspace/Users/gaurav.patel@celebaltech.com/sap-dbx-recon/src"

# Find all compiled Cython files (.so and .c)
so_files = glob.glob(f"{src_path}/**/*.so", recursive=True)
c_files = glob.glob(f"{src_path}/**/*.c", recursive=True)

print(f"🧹 Found {len(so_files)} .so files and {len(c_files)} .c files to clean.")

# Delete them safely
for f in so_files + c_files:
    try:
        os.remove(f)
    except Exception as e:
        print(f"Could not delete {f}: {e}")

print("✅ Cleanup complete! Your framework is now pure Python.")