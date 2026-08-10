"""
delta_loader.py
───────────────
Two responsibilities:
  1. load_sap_excel_to_delta() — Read the SAP Excel file from a UC Volume and
                                  write it to a managed Delta staging table.
  2. load_delta_tables()       — Load SAP staging + DBX source Delta tables as
                                  Spark DataFrames for downstream checks.
                                  DBX is read directly from its live Delta table;
                                  no file upload required.

All table writes use the three-level UC namespace from constants.py.
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime
from pyspark.sql import SparkSession, DataFrame as SDF

from val_framework.core.constants import META_COLUMNS, DELTA_TBLPROPERTIES, tblproperties_sql


# ── 1. SAP Excel → Delta staging table ───────────────────────────────────────

def load_sap_excel_to_delta(
    spark: SparkSession,
    file_path: str,
    sheet_name: str,
    table_name: str,
    stream_name: str,
    mode: str = "overwrite",
) -> tuple[int, int, list[str]]:
    """
    Read the SAP Excel file from a UC Volume path and write it to a Delta table.

    Returns (row_count, col_count, final_column_list).

    Notes:
    - file_path must be a /Volumes/... path (not dbfs:/).
    - Attaches meta-columns: __stream_name__, __source_label__, __load_ts__,
      __source_file__, __source_sheet__ (excluded from all validation checks).
    """
    load_ts = datetime.now()

    pdf = pd.read_excel(file_path, sheet_name=sheet_name)
    row_count = len(pdf)
    final_cols = list(pdf.columns)

    pdf["__stream_name__"]  = stream_name
    pdf["__source_label__"] = "SAP"
    pdf["__load_ts__"]      = load_ts
    pdf["__source_file__"]  = file_path
    pdf["__source_sheet__"] = sheet_name

    # Convert to Spark — fallback: stringify object columns if schema inference fails
    try:
        sdf = spark.createDataFrame(pdf)
    except Exception:
        for c in pdf.columns:
            if pdf[c].dtype == object:
                pdf[c] = pdf[c].astype(str)
        sdf = spark.createDataFrame(pdf)

    if mode == "overwrite":
        spark.sql(f"DROP TABLE IF EXISTS {table_name}")
        (
            sdf.write
            .format("delta")
            .option("overwriteSchema",          "true")
            .option("delta.columnMapping.mode", "name")
            .option("delta.minReaderVersion",   "2")
            .option("delta.minWriterVersion",   "5")
            .saveAsTable(table_name)
        )
        props_set = ", ".join(f"'{k}' = '{v}'" for k, v in DELTA_TBLPROPERTIES.items())
        spark.sql(f"ALTER TABLE {table_name} SET TBLPROPERTIES ({props_set})")
    else:
        sdf.write.format("delta").mode("append").saveAsTable(table_name)

    return row_count, len(final_cols), final_cols


# ── 2. Delta → Spark DataFrames ───────────────────────────────────────────────

def load_delta_tables(
    spark: SparkSession,
    sap_table: str,
    dbx_table: str,
) -> tuple[SDF, SDF]:
    """
    Load SAP staging and DBX source Delta tables as lazy Spark DataFrames.
    Drops all META_COLUMNS so validation checks only see data columns.

    sap_table : Managed staging table written by load_sap_excel_to_delta().
    dbx_table : Live Databricks Delta table read directly (no file upload).

    Returns (sap_sdf, dbx_sdf) — no .toPandas(), data stays distributed.
    """
    sap_sdf = spark.table(sap_table).drop(*META_COLUMNS)
    dbx_sdf = spark.table(dbx_table).drop(*META_COLUMNS)

    sap_cols = set(sap_sdf.columns)
    dbx_cols = set(dbx_sdf.columns)
    matched  = len(sap_cols & dbx_cols)
    print(
        f"    Loaded: SAP={sap_table} ({len(sap_sdf.columns)} cols) | "
        f"DBX={dbx_table} ({len(dbx_sdf.columns)} cols) | "
        f"Aligned={matched}/{min(len(sap_cols), len(dbx_cols))}"
    )

    return sap_sdf, dbx_sdf
