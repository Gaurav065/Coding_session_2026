# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 00b — One-Time Manifest Generation
#
# The Batch{N}_checksum_fast.sha256 files are required by Stage 0 but were not
# placed in the ADLS container by the challenge organizers.
# This notebook computes them from actual file metadata and writes them to the
# container root so the integrity check can run as specified.
#
# Run ONCE before the first pipeline execution.
# Format written (one line per check):
#   FILE_COUNT|17
#   TOTAL_SIZE|1367482901
#   FILE_HASH|a3f7c2e8...
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

from modules.config_loader import load_config, apply_spark_conf
from modules.integrity import _list_data_files, _compute_file_hash

import hashlib

cfg = load_config()
apply_spark_conf(spark, cfg)

BASE_PATH = cfg["storage"]["base_path"]
BATCHES   = ["1", "2", "3"]

print(f"Base path : {BASE_PATH}")
print(f"Generating manifests for batches: {BATCHES}")
print()

# COMMAND ----------

# ─── Compute manifest content for each batch ─────────────────────────────────
manifests = {}   # batch_id → manifest text content

for batch_id in BATCHES:
    folder_path   = f"{BASE_PATH}/Batch{batch_id}"
    manifest_path = f"{BASE_PATH}/Batch{batch_id}_checksum_fast.sha256"

    print(f"Batch{batch_id}: listing files in {folder_path} ...")
    files = _list_data_files(dbutils, folder_path)

    file_count  = len(files)
    total_size  = sum(f["size"] for f in files)
    file_hash   = _compute_file_hash(files)

    content = f"FILE_COUNT|{file_count}\nTOTAL_SIZE|{total_size}\nFILE_HASH|{file_hash}\n"
    manifests[batch_id] = (manifest_path, content)

    print(f"  FILE_COUNT : {file_count}")
    print(f"  TOTAL_SIZE : {total_size:,} bytes")
    print(f"  FILE_HASH  : {file_hash}")
    print(f"  → will write to: {manifest_path}")
    print()

# COMMAND ----------

# ─── Write manifest files to ADLS container root ─────────────────────────────
# Uses spark.createDataFrame + coalesce(1).write.text() so ADLS credentials
# are handled automatically via the registered external location.

from pyspark.sql import Row

for batch_id, (manifest_path, content) in manifests.items():
    lines = [Row(value=line) for line in content.strip().split("\n")]
    df = spark.createDataFrame(lines)

    # Write as a single text file — coalesce(1) forces one output part file.
    # We use a temp folder then move the part file to the final name.
    tmp_path = f"{manifest_path}_tmp"

    (
        df.coalesce(1)
        .write
        .mode("overwrite")
        .text(tmp_path)
    )

    # Find the part file Spark wrote and copy it to the manifest filename
    part_files = [f.path for f in dbutils.fs.ls(tmp_path) if f.name.startswith("part-")]
    if not part_files:
        raise RuntimeError(f"No part file found in {tmp_path}")

    dbutils.fs.cp(part_files[0], manifest_path)
    dbutils.fs.rm(tmp_path, recurse=True)

    print(f"✅ Batch{batch_id} manifest written → {manifest_path}")

# COMMAND ----------

# ─── Verify the written manifests can be read back ───────────────────────────
print("\nVerifying written manifests...")
for batch_id in BATCHES:
    manifest_path = f"{BASE_PATH}/Batch{batch_id}_checksum_fast.sha256"
    try:
        lines = spark.read.text(manifest_path).collect()
        print(f"  Batch{batch_id}: ✅ readable ({len(lines)} lines)")
        for row in lines:
            print(f"    {row.value}")
    except Exception as e:
        print(f"  Batch{batch_id}: � could not read back — {e}")

print("\n✅ Manifest generation complete. Run 01_integrity_check next.")
