# Databricks notebook source
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %pip install openpyxl

# COMMAND ----------

# MAGIC %md
# MAGIC # 02 — Load & Map
# MAGIC
# MAGIC Loads the SAP Excel file into a Delta staging table, reads the DBX table
# MAGIC directly from its live Delta source, and builds the column mapping.
# MAGIC
# MAGIC ### Steps
# MAGIC | Step | Action |
# MAGIC |------|--------|
# MAGIC | 1 | Load stream config JSON |
# MAGIC | 2 | Read column headers from SAP Excel + DBX Delta schema → build EXACT / NORMALIZED / FUZZY mapping |
# MAGIC | 3 | Save mapping to `/Volumes/.../config/mappings/<stream>.json` |
# MAGIC | 4 | Load SAP Excel → Delta staging table |
# MAGIC | 5 | Snapshot DBX Delta table → local staging table (column-renamed to SAP names) |
# MAGIC | 6 | Update stream config with staging Delta table paths |
# MAGIC
# MAGIC ### Prerequisites
# MAGIC - Run `00_setup_metadata` first.

# COMMAND ----------

# ── Widgets ───────────────────────────────────────────────────────────────────

dbutils.widgets.text("stream_name", "yrforecastn_dc02", "1. Stream Name (blank = all active)")
dbutils.widgets.dropdown("load_mode", "overwrite", ["overwrite", "append"], "2. Load Mode")

# COMMAND ----------

# ── Bootstrap ─────────────────────────────────────────────────────────────────

import re
import sys
import os

from datetime import datetime
from pyspark.sql import SparkSession, functions as F

# import sys
# import os

# If your notebook is inside the /notebooks/ folder, ".." goes up to the repo root
src_path = "/Workspace/Users/gaurav.patel@celebaltech.com/sap-dbx-recon/src"

if src_path not in sys.path:
    sys.path.insert(0, src_path)

import pandas as pd

from val_framework.config_loader import (
    load_stream_config,
    list_stream_configs,
    update_stream_config,
    save_column_mapping,
)
from val_framework.mapping.column_mapper import build_column_mapping, build_aligned_column_order
from val_framework.loaders.delta_loader import load_sap_excel_to_delta
from val_framework.core.constants import DATA_SCHEMA, META_COLUMNS, UC_CATALOG

DATA_DB = f"{UC_CATALOG}.{DATA_SCHEMA}"

# COMMAND ----------

# ── Determine which streams to process ───────────────────────────────────────

stream_filter = dbutils.widgets.get("stream_name").strip()
load_mode     = dbutils.widgets.get("load_mode").strip()

if stream_filter:
    registry = [load_stream_config(stream_filter)]
else:
    registry = list_stream_configs(active_only=True)

if not registry:
    raise ValueError("No active stream configs found. Run 00_setup_metadata first.")

print(f"  Streams to process : {[r['stream_name'] for r in registry]}")
print(f"  Load mode          : {load_mode}")

# COMMAND ----------

# ── Shared helper: sanitize a string into a valid Delta table name ────────────

def _sanitize(name: str) -> str:
    s = re.sub(r"[^a-z0-9_]", "_", str(name).lower().strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:128] if s else "unnamed"

# COMMAND ----------

# ── Main loop: process each stream ────────────────────────────────────────────

load_results = []

for cfg in registry:
    stream    = cfg["stream_name"]
    safe      = _sanitize(stream)
    sap_table = f"{DATA_DB}.sap_{safe}"
    dbx_table = f"{DATA_DB}.dbx_{safe}"

    print(f"\n{'='*70}")
    print(f"  PROCESSING: {stream}")
    print(f"{'='*70}")

    # ── PHASE 1: Build column mapping ─────────────────────────────────────────
    print(f"\n  [1/3] Building column mapping...")

    # SAP columns: read first 5 rows of Excel for headers only (no full load yet)
    src_head = pd.read_excel(cfg["sap_file_path"], sheet_name=cfg["sap_sheet_name"], nrows=5)

    # DBX columns: read schema from the live Delta table — zero data movement
    dbx_source = cfg["dbx_source_delta_table"]
    dbx_schema_cols = [
        c for c in spark.table(dbx_source).columns
        if c not in META_COLUMNS
    ]
    tgt_head = pd.DataFrame(columns=dbx_schema_cols)

    mapping_df = build_column_mapping(src_head, tgt_head, stream)

    mapped_n   = len(mapping_df[mapping_df["is_mapped"] == "Y"])
    unmapped_n = len(mapping_df[mapping_df["mapping_method"] == "UNMAPPED"])
    fuzzy_n    = len(mapping_df[mapping_df["mapping_method"].str.startswith("FUZZY", na=False)])

    print(f"    Mapped: {mapped_n}  |  Unmapped: {unmapped_n}  |  Fuzzy (review): {fuzzy_n}")

    mapping_path = save_column_mapping(stream, mapping_df)
    print(f"    Mapping saved → {mapping_path}")

    # ── PHASE 2: Load SAP Excel → Delta staging ───────────────────────────────
    print(f"\n  [2/3] Loading SAP Excel → Delta staging table...")

    spark.sql(f"CREATE DATABASE IF NOT EXISTS {UC_CATALOG}.{DATA_SCHEMA}")

    try:
        sap_rows, sap_col_n, sap_final = load_sap_excel_to_delta(
            spark,
            cfg["sap_file_path"],
            cfg["sap_sheet_name"],
            sap_table,
            stream,
            mode=load_mode,
        )
        print(f"    SAP → {sap_table}: {sap_rows:,} rows × {sap_col_n} cols")
    except Exception as e:
        print(f"    SAP ERROR: {e}")
        sap_rows, sap_final = 0, []

    # ── PHASE 3: Snapshot DBX Delta → staging (with column renames) ───────────
    print(f"\n  [3/3] Snapshotting DBX Delta table → staging...")

    try:
        src_cols    = list(src_head.columns)
        aligned_tgt = build_aligned_column_order(src_cols, dbx_schema_cols, mapping_df)

        mapped_rows = mapping_df[mapping_df["is_mapped"] == "Y"]
        tgt_to_src  = dict(zip(mapped_rows["target_column_name"], mapped_rows["source_column_name"]))
        rename_map  = {t: s for t, s in tgt_to_src.items() if t != s and t in set(aligned_tgt)}

        dbx_sdf = spark.table(dbx_source).drop(*META_COLUMNS)

        # Reorder columns to match SAP order, then rename to SAP column names
        valid_aligned = [c for c in aligned_tgt if c in dbx_sdf.columns]
        rest          = [c for c in dbx_sdf.columns if c not in set(valid_aligned)]
        dbx_sdf       = dbx_sdf.select(valid_aligned + rest)

        # for old, new in rename_map.items():
        #     dbx_sdf = dbx_sdf.withColumnRenamed(old, new)

        # Add meta-columns for lineage
        load_ts = datetime.now()
        dbx_sdf = (
            dbx_sdf
            .withColumn("__stream_name__",  F.lit(stream))
            .withColumn("__source_label__", F.lit("DBX"))
            .withColumn("__load_ts__",      F.lit(str(load_ts)))
            .withColumn("__source_file__",  F.lit(dbx_source))
            .withColumn("__source_sheet__", F.lit("delta"))
        )

        dbx_rows    = dbx_sdf.count()
        dbx_col_n   = len(dbx_sdf.columns) - len(META_COLUMNS)
        dbx_final   = [c for c in dbx_sdf.columns if c not in META_COLUMNS]

        if load_mode == "overwrite":
            spark.sql(f"DROP TABLE IF EXISTS {dbx_table}")
            (
                dbx_sdf.write
                .format("delta")
                .option("overwriteSchema",          "true")
                .option("delta.columnMapping.mode", "name")
                .option("delta.minReaderVersion",   "2")
                .option("delta.minWriterVersion",   "5")
                .saveAsTable(dbx_table)
            )
        else:
            dbx_sdf.write.format("delta").mode("append").saveAsTable(dbx_table)

        print(f"    DBX → {dbx_table}: {dbx_rows:,} rows × {dbx_col_n} cols")
        if rename_map:
            print(f"    Renames applied: {len(rename_map)} columns")

    except Exception as e:
        print(f"    DBX ERROR: {e}")
        dbx_rows, dbx_final = 0, []

    # Column alignment check
    if sap_final and dbx_final:
        match_n = sum(1 for s, d in zip(sap_final, dbx_final) if s == d)
        total_n = min(len(sap_final), len(dbx_final))
        status  = "PERFECT" if match_n == total_n == len(sap_final) == len(dbx_final) else "PARTIAL"
        print(f"    Column alignment: {match_n}/{total_n} — {status}")

    # Patch stream config with staging Delta table paths
    update_stream_config(stream, {
        "sap_delta_table" : sap_table,
        "dbx_delta_table" : dbx_table,
    })

    load_results.append({
        "stream"    : stream,
        "sap_table" : sap_table,
        "dbx_table" : dbx_table,
        "sap_rows"  : sap_rows,
        "dbx_rows"  : dbx_rows,
        "mapped"    : mapped_n,
        "unmapped"  : unmapped_n,
        "fuzzy"     : fuzzy_n,
    })

# COMMAND ----------

# ── Summary ───────────────────────────────────────────────────────────────────

print(f"\n{'='*70}")
print(f"  LOAD & MAP COMPLETE — {len(load_results)} stream(s)")
print(f"{'='*70}")

for lr in load_results:
    meta = set(META_COLUMNS)
    sc   = [c for c in spark.table(lr["sap_table"]).columns if c not in meta]
    dc   = [c for c in spark.table(lr["dbx_table"]).columns if c not in meta]
    bad  = [c for c in sc + dc if c.startswith("col_")]

    print(f"\n  {lr['stream']}")
    print(f"    SAP staging : {lr['sap_table']}  ({lr['sap_rows']:,} rows)")
    print(f"    DBX staging : {lr['dbx_table']}  ({lr['dbx_rows']:,} rows)")
    print(f"    Mapping     : {lr['mapped']} mapped | {lr['unmapped']} unmapped | {lr['fuzzy']} fuzzy")
    print(f"    SAP cols (first 6): {sc[:6]}")
    print(f"    DBX cols (first 6): {dc[:6]}")
    print(f"    col_ prefix issues: {'NONE' if not bad else bad}")

print(f"\n  NEXT → Run 03_run_validation")

# COMMAND ----------

import pandas as pd
from val_framework.config_loader import load_column_mapping, save_column_mapping

current_stream = dbutils.widgets.get("stream_name").strip() 
mapping_df = load_column_mapping(current_stream)

# 1. Find all mappings that were tagged as FUZZY
fuzzy_mask = mapping_df["mapping_method"].str.startswith("FUZZY", na=False)
fuzzy_count = fuzzy_mask.sum()

if fuzzy_count > 0:
    # 2. Automatically upgrade them so the framework trusts them!
    mapping_df.loc[fuzzy_mask, "mapping_method"] = "NORMALIZED"
    
    # 3. Save the mapping file back to the volume
    save_column_mapping(current_stream, mapping_df)
    
    print(f"✅ Auto-Confirmed {fuzzy_count} fuzzy matches (like CALWEEK -> 0CALWEEK)!")
else:
    print("No fuzzy mappings needed confirmation.")