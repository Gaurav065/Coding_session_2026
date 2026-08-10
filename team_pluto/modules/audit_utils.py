"""
Audit column management.

Each layer has a specific set of audit columns:

  Landing : _landing_ts, _batch, _source_file, _run_id
  Bronze  : _ingest_ts,  _batch, _source_file, _run_id   (drop _landing_ts)
  Silver  : _load_ts,    _batch,               _run_id   (drop _ingest_ts + _source_file)
  Staging : _load_ts,    _batch,               _run_id
  Gold    : _load_ts,    _batch,               _run_id   (new gold load timestamp)
"""
from __future__ import annotations

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import StringType


# ─── Landing ────────────────────────────────────────────────────────────────

def add_landing_audit(df: DataFrame, batch_id: str, source_file: str, run_id: str) -> DataFrame:
    return (
        df
        .withColumn("_landing_ts", F.current_timestamp())
        .withColumn("_batch", F.lit(batch_id))
        .withColumn("_source_file", F.lit(source_file))
        .withColumn("_run_id", F.lit(run_id))
    )


# ─── Bronze ─────────────────────────────────────────────────────────────────

def landing_to_bronze(df: DataFrame) -> DataFrame:
    """Swap _landing_ts → _ingest_ts; carry _batch, _source_file, _run_id."""
    return (
        df
        .drop("_landing_ts")
        .withColumn("_ingest_ts", F.current_timestamp())
    )


def cast_all_to_string(df: DataFrame) -> DataFrame:
    """Cast ALL columns to STRING — Bronze iron rule, no exceptions.
    _ingest_ts is dropped at Silver so TimestampType adds no value in Bronze.

    Uses isinstance() instead of str() comparison — str(StringType()) returns
    'StringType()' in DBR 17+ (Spark 4.0) so string comparison is unreliable.
    """
    for field in df.schema.fields:
        if not isinstance(field.dataType, StringType):
            df = df.withColumn(field.name, F.col(field.name).cast("string"))
    return df


def add_bronze_audit(df: DataFrame, batch_id: str, source_file: str, run_id: str) -> DataFrame:
    """Convenience: add bronze audit columns directly (when not reading from landing)."""
    return (
        df
        .withColumn("_ingest_ts", F.current_timestamp())
        .withColumn("_batch", F.lit(batch_id))
        .withColumn("_source_file", F.lit(source_file))
        .withColumn("_run_id", F.lit(run_id))
    )


# ─── Silver ─────────────────────────────────────────────────────────────────

def bronze_to_silver(df: DataFrame) -> DataFrame:
    """Swap _ingest_ts → _load_ts; drop _source_file."""
    return (
        df
        .drop("_ingest_ts", "_source_file")
        .withColumn("_load_ts", F.current_timestamp())
    )


# ─── Staging ────────────────────────────────────────────────────────────────

def add_staging_audit(df: DataFrame, batch_id: str, run_id: str) -> DataFrame:
    return (
        df
        .withColumn("_load_ts", F.current_timestamp())
        .withColumn("_batch", F.lit(batch_id))
        .withColumn("_run_id", F.lit(run_id))
    )


# ─── Gold ────────────────────────────────────────────────────────────────────

def add_gold_audit(df: DataFrame, batch_id: str, run_id: str) -> DataFrame:
    return (
        df
        .withColumn("_load_ts", F.current_timestamp())
        .withColumn("_batch", F.lit(batch_id))
        .withColumn("_run_id", F.lit(run_id))
    )
