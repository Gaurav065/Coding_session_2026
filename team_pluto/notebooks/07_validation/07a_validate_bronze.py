# Databricks notebook source
# ═══════════════════════════════════════════════════════════════════════════════
# 07a — Bronze Validation
# Validates row counts in all Bronze tables against expected values.
# Expected values from the problem statement (test environment).
# Run after ALL batches have been processed to check final cumulative counts.
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
from modules.delta_utils import row_count

cfg = load_config()
apply_spark_conf(spark, cfg)

# COMMAND ----------

dbutils.widgets.text("run_id", "")
dbutils.widgets.text("after_batch", "3")   # validate after which batch (1, 2, or 3)

RUN_ID = dbutils.widgets.get("run_id")
AFTER_BATCH = dbutils.widgets.get("after_batch")

# Expected counts per table per batch from problem statement
# Format: {table_name: {batch: expected_count}}
EXPECTED = {
    "batchdate":        {1: 1,         2: 2,         3: 3},
    "date":             {1: 26_028,    2: 26_028,    3: 26_028},
    "time":             {1: 86_465,    2: 86_465,    3: 86_465},
    "statustype":       {1: 6,         2: 6,         3: 6},
    "taxrate":          {1: 320,       2: 320,       3: 320},
    "industry":         {1: 102,       2: 102,       3: 102},
    "tradetype":        {1: 5,         2: 5,         3: 5},
    "finwire":          {1: 471_446,   2: 471_446,   3: 471_446},   # includes header lines
    "dailymarket":      {1: 5_270_304, 2: 5_277_664, 3: 5_285_024},
    "hr":               {1: 50_000,    2: 50_000,    3: 50_000},
    "customermgmt":     {1: 50_000,    2: 50_000,    3: 50_000},
    "customer":         {1: 0,         2: 50,        3: 100},
    "prospect":         {1: 49_940,    2: 99_880,    3: 149_820},
    "watchhistory":     {1: 3_000_195, 2: 3_007_092, 3: 3_013_989},
    "account":          {1: 0,         2: 100,       3: 200},
    "cashtransaction":  {1: 1_203_664, 2: 1_204_301, 3: 1_204_943},
    "trade":            {1: 1_300_824, 2: 1_302_629, 3: 1_304_387},
    "tradehistory":     {1: 3_267_433, 2: 3_267_433, 3: 3_267_433},
    "holdinghistory":   {1: 1_205_282, 2: 1_205_944, 3: 1_206_578},
}

# COMMAND ----------

from pyspark.sql import functions as F

results = []
after_b = int(AFTER_BATCH)

print(f"Bronze Validation — After Batch {AFTER_BATCH}")
print(f"{'Table':<25} {'Expected':>12} {'Actual':>12} {'Status'}")
print("─" * 62)

pass_count = fail_count = skip_count = 0

for table_name, expected_by_batch in sorted(EXPECTED.items()):
    expected = expected_by_batch.get(after_b, 0)
    full_tbl = tbl(cfg, "bronze", table_name)

    try:
        actual = spark.sql(f"SELECT COUNT(*) FROM {full_tbl}").collect()[0][0]
        if actual == expected:
            status = "✅ PASS"
            pass_count += 1
        else:
            status = f"� FAIL (diff={actual - expected:+,})"
            fail_count += 1
    except Exception as e:
        actual = -1
        status = f"⚠  ERROR: {str(e)[:40]}"
        skip_count += 1

    print(f"  {table_name:<23} {expected:>12,} {actual:>12,}  {status}")
    results.append((table_name, expected, actual, status))

print("─" * 62)
print(f"Result: PASS={pass_count}  FAIL={fail_count}  ERROR={skip_count}")

# COMMAND ----------

# ─── Persist validation results to operations ────────────────────────────────
from datetime import datetime, timezone

RECON_TABLE = tbl(cfg, "operations", "pipeline_recon_results")

rows = [(RUN_ID, AFTER_BATCH, "bronze", r[0], r[1], r[2],
         "PASS" if r[1] == r[2] else "FAIL", datetime.now(timezone.utc))
        for r in results if r[2] >= 0]

cols = ["run_id", "after_batch", "layer", "table_name",
        "expected_rows", "actual_rows", "status", "validated_at"]

df_recon = spark.createDataFrame(rows, cols)
df_recon.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(RECON_TABLE)
print(f"Results written to {RECON_TABLE}")
