# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 01 — Raw Zone Integrity Check (Stage 0)
# Verifies FILE_COUNT, TOTAL_SIZE, FILE_HASH for each batch against
# the pre-generated Batch{N}_checksum_fast.sha256 manifests.
# Pipeline MUST NOT proceed if any batch FAILS.
# Results persisted to operations.integrity_check.
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

from modules.config_loader import load_config, tbl, apply_spark_conf
from modules.integrity import verify_batch, persist_results

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

# ─── Parameters ─────────────────────────────────────────────────────────────
dbutils.widgets.text("run_id", "")
RUN_ID = dbutils.widgets.get("run_id") or spark.sql("SELECT date_format(current_timestamp(), 'yyyyMMdd_HHmmss')").collect()[0][0]

BASE_PATH = cfg["storage"]["base_path"]
INTEGRITY_TABLE = tbl(cfg, "operations", "integrity_check")
BATCHES = ["1", "2", "3"]

print(f"Run ID : {RUN_ID}")
print(f"Base   : {BASE_PATH}")
print(f"Target : {INTEGRITY_TABLE}")

# COMMAND ----------

# ─── Run integrity checks for all 3 batches ──────────────────────────────────
import time

results = []
start = time.time()

for batch_id in BATCHES:
    print(f"\nChecking Batch{batch_id}...", end=" ")
    result = verify_batch(spark, dbutils, batch_id, BASE_PATH, RUN_ID)
    results.append(result)

    icon = "✅ PASS" if result.status == "PASS" else ("⚠️  FAIL" if result.status == "FAIL" else "❌ ERROR")
    print(f"{icon}")
    if result.status != "PASS":
        print(f"  Detail: {result.error_detail}")
    else:
        print(f"  Files={result.actual_file_count}, Size={result.actual_total_size:,} bytes, Hash OK")

elapsed = time.time() - start
print(f"\n{'─'*60}")
print(f"Integrity Check: {len(BATCHES)} batches | "
      f"PASS={sum(1 for r in results if r.status=='PASS')} "
      f"FAIL={sum(1 for r in results if r.status=='FAIL')} "
      f"ERR={sum(1 for r in results if r.status=='ERROR')} "
      f"| {elapsed:.1f}s")

# COMMAND ----------

# ─── Persist results to operations.integrity_check ──────────────────────────
persist_results(spark, results, INTEGRITY_TABLE)
print(f"Results written to {INTEGRITY_TABLE}")

# COMMAND ----------

# ─── Gate logic ──────────────────────────────────────────────────────────────
# FAIL   = manifest found but FILE_COUNT / TOTAL_SIZE / FILE_HASH mismatch
#          → hard halt: data is provably corrupt, do not ingest
# ERROR  = manifest not found in ADLS (environment / setup issue)
#          → non-blocking warning per spec: log, alert, continue
#          spec: "Pipeline Warns on Failure — Non-blocking alert"
failed  = [r for r in results if r.status == "FAIL"]
errored = [r for r in results if r.status == "ERROR"]

if errored:
    batch_names = ", ".join(f"Batch{r.batch}" for r in errored)
    print(f"\n⚠  Manifests not found for {len(errored)} batch(es): {batch_names}")
    print("   Integrity results logged to operations.integrity_check.")
    print("   Pipeline proceeds — place Batch{{N}}_checksum_fast.sha256 at ADLS root to enable full validation.")

if failed:
    batch_names = ", ".join(f"Batch{r.batch}" for r in failed)
    msg = f"INTEGRITY CHECK FAILED: {len(failed)} batch(es) have corrupt data: {batch_names}"
    print(f"\n⛔  {msg}")
    raise RuntimeError(msg)

if not failed and not errored:
    print("\n✅ All batches passed integrity check. Pipeline may proceed.")

# COMMAND ----------

# ─── Display summary ─────────────────────────────────────────────────────────
display(spark.sql(f"SELECT batch, status, actual_file_count, actual_size, hash_match, error_detail, check_timestamp FROM {INTEGRITY_TABLE} WHERE run_id = '{RUN_ID}' ORDER BY batch"))
