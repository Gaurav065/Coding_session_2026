# Databricks notebook source
dbutils.library.restartPython()

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Create catalog
# MAGIC CREATE CATALOG IF NOT EXISTS recon_framework;
# MAGIC
# MAGIC -- ── Schemas for Delta tables 
# MAGIC CREATE SCHEMA IF NOT EXISTS recon_framework.validation_data;
# MAGIC CREATE SCHEMA IF NOT EXISTS recon_framework.audit_logs;
# MAGIC
# MAGIC -- ── Schemas for UC Volumes 
# MAGIC CREATE SCHEMA IF NOT EXISTS recon_framework.validation_inputs;
# MAGIC CREATE SCHEMA IF NOT EXISTS recon_framework.config;
# MAGIC CREATE SCHEMA IF NOT EXISTS recon_framework.reports;
# MAGIC CREATE SCHEMA IF NOT EXISTS recon_framework.build;
# MAGIC
# MAGIC -- ── Volumes 
# MAGIC -- Data input: SAP Excel files
# MAGIC CREATE VOLUME IF NOT EXISTS recon_framework.validation_inputs.raw_files;
# MAGIC
# MAGIC -- Config: stream JSON + column mapping JSON
# MAGIC CREATE VOLUME IF NOT EXISTS recon_framework.config.streams;
# MAGIC CREATE VOLUME IF NOT EXISTS recon_framework.config.mappings;
# MAGIC
# MAGIC -- Reports: JSON manifests + Parquet mismatch files
# MAGIC CREATE VOLUME IF NOT EXISTS recon_framework.reports.run_outputs;
# MAGIC
# MAGIC -- Build: Cython .so binaries + init_script.sh
# MAGIC -- Path structure: /Volumes/recon_framework/build/so_cache/<file>
# MAGIC CREATE VOLUME IF NOT EXISTS recon_framework.build.so_cache;

# COMMAND ----------

# MAGIC %md
# MAGIC # 00 — Setup: Stream Configuration
# MAGIC
# MAGIC Registers a stream by writing a JSON config file to the UC Volume.
# MAGIC
# MAGIC One run of this notebook = one stream registered (or updated).
# MAGIC To change primary keys or excluded columns later, just re-run — no DDL required.
# MAGIC
# MAGIC ### What you need
# MAGIC | Input | Where |
# MAGIC |-------|-------|
# MAGIC | SAP Excel file | Upload to UC Volume, paste the path in widget 2 |
# MAGIC | DBX Delta table | Existing table in your workspace — paste the three-level name in widget 3 |
# MAGIC | Primary key columns | Comma-separated SAP column names in widget 4 |
# MAGIC
# MAGIC ### Next step
# MAGIC Run `02_load_and_map` to load the SAP file and build the column mapping.

# COMMAND ----------

# ── Widgets 

dbutils.widgets.text(
    "stream_name", "yrforecastn_dc02",
    "1. Stream Name",
)
dbutils.widgets.text(
    "sap_file_path",
    "/Volumes/recon_framework/validation_inputs/raw_files/ZLOFOA01 2026.xlsx",
    "2. SAP File Path (UC Volume)",
)
dbutils.widgets.text(
    "dbx_source_delta_table",
    "catalog.schema.table_name",
    "3. DBX Delta Table (catalog.schema.table)",
)
dbutils.widgets.text(
    "primary_key_columns",
    "0CALWEEK,0CALMONTH,0CALYEAR,0CALMONTH2,0FISCPER,0FISCYEAR,"
    "0CALDAY,0FISCPER3,0FISCVARNT,0MATERIAL,0PLANT,0SALES_DIST,0VENDOR",
    "4. Primary Key Columns (comma-separated)",
)

# COMMAND ----------

# ── Parse widget values 

stream_name     = dbutils.widgets.get("stream_name").strip()
sap_file        = dbutils.widgets.get("sap_file_path").strip()
dbx_delta_table = dbutils.widgets.get("dbx_source_delta_table").strip()
pk_raw          = dbutils.widgets.get("primary_key_columns").strip()

pk_cols = [c.strip() for c in pk_raw.split(",") if c.strip()]

if not stream_name:
    raise ValueError("stream_name widget cannot be empty.")
if not pk_cols:
    raise ValueError("primary_key_columns widget cannot be empty.")
if not dbx_delta_table or dbx_delta_table == "catalog.schema.table_name":
    raise ValueError("dbx_source_delta_table must be set to the three-level Delta table name.")

print(f"  Stream          : {stream_name}")
print(f"  SAP file        : {sap_file}")
print(f"  DBX Delta table : {dbx_delta_table}")
print(f"  Primary keys    : {pk_cols}")

# COMMAND ----------

# ── Build and save config 

import sys
import os

from pyspark.sql import SparkSession

repo_root = os.path.abspath("..")
src_path  = os.path.join(repo_root, "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from val_framework.config_loader import build_stream_config, save_stream_config

config = build_stream_config(
    stream_name            = stream_name,
    sap_file_path          = sap_file,
    dbx_source_delta_table = dbx_delta_table,
    primary_key_columns    = pk_cols,
)

saved_path = save_stream_config(config)
print(f"\n  Config saved → {saved_path}")

# COMMAND ----------

# ── Verify: reload and display 

import json
from val_framework.config_loader import load_stream_config

loaded = load_stream_config(stream_name)
print(json.dumps(loaded, indent=2))

# COMMAND ----------

# ── Show all registered streams 

from val_framework.config_loader import list_stream_configs

all_streams = list_stream_configs(active_only=False)
display(spark.createDataFrame([
    {
        "stream_name"            : s["stream_name"],
        "dbx_source_delta_table" : s.get("dbx_source_delta_table", ""),
        "primary_key_columns"    : ", ".join(s.get("primary_key_columns", [])),
        "exclude_columns"        : ", ".join(s.get("exclude_columns", [])) or "—",
        "is_active"              : str(s.get("is_active", True)),
        "updated_at"             : s.get("updated_at", ""),
    }
    for s in all_streams
]))

print(f"\n  NEXT → Run 02_load_and_map for stream '{stream_name}'")