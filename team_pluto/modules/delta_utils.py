"""
Delta Lake write / merge / read helpers.

All writes are idempotent:
  - Landing  : Parquet to UC Volume, one subdirectory per batch — overwrite
               only that batch's directory; other batches untouched.
  - Bronze   : Delta append, guarded by batch+run_id check to prevent double-loading
  - Silver   : MERGE or CREATE OR REPLACE depending on pattern
  - Staging  : overwrite (intermediate workspace)
  - Gold     : MERGE for dimensions, append for facts
"""
from __future__ import annotations

from typing import List

from delta.tables import DeltaTable
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import StringType


# ─── Landing ────────────────────────────────────────────────────────────────

def write_landing(df: DataFrame, volume_path: str) -> int:
    """Write landing DataFrame as Parquet (snappy) to a UC Volume path.

    volume_path must include the batch subdirectory, produced by
    landing_volume_path(cfg, batch_id, table_name), e.g.:
      /Volumes/{catalog}/landing/landing_team_pluto/batch1/watchhistory

    Batch-idempotent: mode("overwrite") replaces only the specific path —
    other batch directories are completely untouched.

    Count is read back from the written Parquet files. Spark reads the
    row-count from each file's footer statistics — no full data scan,
    no driver memory pressure. Safe for large datasets running in parallel.
    """
    (
        df.write
        .format("parquet")
        .mode("overwrite")
        .option("compression", "snappy")
        .save(volume_path)
    )
    return df.sparkSession.read.parquet(volume_path).count()


def read_landing(spark: SparkSession, volume_path: str) -> DataFrame:
    """Read from a landing Parquet Volume path."""
    return spark.read.parquet(volume_path)


def landing_already_exists(spark: SparkSession, volume_path: str) -> bool:
    """Return True if a landing Volume path already contains Parquet data.

    Uses limit(1) so Spark only reads the first row-group header of the
    first file — essentially a metadata check with negligible overhead.
    Returns False if the path doesn't exist or is empty.
    """
    try:
        return spark.read.parquet(volume_path).limit(1).count() > 0
    except Exception:
        return False


# ─── Bronze ─────────────────────────────────────────────────────────────────

def batch_already_in_bronze(spark: SparkSession, table: str, batch_id: str) -> bool:
    """Return True if this batch_id already exists in the Bronze table."""
    try:
        cnt = spark.sql(f"SELECT 1 FROM {table} WHERE _batch = '{batch_id}' LIMIT 1").count()
        return cnt > 0
    except Exception:
        return False


def _bronze_schema_needs_fix(spark: SparkSession, table: str) -> bool:
    """Return True if an existing bronze table has any non-STRING column.

    Uses isinstance(field.dataType, StringType) instead of str() comparison.
    In Databricks Runtime 17+ (Spark 4.0), str(StringType()) returns
    'StringType()' (with parentheses), so string comparison is unreliable
    across runtime versions. isinstance() is always correct.
    """
    try:
        for field in spark.table(table).schema.fields:
            if not isinstance(field.dataType, StringType):
                return True
        return False
    except Exception:
        return False  # table doesn't exist yet — first write will create it correctly


def append_bronze(
    df: DataFrame,
    table: str,
    partition_by: str = "_batch",
    allow_schema_evolution: bool = True,
) -> int:
    """Write to Bronze Delta table, partitioned by _batch.

    Three-path strategy — all paths are idempotent and thread-safe.

    WHY NOT session config / dynamic partition overwrite:
    The orchestrator runs 7 bronze notebooks in parallel via ThreadPoolExecutor.
    All notebooks share the same SparkSession. Setting
    spark.sql.sources.partitionOverwriteMode at session level is a global
    mutation — two threads racing on set("dynamic") / set("static") cause
    one thread to write with the wrong mode and overwrite the entire table.

    Path 3 avoids all session-level config by using DELETE + APPEND:
      - DELETE removes only this batch's rows (WHERE _batch = 'N')
      - APPEND inserts the new rows
    Each thread operates on a different batch value so there are no
    conflicts; Delta's MVCC transaction log makes each step atomic.

    1. Table does not exist → plain overwrite creates it with correct schema.
    2. Table exists with non-STRING columns (stale schema from old runs)
       → full overwrite + overwriteSchema heals schema in one shot.
       Other batch data is restored when those batches are re-run.
    3. Table exists with correct all-STRING schema
       → DELETE this batch's partition then APPEND. No session config
       mutation — safe for parallel execution.
    """
    spark = df.sparkSession

    batch_vals = df.select(partition_by).limit(1).collect()
    batch_val  = batch_vals[0][0] if batch_vals else None

    if not table_exists(spark, table):
        # Path 1 — new table: plain overwrite creates it with correct schema.
        (
            df.write
            .format("delta")
            .mode("overwrite")
            .partitionBy(partition_by)
            .saveAsTable(table)
        )

    elif _bronze_schema_needs_fix(spark, table):
        # Path 2 — schema heal: full overwrite + overwriteSchema fixes types.
        (
            df.write
            .format("delta")
            .mode("overwrite")
            .option("overwriteSchema", "true")
            .partitionBy(partition_by)
            .saveAsTable(table)
        )

    else:
        # Path 3 — idempotent batch replace: DELETE this partition then APPEND.
        # Thread-safe: no session config is mutated. Each parallel thread
        # deletes/inserts its own distinct batch value — no cross-thread conflict.
        if batch_val is not None:
            spark.sql(
                f"DELETE FROM {table} WHERE {partition_by} = '{batch_val}'"
            )
        (
            df.write
            .format("delta")
            .mode("append")
            .saveAsTable(table)
        )

    if batch_val is not None:
        return spark.sql(
            f"SELECT COUNT(*) FROM {table} WHERE {partition_by} = '{batch_val}'"
        ).collect()[0][0]
    return spark.sql(f"SELECT COUNT(*) FROM {table}").collect()[0][0]


def safe_append_bronze(
    spark: SparkSession,
    df: DataFrame,
    table: str,
    batch_id: str,
    run_id: str,
    partition_by: str = "_batch",
) -> tuple[int, str]:
    """Append to Bronze only if batch+run_id not already present.

    Returns (rows_written, status) where status is 'INSERTED' or 'SKIPPED'.
    """
    if batch_already_in_bronze(spark, table, batch_id):
        existing_run = (
            spark.sql(f"SELECT _run_id FROM {table} WHERE _batch='{batch_id}' LIMIT 1")
            .collect()[0][0]
        )
        if existing_run == run_id:
            return 0, "SKIPPED"
    count = append_bronze(df, table, partition_by)
    return count, "INSERTED"


# ─── Overwrite (Staging / Landing refresh) ──────────────────────────────────

def overwrite_table(df: DataFrame, table: str, partition_by: str | None = None) -> int:
    writer = df.write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    if partition_by:
        writer = writer.partitionBy(partition_by)
    writer.saveAsTable(table)
    return df.sparkSession.sql(f"SELECT COUNT(*) FROM {table}").collect()[0][0]


# ─── Silver / Gold MERGE ────────────────────────────────────────────────────

def merge_into(
    spark: SparkSession,
    source_df: DataFrame,
    target_table: str,
    merge_keys: List[str],
    update_cols: List[str] | None = None,
    delete_condition: str | None = None,
) -> dict:
    """Generic SCD-1 MERGE: update matched rows, insert unmatched.

    Args:
        merge_keys    : columns to match on (natural key)
        update_cols   : columns to update on match (None = all source columns)
        delete_condition : SQL expression on source for soft-delete (optional)

    Returns row counts dict with 'inserted', 'updated', 'deleted'.
    """
    if not DeltaTable.isDeltaTable(spark, target_table):
        source_df.write.format("delta").saveAsTable(target_table)
        cnt = spark.sql(f"SELECT COUNT(*) FROM {target_table}").collect()[0][0]
        return {"inserted": cnt, "updated": 0, "deleted": 0}

    target = DeltaTable.forName(spark, target_table)
    cond = " AND ".join(f"t.{k} = s.{k}" for k in merge_keys)

    if update_cols is None:
        update_map = {c: f"s.{c}" for c in source_df.columns}
    else:
        update_map = {c: f"s.{c}" for c in update_cols}

    merger = (
        target.alias("t")
        .merge(source_df.alias("s"), cond)
        .whenMatchedUpdate(set=update_map)
        .whenNotMatchedInsertAll()
    )

    if delete_condition:
        merger = merger.whenNotMatchedBySourceDelete(condition=delete_condition)

    merger.execute()
    return {"inserted": -1, "updated": -1, "deleted": -1}  # DeltaTable.merge() has no row count API


def create_or_replace_table(
    df: DataFrame,
    table: str,
    partition_by: str | None = None,
) -> int:
    """Full rebuild — CREATE OR REPLACE. Used for Silver/Gold full-rebuild tables.

    Args:
        df           : DataFrame to write.
        table        : Fully qualified table name.
        partition_by : Optional column name to partition by (e.g. 'BatchID').
                       Use for large fact tables to enable partition pruning.
    """
    writer = (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("overwriteSchema", "true")
    )
    if partition_by:
        writer = writer.partitionBy(partition_by)
    writer.saveAsTable(table)
    return df.sparkSession.sql(f"SELECT COUNT(*) FROM {table}").collect()[0][0]


# ─── Table existence ─────────────────────────────────────────────────────────

def table_exists(spark: SparkSession, table: str) -> bool:
    try:
        spark.sql(f"DESCRIBE TABLE {table}")
        return True
    except Exception:
        return False


def row_count(spark: SparkSession, table: str, filter_clause: str = "") -> int:
    where = f" WHERE {filter_clause}" if filter_clause else ""
    return spark.sql(f"SELECT COUNT(*) FROM {table}{where}").collect()[0][0]


def optimize_table(
    spark: SparkSession,
    table: str,
    zorder_cols: List[str] | None = None,
) -> None:
    """Run OPTIMIZE (with optional ZORDER BY) on a Delta table.

    Compacts small files written by concurrent/incremental loads into larger
    files (target ~1 GB each) and collects column statistics for data skipping.

    ZORDER co-locates rows with the same key values in the same files, which
    dramatically reduces the number of files scanned for selective queries.

    Typical usage after gold writes:
        optimize_table(spark, tgt_trade, zorder_cols=["SK_AccountID", "SK_SecurityID"])
        optimize_table(spark, tgt_fmh,   zorder_cols=["SK_SecurityID", "SK_DateID"])

    Args:
        spark       : Active SparkSession.
        table       : Fully qualified Delta table name.
        zorder_cols : Columns to Z-order by (up to 4 recommended). Pass None
                      for plain OPTIMIZE without ZORDER.
    """
    if zorder_cols:
        cols = ", ".join(zorder_cols)
        spark.sql(f"OPTIMIZE {table} ZORDER BY ({cols})")
    else:
        spark.sql(f"OPTIMIZE {table}")