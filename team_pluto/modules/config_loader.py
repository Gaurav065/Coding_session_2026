"""
Config loader — reads config/config.yaml and exposes helpers
for table references, paths, and Spark settings.
Works with both Unity Catalog (catalog.schema.table)
and Hive Metastore (schema.table) depending on config flag.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


def load_config(config_path: str | None = None) -> dict:
    path = Path(config_path) if config_path else _CONFIG_PATH
    with open(path) as fh:
        return yaml.safe_load(fh)


# ─── Catalog / Table reference helpers ──────────────────────────────────────

def _catalog_prefix(cfg: dict) -> str | None:
    if cfg["catalog"]["use_unity_catalog"]:
        return cfg["catalog"]["name"]
    return None


def tbl(cfg: dict, schema_key: str, table_name: str) -> str:
    """Return fully qualified table name.

    UC mode  : catalog.schema.table
    Hive mode: schema.table
    """
    schema = cfg["schemas"][schema_key]
    prefix = _catalog_prefix(cfg)
    return f"{prefix}.{schema}.{table_name}" if prefix else f"{schema}.{table_name}"


def schema_name(cfg: dict, schema_key: str) -> str:
    """Return schema name, prefixed with catalog if UC enabled."""
    schema = cfg["schemas"][schema_key]
    prefix = _catalog_prefix(cfg)
    return f"{prefix}.{schema}" if prefix else schema


# ─── Storage path helpers ────────────────────────────────────────────────────

def raw_batch_path(cfg: dict, batch_id: int | str) -> str:
    folder = cfg["storage"]["batch_folders"][int(batch_id)]
    return f"{cfg['storage']['base_path']}/{folder}"


def landing_volume_path(cfg: dict, batch_id: int | str, table_name: str) -> str:
    """Return UC Volume path for a landing Parquet dataset.

    Structure: /Volumes/{catalog}/landing/{volume_name}/batch{N}/{table_name}

    Each batch writes to its own subdirectory — re-running batch 1 overwrites
    only batch1/{table} while batch2/ and batch3/ are untouched.
    e.g. /Volumes/charles_schwab_retailbrokerage_dev_team_pluto/landing/landing_team_pluto/batch1/watchhistory
    """
    catalog  = cfg["catalog"]["name"]
    vol_name = cfg.get("landing_volume", "landing_team_pluto")
    return f"/Volumes/{catalog}/landing/{vol_name}/batch{batch_id}/{table_name}"


# ─── Spark configuration helper ─────────────────────────────────────────────

def apply_spark_conf(spark, cfg: dict) -> None:
    """Apply performance tuning from config to the active Spark session."""
    sp = cfg.get("spark", {})

    if sp.get("aqe_enabled", True):
        spark.conf.set("spark.sql.adaptive.enabled", "true")
        spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
        spark.conf.set("spark.sql.adaptive.skewJoin.enabled", "true")

    # AQE advisory partition size — target size after coalescePartitions
    advisory = sp.get("advisory_partition_bytes", "134217728")
    spark.conf.set("spark.sql.adaptive.advisoryPartitionSizeInBytes", str(advisory))

    # AQE local shuffle reader — reads map output from local disk instead of remote fetch
    if sp.get("local_shuffle_reader", True):
        spark.conf.set("spark.sql.adaptive.localShuffleReader.enabled", "true")

    shuffle = sp.get("shuffle_partitions", "auto")
    if shuffle != "auto":
        spark.conf.set("spark.sql.shuffle.partitions", str(shuffle))

    max_part = sp.get("max_partition_bytes", "134217728")
    spark.conf.set("spark.sql.files.maxPartitionBytes", str(max_part))

    broadcast = sp.get("broadcast_threshold_bytes", "209715200")
    spark.conf.set("spark.sql.autoBroadcastJoinThreshold", str(broadcast))

    if sp.get("optimize_write", True):
        spark.conf.set("spark.databricks.delta.optimizeWrite.enabled", "true")

    if sp.get("auto_compact", True):
        spark.conf.set("spark.databricks.delta.autoCompact.enabled", "true")

    # Low-shuffle MERGE — Delta rewrites only partitions that contain matched rows
    if sp.get("delta_low_shuffle_merge", True):
        spark.conf.set("spark.databricks.delta.merge.enableLowShuffle", "true")

    # Databricks IO cache — transparent SSD-backed block cache for Delta reads
    if sp.get("io_cache_enabled", False):
        spark.conf.set("spark.databricks.io.cache.enabled", "true")
