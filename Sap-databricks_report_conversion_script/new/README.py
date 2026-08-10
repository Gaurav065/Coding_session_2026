# Databricks notebook source
# MAGIC %md
# MAGIC # SAP <-> Databricks Validation Framework
# MAGIC
# MAGIC ## Quick Start
# MAGIC
# MAGIC | Step | Notebook | Action |
# MAGIC |------|----------|--------|
# MAGIC | 1 | Upload files to Volume | `/Volumes/training/default/validation_volume/` |
# MAGIC | 2 | `00_setup_metadata` | Fill widgets -> Run All (creates tables + registers pair) |
# MAGIC | 3 | `02_dynamic_column_mapper` | Set `stream_name` -> Run All (maps columns) |
# MAGIC | 4 | `04_run_validation` | Set `stream_name` -> Run All (runs 17 checks) |
# MAGIC | 5 | `05_validation_report` | Set `stream_name` -> Run All (view results) |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## 17 Validation Checks
# MAGIC
# MAGIC | # | Check | Category | PK? |
# MAGIC |---|-------|----------|-----|
# MAGIC | 1 | Row Count | STRUCTURE | — |
# MAGIC | 2 | Column Structure | STRUCTURE | — |
# MAGIC | 3 | Data Types (NaN promotion = PASS) | SCHEMA | — |
# MAGIC | 4 | Null Counts | DATA_QUALITY | — |
# MAGIC | 5 | Numeric Aggregates (SUM) | DATA_ACCURACY | — |
# MAGIC | 6 | Distinct Value Counts | DATA_QUALITY | — |
# MAGIC | 7 | Duplicate Rows | DATA_QUALITY | — |
# MAGIC | 8 | Row Data Comparison | DATA_ACCURACY | Yes |
# MAGIC | 9 | Value Distribution | DATA_QUALITY | — |
# MAGIC | 10 | PK Hash Comparison (PK-only) | DATA_ACCURACY | Yes |
# MAGIC | 11 | Source - Target (A-B) | KEY_VALIDATION | Yes |
# MAGIC | 12 | Target - Source (B-A) | KEY_VALIDATION | Yes |
# MAGIC | 13 | PK Value Drill-Down | KEY_VALIDATION | Yes |
# MAGIC | 14 | Column-Wise Success % | DATA_ACCURACY | Yes |
# MAGIC | 15 | Mismatch Detail + PK | DATA_ACCURACY | Yes |
# MAGIC | 16 | PK Issue Summary | KEY_VALIDATION | Yes |
# MAGIC | 17 | MINUS Query | DATA_ACCURACY | — |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Key Features
# MAGIC
# MAGIC **Databricks Widgets** — All configuration via widgets (no hardcoded values).
# MAGIC
# MAGIC **PK-Based Matching** — CHECKs 8, 10, 11-16 join on normalized Primary Key.
# MAGIC Row order is irrelevant.
# MAGIC
# MAGIC **Column Order Alignment** — Target columns auto-reordered to match source.
# MAGIC
# MAGIC **SAP Normalization** — Leading zeros (`000000000001010255` -> `1010255`),
# MAGIC SAP blank sentinels (`000000` -> empty), NULL->0 for numerics, date format normalization.
# MAGIC
# MAGIC **CHECK 3 NaN Tolerance** — `int64->float64` from NaN promotion = PASS (not WARNING).
# MAGIC
# MAGIC **CHECK 10 PK-Only Hash** — Hashes only PK columns for record matching (not all columns).
# MAGIC
# MAGIC **Exclude Columns** — User-defined + auto-detected columns excluded from MINUS query.
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Widget Reference
# MAGIC
# MAGIC | Notebook | Widgets |
# MAGIC |----------|---------|
# MAGIC | `00_setup` | metadata_db, results_db, source_file, target_file, source_sheet, target_sheet, stream_name, sap_table, primary_key_columns, exclude_columns, numeric_precision |
# MAGIC | `01_sap` | metadata_db, sap_catalog, sap_table |
# MAGIC | `02_mapper` | metadata_db, stream_name |
# MAGIC | `04_runner` | metadata_db, results_db, stream_name |
# MAGIC | `05_report` | results_db, stream_name, run_id |
# MAGIC
# MAGIC ---
# MAGIC
# MAGIC ## Delta Tables
# MAGIC
# MAGIC **Metadata:** `validation_file_registry`, `dynamic_column_mapping`, `sap_source_schemas`
# MAGIC
# MAGIC **Results (src_tgt_ prefix):**
# MAGIC `src_tgt_validation_summary`, `src_tgt_column_validation`, `src_tgt_row_mismatches`,
# MAGIC `src_tgt_key_mismatches`, `src_tgt_column_success_pct`, `src_tgt_mismatch_with_pk`,
# MAGIC `src_tgt_pk_issue_summary`, `src_tgt_excluded_columns`, `src_tgt_minus_results`