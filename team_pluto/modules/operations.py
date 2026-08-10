"""
Operations layer logging.

Writes structured events to:
  operations.audit_log          — per-table row counts (Bronze → Gold)
  operations.pipeline_logs      — human-readable pipeline events
  operations.pipeline_run_state — current run_id / batch tracking (1 row)
"""
from __future__ import annotations

from datetime import datetime, timezone

from pyspark.sql import SparkSession
from pyspark.sql import functions as F


# ─── audit_log ───────────────────────────────────────────────────────────────

def log_row_count(
    spark: SparkSession,
    table: str,
    *,
    layer: str,
    source_table: str,
    target_table: str,
    operation: str,
    rows_affected: int,
    batch_id: str,
    run_id: str,
) -> None:
    """Append one row to operations.audit_log."""
    row = [(
        run_id, batch_id, layer, source_table, target_table,
        operation, rows_affected,
        datetime.now(timezone.utc),
    )]
    cols = [
        "run_id", "batch", "layer", "source_table", "target_table",
        "operation", "rows_affected", "log_ts",
    ]
    df = spark.createDataFrame(row, cols)
    df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(table)


# ─── pipeline_logs ───────────────────────────────────────────────────────────

def log_event(
    spark: SparkSession,
    table: str,
    *,
    event_type: str,
    message: str,
    layer: str = "",
    batch_id: str = "",
    run_id: str = "",
    status: str = "INFO",
) -> None:
    row = [(run_id, batch_id, layer, event_type, status, message, datetime.now(timezone.utc))]
    cols = ["run_id", "batch", "layer", "event_type", "status", "message", "log_ts"]
    df = spark.createDataFrame(row, cols)
    df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(table)


# ─── pipeline_run_state ──────────────────────────────────────────────────────

def upsert_run_state(
    spark: SparkSession,
    table: str,
    run_id: str,
    batch_id: str,
    stage: str,
    status: str,
) -> None:
    """Append current pipeline run state."""
    row = [(run_id, batch_id, stage, status, datetime.now(timezone.utc))]
    cols = ["run_id", "batch", "current_stage", "status", "updated_ts"]
    df = spark.createDataFrame(row, cols)
    
    # CHANGED: mode is now "append" instead of "overwrite"
    df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(table)
