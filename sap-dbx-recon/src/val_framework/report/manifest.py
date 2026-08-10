"""
manifest.py
───────────
Builds the Layer-1 run manifest JSON — always small (< 5 KB).
Contains run metadata, cluster context, check summary counts,
and references (paths) to the lazy-loaded Layer-2 detail payloads.

The manifest is the only thing the Streamlit dashboard loads on startup.
Detail payloads (Parquet mismatch rows etc.) are fetched on demand.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from val_framework.core.result import ValidationResult
from val_framework.core.constants import (
    VOLUME_REPORTS_PATH,
    REGISTRY_TABLE, COLUMN_MAP_TABLE,
    SUMMARY_TABLE, COLUMN_VAL_TABLE, PK_ISSUES_TABLE,
)


SCHEMA_VERSION = "2.1"


def build_manifest(
    result: ValidationResult,
    run_context: dict,
    stream_reg: dict,
    duration_seconds: float,
) -> dict:
    """
    Build the run manifest dict from a completed ValidationResult.

    Parameters
    ----------
    result           : Completed ValidationResult with all rows populated.
    run_context      : Output of runtime_context.get_run_context(spark).
    stream_reg       : Registry row dict for this stream (from validation_file_registry).
    duration_seconds : Elapsed wall-clock seconds for the full run.
    """
    counts = result.counts()
    overall = result.get_overall_status()

    run_dir    = f"{VOLUME_REPORTS_PATH}/{result.stream_name}/{result.run_id}"
    detail_refs = {
        "checks"       : f"{run_dir}/checks.json",
        "pk_issues"    : f"{run_dir}/pk_issues.json",
        "column_stats" : f"{run_dir}/column_stats.json",
        "mismatches"   : f"{run_dir}/mismatches.parquet",
    }

    return {
        "schema_version" : SCHEMA_VERSION,
        "run" : {
            "run_id"           : result.run_id,
            "stream_name"      : result.stream_name,
            "overall_status"   : overall,
            "created_ts"       : datetime.now(timezone.utc).isoformat(),
            "duration_seconds" : round(duration_seconds, 1),
            "triggered_by"     : run_context.get("user", "unknown"),
        },
        "cluster" : {
            "cluster_id"    : run_context.get("cluster_id", ""),
            "cluster_name"  : run_context.get("cluster_name", ""),
            "dbr_version"   : run_context.get("dbr_version", ""),
            "spark_version" : run_context.get("spark_version", ""),
            "node_type"     : run_context.get("node_type", ""),
            "num_workers"   : run_context.get("num_workers", ""),
            "cloud_provider": run_context.get("cloud_provider", "Azure"),
        },
        "job" : {
            "job_id"         : run_context.get("job_id", ""),
            "run_id_dbx"     : run_context.get("run_id_dbx", ""),
            "task_key"       : run_context.get("task_key", ""),
            "notebook_path"  : run_context.get("notebook_path", ""),
            "workspace_url"  : run_context.get("workspace_url", ""),
        },
        "data_paths" : {
            "sap_source"       : stream_reg.get("source_file_path", ""),
            "dbx_target"       : stream_reg.get("target_file_path", ""),
            "sap_delta_table"  : stream_reg.get("sap_delta_table", ""),
            "dbx_delta_table"  : stream_reg.get("dbx_delta_table", ""),
            "primary_keys"     : stream_reg.get("primary_key_columns", ""),
            "exclude_columns"  : stream_reg.get("exclude_columns", ""),
        },
        "result_tables" : {
            "summary"          : SUMMARY_TABLE,
            "column_validation": COLUMN_VAL_TABLE,
            "pk_issues"        : PK_ISSUES_TABLE,
        },
        "check_summary" : counts,
        "detail_refs"   : detail_refs,
    }