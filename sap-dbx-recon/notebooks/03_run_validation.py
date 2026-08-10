# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Run Validation
# MAGIC
# MAGIC Runs all **12 validation checks** on the aligned Delta staging tables.
# MAGIC Writes results to JSON files on the UC Volume — no Delta result tables.
# MAGIC
# MAGIC ### Check inventory
# MAGIC | # | Check | Category |
# MAGIC |---|-------|----------|
# MAGIC | 1 | row_count | STRUCTURE |
# MAGIC | 2 | column_count | STRUCTURE |
# MAGIC | 3 | mapping_coverage | STRUCTURE |
# MAGIC | 4 | data_type_comparison | SCHEMA |
# MAGIC | 5 | numeric_aggregates | DATA_ACCURACY |
# MAGIC | 6 | distinct_count_comparison | DATA_QUALITY |
# MAGIC | 7 | source_duplicates | DATA_QUALITY |
# MAGIC | 8 | target_duplicates | DATA_QUALITY |
# MAGIC | 9 | hash_comparison | DATA_ACCURACY |
# MAGIC | 10 | sap_minus_dbx | KEY_VALIDATION |
# MAGIC | 11 | dbx_minus_sap | KEY_VALIDATION |
# MAGIC | 12 | pk_issue_summary | KEY_VALIDATION |
# MAGIC
# MAGIC ### Widget notes
# MAGIC - `pk_override` — overrides primary keys for **this run only** without editing the config.
# MAGIC - `exclude_columns` in the stream config JSON drives which columns are skipped during
# MAGIC   value-level checks (numeric aggregates, PK issue summary). Edit the config JSON to change it.

# COMMAND ----------

dbutils.library.restartPython()

# COMMAND ----------

# ── Widgets ───────────────────────────────────────────────────────────────────

dbutils.widgets.text(
    "stream_name", "yrforecastn_dc02",
    "1. Stream Name (blank = all active)",
)
dbutils.widgets.text(
    "pk_override", "",
    "2. PK Override (comma-sep — blank = use config)",
)

# COMMAND ----------

# ── Bootstrap ─────────────────────────────────────────────────────────────────

import re
import sys
import os
import uuid
from datetime import datetime

from pyspark.sql import SparkSession

src_path = "/Workspace/Users/gaurav.patel@celebaltech.com/sap-dbx-recon/src"

if src_path not in sys.path:
    sys.path.insert(0, src_path)
import pandas as pd

from val_framework.config_loader import (
    load_stream_config,
    list_stream_configs,
    load_column_mapping,
    get_primary_keys,
)
from val_framework.core.constants import META_COLUMNS, DATA_SCHEMA, UC_CATALOG
from val_framework.core.result import ValidationResult
from val_framework.core.logger import ValidationLogger
from val_framework.core.runtime_context import get_run_context

from val_framework.checks.structural    import check_row_count, check_column_structure
from val_framework.checks.schema        import check_data_types
from val_framework.checks.data_accuracy import check_numeric_aggregates, check_hash_comparison
from val_framework.checks.data_quality  import check_distinct_counts, check_duplicates
from val_framework.checks.key_validation import (
    check_sap_minus_dbx,
    check_dbx_minus_sap,
    check_pk_issue_summary,
)
from val_framework.report.manifest import build_manifest
from val_framework.report.exporter import write_run_outputs

DATA_DB = f"{UC_CATALOG}.{DATA_SCHEMA}"

# COMMAND ----------

# ── Determine which streams to process ───────────────────────────────────────

stream_filter = dbutils.widgets.get("stream_name").strip()
pk_override   = dbutils.widgets.get("pk_override").strip()

if stream_filter:
    registry = [load_stream_config(stream_filter)]
else:
    registry = list_stream_configs(active_only=True)

if not registry:
    raise ValueError("No active stream configs found. Run 00_setup_metadata first.")

print(f"  Streams : {[r['stream_name'] for r in registry]}")
if pk_override:
    print(f"  PK override ACTIVE: {[c.strip() for c in pk_override.split(',') if c.strip()]}")

# COMMAND ----------

# ── Shared helper: sanitize a string into a valid Delta table name ────────────

def _sanitize(name: str) -> str:
    s = re.sub(r"[^a-z0-9_]", "_", str(name).lower().strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:128] if s else "unnamed"

# COMMAND ----------

# ── Main loop: run checks per stream ─────────────────────────────────────────

overall_results = []

for cfg in registry:
    stream  = cfg["stream_name"]
    run_id  = f"{stream}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
    safe    = _sanitize(stream)
    log     = ValidationLogger(run_id=run_id, stream_name=stream, spark=spark)

    print(f"\n{'='*70}")
    print(f"  STREAM : {stream}")
    print(f"  RUN ID : {run_id}")
    print(f"{'='*70}")

    run_start = datetime.now()

    # Load column mapping and resolve primary keys
    mapping_df = load_column_mapping(stream)
    pk_columns = get_primary_keys(stream, override_csv=pk_override)
    skip_cols  = cfg.get("exclude_columns", [])
    precision  = cfg.get("numeric_precision", 2)

    print(f"  Mapping    : {len(mapping_df)} rows")
    print(f"  Primary keys ({len(pk_columns)}): {pk_columns[:5]}{'...' if len(pk_columns) > 5 else ''}")
    print(f"  Skip cols  : {skip_cols or '—'}")

    if pk_override:
        log.info(f"PK override active: {pk_columns}", check_name="setup")

    # Load Delta staging tables (SAP + DBX snapshots from 02_load_and_map)
    sap_tbl = cfg.get("sap_delta_table") or f"{DATA_DB}.sap_{safe}"
    dbx_tbl = cfg.get("dbx_delta_table") or f"{DATA_DB}.dbx_{safe}"

    sap_sdf = spark.table(sap_tbl).drop(*META_COLUMNS)
    dbx_sdf = spark.table(dbx_tbl).drop(*META_COLUMNS)

    sap_col_n = len(sap_sdf.columns)
    dbx_col_n = len(dbx_sdf.columns)
    aligned   = sum(1 for s, d in zip(sap_sdf.columns, dbx_sdf.columns) if s == d)
    print(f"  Delta: SAP={sap_sdf.count():,}r×{sap_col_n}c | DBX={dbx_sdf.count():,}r×{dbx_col_n}c | aligned={aligned}/{min(sap_col_n, dbx_col_n)}")

    result = ValidationResult(
        run_id      = run_id,
        stream_name = stream,
        source_file = cfg.get("sap_file_path", ""),
        target_file = cfg.get("dbx_source_delta_table", ""),
    )

    # ── STRUCTURE checks ──────────────────────────────────────────────────────
    print(f"\n  Running checks...")
    check_row_count(sap_sdf, dbx_sdf, result, log)
    check_column_structure(sap_sdf, dbx_sdf, mapping_df, result, log)

    # ── SCHEMA check ──────────────────────────────────────────────────────────
    check_data_types(sap_sdf, dbx_sdf, mapping_df, result, log)

    # ── DATA ACCURACY checks ──────────────────────────────────────────────────
    check_numeric_aggregates(sap_sdf, dbx_sdf, mapping_df, result, log,
                             precision=precision, skip_columns=skip_cols)
    check_hash_comparison(sap_sdf, dbx_sdf, mapping_df, pk_columns, result, log,
                          precision=precision)

    # ── DATA QUALITY checks ───────────────────────────────────────────────────
    check_distinct_counts(sap_sdf, dbx_sdf, mapping_df, result, log)
    check_duplicates(sap_sdf, dbx_sdf, result, log)

    # ── KEY VALIDATION checks ─────────────────────────────────────────────────
    _, missing_sdf = check_sap_minus_dbx(sap_sdf, dbx_sdf, mapping_df, pk_columns,
                                          result, log, skip_columns=skip_cols)
    _, orphan_sdf  = check_dbx_minus_sap(sap_sdf, dbx_sdf, mapping_df, pk_columns,
                                          result, log, skip_columns=skip_cols)
    check_pk_issue_summary(sap_sdf, dbx_sdf, mapping_df, pk_columns, result, log,
                           precision=precision, skip_columns=skip_cols)

    # ── Build manifest + export ───────────────────────────────────────────────
    duration_s = (datetime.now() - run_start).total_seconds()
    ctx        = get_run_context(spark)

    stream_reg_dict = {
        "source_file_path"    : cfg.get("sap_file_path", ""),
        "target_file_path"    : cfg.get("dbx_source_delta_table", ""),
        "sap_delta_table"     : sap_tbl,
        "dbx_delta_table"     : dbx_tbl,
        "primary_key_columns" : pk_columns,
        "exclude_columns"     : skip_cols,
    }

    manifest = build_manifest(
        result           = result,
        run_context      = ctx,
        stream_reg       = stream_reg_dict,
        duration_seconds = duration_s,
    )

    manifest_path = write_run_outputs(
        spark        = spark,
        result       = result,
        manifest     = manifest,
        mismatch_sdf = missing_sdf,
        mapping_df   = mapping_df,
    )

    overall_status = result.get_overall_status()
    counts         = result.counts()

    overall_results.append({
        "stream" : stream,
        "run_id" : run_id,
        "status" : overall_status,
        "counts" : counts,
    })

    print(f"\n  {'─'*60}")
    print(f"  RESULT  : {overall_status}")
    print(f"  Checks  : {counts}")
    print(f"  Duration: {duration_s:.1f}s")
    print(f"  Manifest: {manifest_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Run Summary

# COMMAND ----------

# ── Summary table ─────────────────────────────────────────────────────────────

summary_rows = []
for r in overall_results:
    c = r["counts"]
    summary_rows.append({
        "stream"       : r["stream"],
        "run_id"       : r["run_id"],
        "status"       : r["status"],
        "pass"         : c.get("pass",    0),
        "warning"      : c.get("warning", 0),
        "fail"         : c.get("fail",    0),
        "skip"         : c.get("skip",    0),
        "total_checks" : c.get("total",   0),
    })

display(spark.createDataFrame(pd.DataFrame(summary_rows)))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Validation Results — Last Run

# COMMAND ----------

if overall_results:
    import json
    from pathlib import Path
    from val_framework.core.constants import VOLUME_REPORTS_PATH

    last     = overall_results[-1]
    last_cfg = next(c for c in registry if c["stream_name"] == last["stream"])

    checks_path = Path(f"{VOLUME_REPORTS_PATH}/{last['stream']}/{last['run_id']}/checks.json")
    checks_pdf  = pd.DataFrame(json.loads(checks_path.read_text(encoding="utf-8")))

    if not checks_pdf.empty:
        checks_pdf = checks_pdf.sort_values(
            by="status",
            key=lambda s: s.map({"FAIL": 0, "ERROR": 1, "WARNING": 2, "SKIP": 3, "PASS": 4}).fillna(5),
        )
        display(spark.createDataFrame(
            checks_pdf[["check_name", "check_category", "status", "details", "source_value", "target_value"]]
        ))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Column-Level Issues (FAIL + WARNING)

# COMMAND ----------

if overall_results:
    col_path = Path(f"{VOLUME_REPORTS_PATH}/{last['stream']}/{last['run_id']}/column_stats.json")
    col_pdf  = pd.DataFrame(json.loads(col_path.read_text(encoding="utf-8")))
    if not col_pdf.empty:
        issues = col_pdf[col_pdf["status"].isin(["FAIL", "WARNING", "ERROR"])]
        if issues.empty:
            print("  No column-level issues found.")
        else:
            display(spark.createDataFrame(
                issues[["source_column", "target_column", "check_name", "status",
                         "source_value", "target_value", "difference"]]
            ))

# COMMAND ----------

# MAGIC %md
# MAGIC ## PK Issue Summary

# COMMAND ----------

if overall_results:
    pk_path = Path(f"{VOLUME_REPORTS_PATH}/{last['stream']}/{last['run_id']}/pk_issues.json")
    pk_pdf  = pd.DataFrame(json.loads(pk_path.read_text(encoding="utf-8")))
    if pk_pdf.empty:
        print("  No PK issues — all keys matched.")
    else:
        display(spark.createDataFrame(pk_pdf.groupby("issue_type").size().reset_index(name="pk_count")))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Column Mismatch Drill-Down

# COMMAND ----------

if overall_results:
    mismatch_dir = Path(f"{VOLUME_REPORTS_PATH}/{last['stream']}/{last['run_id']}/column_mismatches")
    if mismatch_dir.exists():
        col_files = sorted(mismatch_dir.glob("*.json"))
        print(f"  {len(col_files)} column(s) with mismatches:")
        for cf in col_files:
            data    = json.loads(cf.read_text(encoding="utf-8"))
            total   = data.get("total_rows",   data.get("sampled_rows", 0))
            sampled = data.get("sampled_rows", 0)
            print(f"    {data['column_name']}: {total:,} mismatches  (showing {sampled:,})")
            rows_pdf = pd.DataFrame(data["rows"])
            if not rows_pdf.empty:
                display(spark.createDataFrame(rows_pdf))
    else:
        print("  No column mismatch files (no DATA_MISMATCH or all values matched).")

print("\n  NEXT → Run 05_validation_report to see full report")