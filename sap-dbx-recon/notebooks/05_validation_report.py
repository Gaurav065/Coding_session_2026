# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Validation Report
# MAGIC
# MAGIC Reads results from the **JSON files** written by `03_run_validation`.
# MAGIC No Delta tables or SQL Warehouse required.
# MAGIC
# MAGIC ### Widgets
# MAGIC | Widget | Purpose |
# MAGIC |--------|---------|
# MAGIC | `stream_name` | Which stream to report on |
# MAGIC | `run_id` | Specific run ID (blank = latest) |

# COMMAND ----------

# ── Widgets ───────────────────────────────────────────────────────────────────

dbutils.widgets.text("stream_name", "yrforecastn_dc02", "1. Stream Name")
dbutils.widgets.text("run_id", "","2. Run ID (blank = latest)")

# COMMAND ----------

# ── Bootstrap ─────────────────────────────────────────────────────────────────

import sys
import os

from pyspark.sql import SparkSession

# 0. Tell Databricks where to find the 'val_framework' library
repo_root = os.path.abspath("..") 
src_path = os.path.join(repo_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

import json
import pandas as pd
from pathlib import Path

from val_framework.core.constants import VOLUME_REPORTS_PATH

stream_name   = dbutils.widgets.get("stream_name").strip()
run_id_filter = dbutils.widgets.get("run_id").strip()

if not stream_name:
    raise ValueError("stream_name widget cannot be empty.")

# COMMAND ----------

# ── Resolve run_id ────────────────────────────────────────────────────────────

index_path = Path(f"{VOLUME_REPORTS_PATH}/{stream_name}/run_index.json")

if not index_path.exists():
    raise FileNotFoundError(
        f"No run index found for stream '{stream_name}'.\n"
        f"Expected: {index_path}\n"
        f"Run 03_run_validation first."
    )

run_index = json.loads(index_path.read_text(encoding="utf-8"))

if not run_index:
    raise ValueError(f"run_index.json is empty for stream '{stream_name}'.")

if run_id_filter:
    run_entry = next((r for r in run_index if r["run_id"] == run_id_filter), None)
    if not run_entry:
        raise ValueError(f"run_id '{run_id_filter}' not found in run_index.")
    RUN_ID = run_id_filter
else:
    run_entry = run_index[0]   # Already sorted newest-first
    RUN_ID    = run_entry["run_id"]

print(f"  Stream     : {stream_name}")
print(f"  Run ID     : {RUN_ID}")
print(f"  Status     : {run_entry.get('overall_status', '?')}")
print(f"  Created    : {run_entry.get('created_ts', '?')}")
print(f"  Counts     : {run_entry.get('check_counts', {})}")

run_dir = Path(f"{VOLUME_REPORTS_PATH}/{stream_name}/{RUN_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Run Manifest

# COMMAND ----------

manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
run_meta = manifest.get("run", {})
cluster  = manifest.get("cluster", {})
job_meta = manifest.get("job", {})
data_p   = manifest.get("data_paths", {})

print(f"  Overall status : {run_meta.get('overall_status')}")
print(f"  Duration       : {run_meta.get('duration_seconds', '?')}s")
print(f"  Triggered by   : {run_meta.get('triggered_by', '?')}")
print(f"  Cluster        : {cluster.get('cluster_name','?')} ({cluster.get('dbr_version','?')})")
print(f"  SAP source     : {data_p.get('sap_source','?')}")
print(f"  DBX target     : {data_p.get('dbx_target','?')}")
print(f"  Primary keys   : {data_p.get('primary_keys','?')}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Overall Check Summary (All 12 Checks)

# COMMAND ----------

checks_pdf = pd.DataFrame(json.loads((run_dir / "checks.json").read_text()))

if not checks_pdf.empty:
    checks_pdf = checks_pdf.sort_values(
        by="status",
        key=lambda s: s.map({"FAIL":0,"ERROR":1,"WARNING":2,"SKIP":3,"PASS":4}).fillna(5)
    )
    display(spark.createDataFrame(
        checks_pdf[["check_name","check_category","status","details","source_value","target_value"]]
    ))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Status Breakdown

# COMMAND ----------

if not checks_pdf.empty:
    breakdown = (
        checks_pdf.groupby("status")
        .size()
        .reset_index(name="count")
    )
    breakdown["pct"] = (breakdown["count"] / len(checks_pdf) * 100).round(1)
    breakdown = breakdown.sort_values(
        by="status",
        key=lambda s: s.map({"FAIL":0,"ERROR":1,"WARNING":2,"SKIP":3,"PASS":4}).fillna(5)
    )
    display(spark.createDataFrame(breakdown))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Column-Level Issues (FAIL + WARNING)

# COMMAND ----------

col_pdf = pd.DataFrame(json.loads((run_dir / "column_stats.json").read_text()))

if col_pdf.empty:
    print("  No column-level results.")
else:
    issues = col_pdf[col_pdf["status"].isin(["FAIL","WARNING","ERROR"])].copy()
    if issues.empty:
        print("  All columns PASS.")
    else:
        display(spark.createDataFrame(
            issues[["source_column","target_column","check_name","status",
                     "source_value","target_value","difference"]]
        ))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. PK Issue Summary

# COMMAND ----------

pk_pdf = pd.DataFrame(json.loads((run_dir / "pk_issues.json").read_text()))

if pk_pdf.empty:
    print("  No PK issues — all keys matched cleanly.")
else:
    # Aggregated counts
    agg = pk_pdf.groupby("issue_type").size().reset_index(name="pk_count")
    print(f"  Total PK issues: {len(pk_pdf):,}")
    display(spark.createDataFrame(agg))

    # Detail (first 500 rows)
    display(spark.createDataFrame(
        pk_pdf[["issue_type","primary_key_values","mismatched_columns","details"]].head(500)
    ))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Column Mismatch Drill-Down (DATA_MISMATCH detail)

# COMMAND ----------

mismatch_dir = run_dir / "column_mismatches"

if not mismatch_dir.exists():
    print("  No column mismatch files for this run.")
else:
    col_files = sorted(mismatch_dir.glob("*.json"))
    if not col_files:
        print("  No column mismatch files — all values matched or no DATA_MISMATCH rows.")
    else:
        print(f"  {len(col_files)} mismatched column(s):\n")
        for cf in col_files:
            data    = json.loads(cf.read_text(encoding="utf-8"))
            total   = data.get("total_rows",   data.get("sampled_rows", 0))
            sampled = data.get("sampled_rows", 0)

            print(f"  ── {data['column_name']}  "
                  f"({total:,} mismatches, showing {sampled:,}) ──")

            rows_pdf = pd.DataFrame(data["rows"])
            if not rows_pdf.empty:
                display(spark.createDataFrame(rows_pdf))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Column Mapping Used in This Run

# COMMAND ----------

mapping_file = run_dir / "column_mapping.json"

if mapping_file.exists():
    mp  = json.loads(mapping_file.read_text())
    mp_pdf = pd.DataFrame(mp.get("rows", []))
    if not mp_pdf.empty:
        display(spark.createDataFrame(
            mp_pdf[["source_column_name","target_column_name","mapping_method",
                     "source_dtype","target_dtype","is_mapped"]]
        ))
else:
    print("  column_mapping.json not found — run 02_load_and_map first.")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. Historical Trend (Last 20 Runs)

# COMMAND ----------

trend_rows = []
for entry in run_index[:20]:
    c = entry.get("check_counts", {})
    trend_rows.append({
        "run_id"      : entry["run_id"],
        "created_ts"  : entry.get("created_ts", ""),
        "status"      : entry.get("overall_status", "?"),
        "pass"        : c.get("pass",    0),
        "warning"     : c.get("warning", 0),
        "fail"        : c.get("fail",    0),
        "total"       : c.get("total",   0),
    })

trend_pdf = pd.DataFrame(trend_rows)
if not trend_pdf.empty:
    trend_pdf["pass_rate%"] = (trend_pdf["pass"] / trend_pdf["total"].clip(lower=1) * 100).round(1)
    display(spark.createDataFrame(trend_pdf))

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. SQL MINUS Queries (live, on demand)

# COMMAND ----------

import sys
sys.path.insert(0, "/usr/local/lib/val_framework_so")

from val_framework.core.constants import META_COLUMNS

sap_tbl = manifest.get("data_paths", {}).get("sap_delta_table", "")
dbx_tbl = manifest.get("data_paths", {}).get("dbx_delta_table", "")

if sap_tbl and dbx_tbl:
    except_clause = ", ".join(f"`{c}`" for c in META_COLUMNS)
    pk_cols       = manifest.get("data_paths", {}).get("primary_keys", [])

    print("  Row counts:")
    display(spark.sql(f"""
        SELECT 'SAP' AS src, COUNT(*) AS cnt FROM {sap_tbl}
        UNION ALL
        SELECT 'DBX' AS src, COUNT(*) AS cnt FROM {dbx_tbl}
    """))

    print("\n  SAP − DBX:")
    display(spark.sql(f"""
        SELECT * EXCEPT({except_clause}) FROM {sap_tbl}
        MINUS
        SELECT * EXCEPT({except_clause}) FROM {dbx_tbl}
    """))

    print("\n  DBX − SAP:")
    display(spark.sql(f"""
        SELECT * EXCEPT({except_clause}) FROM {dbx_tbl}
        MINUS
        SELECT * EXCEPT({except_clause}) FROM {sap_tbl}
    """))
else:
    print("  Delta table paths not found in manifest — skipping MINUS queries.")

# COMMAND ----------

# MAGIC %md
# MAGIC ### Row WISE DRILL DOWN

# COMMAND ----------

import json
from pyspark.sql import functions as F
from val_framework.core.constants import META_COLUMNS

# 1. Get table paths and PKs from the run manifest
sap_tbl = manifest.get("data_paths", {}).get("sap_delta_table", "")
dbx_tbl = manifest.get("data_paths", {}).get("dbx_delta_table", "")
pk_cols = manifest.get("data_paths", {}).get("primary_keys", [])

if sap_tbl and dbx_tbl and pk_cols:
    
    sap_df = spark.table(sap_tbl).drop(*META_COLUMNS)
    dbx_df = spark.table(dbx_tbl).drop(*META_COLUMNS)
    
    # 2. Load the mapping file and RENAME DBX columns FIRST
    mapping_file = run_dir / "column_mapping.json"
    mapping_data = json.loads(mapping_file.read_text(encoding="utf-8"))
    
    for row in mapping_data.get("rows", []):
        if row["is_mapped"] == "Y":
            src_col = row["source_column_name"]
            tgt_col = row["target_column_name"]
            if tgt_col in dbx_df.columns and src_col != tgt_col:
                dbx_df = dbx_df.withColumnRenamed(tgt_col, src_col)

    # ---> THE FIX: Deduplicate on Primary Keys NOW (after dbx_df has SAP column names) <---
    sap_df = sap_df.dropDuplicates(subset=pk_cols)
    dbx_df = dbx_df.dropDuplicates(subset=pk_cols)

    # Ensure both dataframes have the exact same columns in the exact same order
    common_cols = [c for c in sap_df.columns if c in dbx_df.columns]
    val_cols = [c for c in common_cols if c not in pk_cols]
    
    sap_df = sap_df.select(*common_cols)
    dbx_df = dbx_df.select(*common_cols)

    # 3. Use EXCEPT to find rows that are completely unique to each side
    sap_diff = sap_df.exceptAll(dbx_df)
    dbx_diff = dbx_df.exceptAll(sap_df)

    # 4. Find PKs that exist in BOTH diffs (this isolates DATA_MISMATCHES)
    mismatch_pks = sap_diff.select(*pk_cols).intersect(dbx_diff.select(*pk_cols))

    # 5. Extract mismatched rows and add the SOURCE flag
    sap_mismatch_rows = sap_diff.join(mismatch_pks, on=pk_cols, how="inner") \
                                .withColumn("SOURCE", F.lit("SAP"))
                                
    dbx_mismatch_rows = dbx_diff.join(mismatch_pks, on=pk_cols, how="inner") \
                                .withColumn("SOURCE", F.lit("DBX"))

    # 6. Combine SAP and DBX rows into one table
    interleaved_df = sap_mismatch_rows.unionByName(dbx_mismatch_rows)

    # 7. Reorder columns: SOURCE flag first, then Primary Keys, then Values
    final_cols = ["SOURCE"] + pk_cols + val_cols
    interleaved_df = interleaved_df.select(*final_cols)

    # 8. Sort by Primary Keys, then by SOURCE descending 
    interleaved_df = interleaved_df.orderBy(*pk_cols, F.col("SOURCE").desc())

    print(f"Showing Interleaved DATA_MISMATCH Drill-Down:")
    display(interleaved_df)
    
else:
    print("Could not load Delta table paths from manifest.")