# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Validation Report & Dashboard
# MAGIC
# MAGIC View results from the latest validation run (Checks 1-17).
# MAGIC
# MAGIC ### Widgets
# MAGIC | Widget | Purpose |
# MAGIC |--------|---------|
# MAGIC | `results_db` | Database containing result tables |
# MAGIC | `stream_name` | Filter by stream (blank = latest run) |
# MAGIC | `run_id` | Specific run ID (blank = latest) |

# COMMAND ----------

# ══════════════════════════════════════════════════════════════════
#  WIDGETS
# ══════════════════════════════════════════════════════════════════

dbutils.widgets.text("results_db",  "results_db",       "1. Results Database")
dbutils.widgets.text("stream_name", "yrforecastn_dc02", "2. Stream Name (blank=all)")
dbutils.widgets.text("run_id",      "",                 "3. Run ID (blank=latest)")

# COMMAND ----------

RESULTS_DB    = dbutils.widgets.get("results_db").strip()
stream_filter = dbutils.widgets.get("stream_name").strip()
run_id_filter = dbutils.widgets.get("run_id").strip()

# ── Resolve run_id ────────────────────────────────────────────
if run_id_filter:
    RUN_ID = run_id_filter
elif stream_filter:
    row = spark.sql(f"""
        SELECT run_id FROM {RESULTS_DB}.src_tgt_validation_summary
        WHERE stream_name = '{stream_filter}'
        ORDER BY created_ts DESC LIMIT 1
    """).collect()
    if not row:
        raise ValueError(f"No results found for stream '{stream_filter}'")
    RUN_ID = row[0]['run_id']
else:
    row = spark.sql(f"""
        SELECT run_id FROM {RESULTS_DB}.src_tgt_validation_summary
        ORDER BY created_ts DESC LIMIT 1
    """).collect()
    if not row:
        raise ValueError("No validation results found. Run 04_run_validation first.")
    RUN_ID = row[0]['run_id']

print(f"  Report for run_id: {RUN_ID}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## 1. Overall Summary (All 17 Checks)

# COMMAND ----------

summary_df = spark.sql(f"""
    SELECT check_name, check_category, status, details,
           source_value, target_value
    FROM {RESULTS_DB}.src_tgt_validation_summary
    WHERE run_id = '{RUN_ID}'
    ORDER BY
        CASE status WHEN 'FAIL' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END,
        check_category, check_name
""")
display(summary_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 2. Status Breakdown

# COMMAND ----------

status_df = spark.sql(f"""
    SELECT status, COUNT(*) AS check_count,
           ROUND(COUNT(*) * 100.0 / (
               SELECT COUNT(*) FROM {RESULTS_DB}.src_tgt_validation_summary
               WHERE run_id = '{RUN_ID}'
           ), 1) AS pct
    FROM {RESULTS_DB}.src_tgt_validation_summary
    WHERE run_id = '{RUN_ID}'
    GROUP BY status
    ORDER BY CASE status WHEN 'FAIL' THEN 1 WHEN 'WARNING' THEN 2 ELSE 3 END
""")
display(status_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 3. Column-Level Issues (FAIL + WARNING)

# COMMAND ----------

col_issues = spark.sql(f"""
    SELECT source_column, target_column, check_name,
           status, source_value, target_value, difference
    FROM {RESULTS_DB}.src_tgt_column_validation
    WHERE run_id = '{RUN_ID}' AND status IN ('FAIL', 'WARNING')
    ORDER BY status, source_column
""")
display(col_issues)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 4. Column-Wise Success Percentage (PK-Based, CHECK 14)

# COMMAND ----------

success_df = spark.sql(f"""
    SELECT source_column, target_column,
           total_rows_compared, matched_rows, mismatched_rows,
           ROUND(success_pct, 2) AS success_pct, status
    FROM {RESULTS_DB}.src_tgt_column_success_pct
    WHERE run_id = '{RUN_ID}'
    ORDER BY success_pct ASC, source_column
""")
display(success_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 5. Row-Level Mismatches (CHECK 8 Sample)

# COMMAND ----------

row_mm = spark.sql(f"""
    SELECT row_number, column_name, source_value, target_value, mismatch_type
    FROM {RESULTS_DB}.src_tgt_row_mismatches
    WHERE run_id = '{RUN_ID}'
    ORDER BY row_number, column_name
    LIMIT 500
""")
display(row_mm)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 6. Key Mismatches — Source-Target / Target-Source (CHECKs 11-13)

# COMMAND ----------

key_df = spark.sql(f"""
    SELECT check_type, primary_key_values, column_name,
           source_value, target_value, details
    FROM {RESULTS_DB}.src_tgt_key_mismatches
    WHERE run_id = '{RUN_ID}'
    ORDER BY check_type, primary_key_values
    LIMIT 500
""")
display(key_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 7. Mismatch Detail with PK Context (CHECK 15)

# COMMAND ----------

mismatch_df = spark.sql(f"""
    SELECT primary_key_values, column_name,
           source_column, target_column,
           source_value, target_value
    FROM {RESULTS_DB}.src_tgt_mismatch_with_pk
    WHERE run_id = '{RUN_ID}'
    ORDER BY primary_key_values, column_name
    LIMIT 1000
""")
display(mismatch_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 8. PK Issue Summary (CHECK 16)

# COMMAND ----------

pk_agg = spark.sql(f"""
    SELECT issue_type, COUNT(*) AS pk_count
    FROM {RESULTS_DB}.src_tgt_pk_issue_summary
    WHERE run_id = '{RUN_ID}'
    GROUP BY issue_type
    ORDER BY pk_count DESC
""")
display(pk_agg)

# COMMAND ----------

pk_detail = spark.sql(f"""
    SELECT issue_type, primary_key_values,
           mismatched_columns, details
    FROM {RESULTS_DB}.src_tgt_pk_issue_summary
    WHERE run_id = '{RUN_ID}'
    ORDER BY issue_type, primary_key_values
    LIMIT 500
""")
display(pk_detail)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 9. Excluded Columns Audit (CHECK 17)

# COMMAND ----------

excl_df = spark.sql(f"""
    SELECT column_name, exclusion_source, reason
    FROM {RESULTS_DB}.src_tgt_excluded_columns
    WHERE run_id = '{RUN_ID}'
    ORDER BY exclusion_source, column_name
""")
display(excl_df)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 10. MINUS Query Results (CHECK 17)

# COMMAND ----------

minus_agg = spark.sql(f"""
    SELECT direction, COUNT(*) AS row_count
    FROM {RESULTS_DB}.src_tgt_minus_results
    WHERE run_id = '{RUN_ID}'
    GROUP BY direction
""")
display(minus_agg)

# COMMAND ----------

minus_sample = spark.sql(f"""
    SELECT direction, row_data
    FROM {RESULTS_DB}.src_tgt_minus_results
    WHERE run_id = '{RUN_ID}'
    ORDER BY direction
    LIMIT 1000
""")
display(minus_sample)

# COMMAND ----------

# MAGIC %md
# MAGIC ## 11. Historical Trend (Last 10 Runs)

# COMMAND ----------

trend_df = spark.sql(f"""
    WITH runs AS (
        SELECT DISTINCT run_id, stream_name,
               MIN(created_ts) AS run_ts
        FROM {RESULTS_DB}.src_tgt_validation_summary
        GROUP BY run_id, stream_name
        ORDER BY run_ts DESC
        LIMIT 10
    )
    SELECT r.run_id, r.stream_name,
           DATE_FORMAT(r.run_ts, 'yyyy-MM-dd HH:mm') AS run_time,
           SUM(CASE WHEN s.status = 'PASS' THEN 1 ELSE 0 END)    AS pass_count,
           SUM(CASE WHEN s.status = 'WARNING' THEN 1 ELSE 0 END) AS warn_count,
           SUM(CASE WHEN s.status = 'FAIL' THEN 1 ELSE 0 END)    AS fail_count,
           COUNT(*)                                                AS total_checks
    FROM runs r
    JOIN {RESULTS_DB}.src_tgt_validation_summary s ON r.run_id = s.run_id
    GROUP BY r.run_id, r.stream_name, r.run_ts
    ORDER BY r.run_ts DESC
""")
display(trend_df)