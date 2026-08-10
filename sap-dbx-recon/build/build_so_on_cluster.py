
# Databricks notebook source
# MAGIC %md
# MAGIC # Build — Compile val_framework to Cython .so binaries
# MAGIC
# MAGIC **Run this notebook ONCE on the cluster after any source code change.**
# MAGIC
# MAGIC The compiled `.so` files and `init_script.sh` are saved to the UC Volume:
# MAGIC ```
# MAGIC /Volumes/recon_framework/build/so_cache/
# MAGIC ```
# MAGIC UC Volume path structure: `/Volumes/<catalog>/<schema>/<volume>/<file>`
# MAGIC - catalog : `recon_framework`
# MAGIC - schema  : `build`
# MAGIC - volume  : `so_cache`
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - Run `00_setup_metadata` first — it creates the `recon_framework.build.so_cache` volume.
# MAGIC - Cluster must be DBR 13.3 LTS or above.
# MAGIC - Source code must be in the Databricks Repo attached to this workspace.
# MAGIC
# MAGIC ### After this notebook completes
# MAGIC 1. Configure the cluster init script path:
# MAGIC    `/Volumes/recon_framework/build/so_cache/init_script.sh`
# MAGIC 2. Restart the cluster.

# COMMAND ----------

# MAGIC %pip install cython setuptools --quiet

# COMMAND ----------

import subprocess, sys, os, shutil, json
from pathlib import Path
from datetime import datetime

# ── Paths — update REPO_ROOT to your actual Databricks Repo path ─────────────
REPO_ROOT    = Path("/Workspace/Users/gaurav.patel@celebaltech.com/sap-dbx-recon")
SRC_DIR      = REPO_ROOT / "src" / "val_framework"
BUILD_SCRIPT = REPO_ROOT / "setup_cython.py"

# UC Volume: /Volumes/<catalog>/<schema>/<volume>
# catalog=recon_framework  schema=build  volume=so_cache
SO_VOLUME = Path("/Volumes/recon_framework/build/so_cache")

print(f"Repo root  : {REPO_ROOT}")
print(f"Source dir : {SRC_DIR}")
print(f"SO Volume  : {SO_VOLUME}")
print(f"Python     : {sys.version}")
print(f"Platform   : {sys.platform}")

# Validate paths before starting
if not REPO_ROOT.exists():
    raise FileNotFoundError(
        f"Repo root not found: {REPO_ROOT}\n"
        "Update REPO_ROOT above to match your Databricks Repo path.\n"
        "Find it in: Workspace -> Repos -> right-click repo -> Copy path"
    )
if not SO_VOLUME.exists():
    raise FileNotFoundError(
        f"UC Volume not found: {SO_VOLUME}\n"
        "Run 00_setup_metadata first — it creates recon_framework.build.so_cache."
    )

# COMMAND ----------

# Step 1 — Verify gcc is available (present on all Databricks clusters)
result = subprocess.run(["gcc", "--version"], capture_output=True, text=True)
print(result.stdout.split("\n")[0])

# Step 2 — Install Cython (already done via %pip above, this is a guard)
subprocess.run(
    [sys.executable, "-m", "pip", "install", "cython>=3.0", "setuptools", "-q"],
    check=True,
)

# COMMAND ----------

# Step 3 — Run Cython build (compiles on THIS cluster's Linux Python)
print(f"\n{'='*60}")
print("  Starting Cython compilation...")
print(f"{'='*60}\n")

os.chdir(str(REPO_ROOT))
result = subprocess.run(
    [sys.executable, str(BUILD_SCRIPT)],
    capture_output=True,
    text=True,
)
print(result.stdout)
if result.returncode != 0:
    print("STDERR:", result.stderr)
    raise RuntimeError(f"Cython build failed (exit code {result.returncode})")

# COMMAND ----------

# Step 4 — Collect all .so files produced
so_files = sorted(SRC_DIR.rglob("*.so"))
print(f"\nCompiled {len(so_files)} .so file(s):")
for f in so_files:
    print(f"  {f.name}  ({f.stat().st_size / 1024:.1f} KB)")

if not so_files:
    raise RuntimeError("No .so files found — build may have failed silently.")

# COMMAND ----------

# Step 5 — Copy .so files to UC Volume (preserve val_framework/... subdirs)
#
# UC Volume path: /Volumes/recon_framework/build/so_cache/
#   ├── val_framework/
#   │   ├── __init__.py          (plain .py — required for package discovery)
#   │   ├── config_loader.<hash>.so
#   │   ├── checks/
#   │   │   ├── __init__.py
#   │   │   ├── key_validation.<hash>.so
#   │   │   └── ...
#   │   └── ...
#   ├── init_script.sh
#   └── build_manifest.json

copied = []

for so_file in so_files:
    # Relative to src/  e.g.  val_framework/checks/key_validation.cpython-311...so
    rel  = so_file.relative_to(SRC_DIR.parent)
    dest = SO_VOLUME / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(so_file), str(dest))
    copied.append(str(dest))
    print(f"  Copied: {rel}")

# Also copy __init__.py files — they are NOT compiled to .so but Python
# needs them for package discovery inside the install dir.
for init_file in SRC_DIR.rglob("__init__.py"):
    rel  = init_file.relative_to(SRC_DIR.parent)
    dest = SO_VOLUME / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(init_file), str(dest))
    print(f"  Copied: {rel}  (package init)")

# COMMAND ----------

# Step 6 — Copy init_script.sh to the same UC Volume
#
# CORRECT destination: /Volumes/recon_framework/build/so_cache/init_script.sh
#   (/Volumes/<catalog>/<schema>/<volume>/<filename>)
#
# This is what you register in:
#   Cluster settings -> Advanced -> Init Scripts -> Volume path
#   -> /Volumes/recon_framework/build/so_cache/init_script.sh

init_src  = REPO_ROOT / "build" / "init_script.sh"
init_dest = SO_VOLUME / "init_script.sh"

shutil.copy2(str(init_src), str(init_dest))
print(f"\n  init_script.sh copied -> {init_dest}")
print(f"\n  Cluster init script path to register:")
print(f"    /Volumes/recon_framework/build/so_cache/init_script.sh")

# COMMAND ----------

# Step 7 — Write build manifest
manifest = {
    "built_at"      : datetime.now().isoformat(),
    "python_version": sys.version,
    "platform"      : sys.platform,
    "file_count"    : len(copied),
    "files"         : [str(Path(p).name) for p in copied],
}
manifest_path = SO_VOLUME / "build_manifest.json"
manifest_path.write_text(json.dumps(manifest, indent=2))
print(f"  Build manifest written -> {manifest_path}")

# COMMAND ----------

print(f"\n{'='*60}")
print(f"  BUILD COMPLETE")
print(f"  {len(copied)} .so file(s) in {SO_VOLUME}")
print(f"{'='*60}")
print(f"\n  NEXT STEPS:")
print(f"  1. Go to Compute -> your cluster -> Edit")
print(f"  2. Advanced Options -> Init Scripts -> Add:")
print(f"       /Volumes/recon_framework/build/so_cache/init_script.sh")
print(f"  3. Save + Restart the cluster")
print(f"  4. After restart, the init script auto-loads .so files into sys.path")
