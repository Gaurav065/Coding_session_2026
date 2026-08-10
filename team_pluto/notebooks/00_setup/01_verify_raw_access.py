# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 01 — Verify Raw Storage Access
# Quick sanity check: confirms the external location is accessible and lists
# what's in each batch folder. Run this FIRST before anything else.
# ═══════════════════════════════════════════════════════════════════════════════

# COMMAND ----------

import sys
_nb = dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()
_root = _nb.rsplit('/notebooks/', 1)[0] if '/notebooks/' in _nb else _nb.rsplit('/', 2)[0]
if not _root.startswith('/Workspace'): _root = '/Workspace' + _root
# Evict any stale 'modules' cached from other repos on this shared cluster
for _k in list(sys.modules.keys()):
    if _k == 'modules' or _k.startswith('modules.'):
        del sys.modules[_k]
sys.path.insert(0, _root)

from modules.config_loader import load_config

cfg = load_config()

BASE_PATH = cfg["storage"]["base_path"]
BATCHES   = cfg["storage"]["batch_folders"]   # {1: "Batch1", 2: "Batch2", 3: "Batch3"}

print(f"Storage account : {cfg['storage']['account']}")
print(f"Container       : {cfg['storage']['container']}")
print(f"Base path       : {BASE_PATH}")
print(f"Access type     : External location (no mount needed)")

# COMMAND ----------

# ─── Test 1: List root of container ─────────────────────────────────────────
print("\n── Root contents ──────────────────────────────────────────")
try:
    root_items = dbutils.fs.ls(BASE_PATH + "/")
    for item in root_items:
        size_str = f"{item.size:>15,} bytes" if item.size > 0 else "          <folder>"
        print(f"  {item.name:<45} {size_str}")
    print(f"\n  Total items at root: {len(root_items)}")
except Exception as e:
    print(f"  � Cannot list root: {e}")
    raise

# COMMAND ----------

# ─── Test 2: List each batch folder and count files ──────────────────────────
print("\n── Batch folder contents ───────────────────────────────────")
for batch_num, folder_name in BATCHES.items():
    folder_path = f"{BASE_PATH}/{folder_name}"
    try:
        files = dbutils.fs.ls(folder_path)
        data_files   = [f for f in files if not f.name.endswith(".sha256") and not f.name.endswith("/")]
        audit_files  = [f for f in data_files if "_audit" in f.name.lower()]
        source_files = [f for f in data_files if "_audit" not in f.name.lower()]
        total_size   = sum(f.size for f in data_files)

        print(f"\n  {folder_name}/ — {len(data_files)} files, {total_size:,} bytes total")
        print(f"    Source files : {len(source_files)}")
        print(f"    Audit files  : {len(audit_files)}")
        for f in sorted(source_files, key=lambda x: x.name):
            print(f"      {f.name:<45} {f.size:>12,} bytes")
    except Exception as e:
        print(f"\n  � {folder_name}: {e}")

# COMMAND ----------

# ─── Test 3: Verify checksum manifests exist ────────────────────────────────
print("\n── Checksum manifests ──────────────────────────────────────")
for batch_num in BATCHES:
    manifest = f"{BASE_PATH}/Batch{batch_num}_checksum_fast.sha256"
    try:
        info = dbutils.fs.ls(manifest)
        print(f"  ✅ Batch{batch_num}_checksum_fast.sha256  ({info[0].size} bytes)")
    except Exception:
        print(f"  � Batch{batch_num}_checksum_fast.sha256  NOT FOUND")

# COMMAND ----------

# ─── Test 4: Spot-read a small file to confirm decode works ─────────────────
print("\n── Spot read: BatchDate.txt from Batch1 ────────────────────")
try:
    df = spark.read.text(f"{BASE_PATH}/Batch1/BatchDate.txt")
    df.show(truncate=False)
    print("  ✅ Read successful")
except Exception as e:
    print(f"  � Read failed: {e}")

# COMMAND ----------

print("\n✅ Raw access verification complete.")
print(f"   Landing path (writable): {cfg['landing_base_path']}")
print("\nNext step: run notebooks/00_setup/00_catalog_setup.py")
