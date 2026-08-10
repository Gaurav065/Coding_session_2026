"""
exporter.py
───────────
Writes all run outputs to Unity Catalog Volumes (not DBFS, not Delta tables).

Output layout per run:
  /Volumes/<catalog>/reports/run_outputs/<stream>/<run_id>/
    ├── manifest.json          ← Layer-1: always small, loads instantly
    ├── column_mapping.json    ← Mapping used for this run (copy from config)
    ├── checks.json            ← All check summary rows
    ├── column_stats.json      ← Column-level check results
    ├── pk_issues.json         ← MISSING_IN_DBX / MISSING_IN_SAP / DATA_MISMATCH rows
    ├── column_mismatches/
    │   ├── <col_name>.json    ← Side-by-side SAP vs DBX values (one file per column)
    │   └── ...
    └── mismatches.parquet     ← Full row-level mismatch SDF (large, lazy-loaded)

Stream-level index (for trend queries):
  /Volumes/<catalog>/reports/run_outputs/<stream>/run_index.json
    [{run_id, stream_name, overall_status, created_ts, check_counts}, ...]

All paths use /Volumes/... (UC Volume API, DBR 13.3 LTS+ required).
No dbfs:/ paths. No Delta writes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from pyspark.sql import SparkSession, DataFrame as SDF

from val_framework.core.constants import VOLUME_REPORTS_PATH
from val_framework.core.result import ValidationResult


# ── Internal helpers ──────────────────────────────────────────────────────────

def _safe_col_name(col: str) -> str:
    """Sanitize a column name for use as a filename."""
    return re.sub(r"[^\w]", "_", col).strip("_") or "col"


def _write_json(path: Path, data, *, indent: int = 2) -> None:
    """Write data as pretty-printed JSON. Handles datetime via default=str."""
    path.write_text(json.dumps(data, indent=indent, default=str), encoding="utf-8")


# ── Main entry point ──────────────────────────────────────────────────────────

def write_run_outputs(
    spark: SparkSession,
    result: ValidationResult,
    manifest: dict,
    mismatch_sdf: SDF | None = None,
    mapping_df: pd.DataFrame | None = None,
) -> str:
    """
    Write all run outputs to the UC Volume report directory.

    Parameters
    ----------
    spark       : Active SparkSession (needed for Parquet write).
    result      : Populated ValidationResult from the current run.
    manifest    : Dict from report.manifest.build_manifest().
    mismatch_sdf: Optional Spark DataFrame of full row-level mismatches.
    mapping_df  : Optional column mapping DataFrame to copy into the run dir.

    Returns
    -------
    str : Path to the manifest.json file (useful for logging / display).
    """
    run_dir = Path(f"{VOLUME_REPORTS_PATH}/{result.stream_name}/{result.run_id}")
    run_dir.mkdir(parents=True, exist_ok=True)

    # ── Layer 1: manifest.json ────────────────────────────────────────────────
    manifest_path = run_dir / "manifest.json"
    _write_json(manifest_path, manifest)
    print(f"    Written: {manifest_path}")

    # ── Column mapping snapshot (copy of what was used for this run) ──────────
    if mapping_df is not None:
        mapping_path = run_dir / "column_mapping.json"
        _write_json(mapping_path, {
            "stream_name" : result.stream_name,
            "run_id"      : result.run_id,
            "rows"        : mapping_df.to_dict("records"),
        })
        print(f"    Written: {mapping_path}")

    # ── checks.json (all summary rows) ───────────────────────────────────────
    checks_path = run_dir / "checks.json"
    _write_json(checks_path, result.summary_rows)
    print(f"    Written: {checks_path}")

    # ── column_stats.json (column-level results) ──────────────────────────────
    col_path = run_dir / "column_stats.json"
    _write_json(col_path, result.column_rows)
    print(f"    Written: {col_path}")

    # ── pk_issues.json (MISSING + DATA_MISMATCH summary rows) ────────────────
    pk_path = run_dir / "pk_issues.json"
    _write_json(pk_path, result.pk_issue_rows)
    print(f"    Written: {pk_path}")

    # ── column_mismatches/<col>.json (side-by-side SAP vs DBX drill-down) ────
    if result.column_mismatch_rows:
        mismatch_dir = run_dir / "column_mismatches"
        mismatch_dir.mkdir(parents=True, exist_ok=True)

        # Group rows by column name
        col_groups: dict[str, list[dict]] = {}
        col_totals: dict[str, int] = {}

        for row in result.column_mismatch_rows:
            col = row["column_name"]
            col_totals[col] = col_totals.get(col, 0) + 1
            if col not in col_groups:
                col_groups[col] = []
            col_groups[col].append({
                "pk_values" : row["pk_values"],
                "sap_value" : row["sap_value"],
                "dbx_value" : row["dbx_value"],
            })

        for col_name, rows in col_groups.items():
            fname = _safe_col_name(col_name)
            col_file = mismatch_dir / f"{fname}.json"
            _write_json(col_file, {
                "column_name"   : col_name,
                "stream_name"   : result.stream_name,
                "run_id"        : result.run_id,
                "sampled_rows"  : len(rows),
                "total_rows"    : col_totals.get(col_name, len(rows)),
                "rows"          : rows,
            })

        print(f"    Written: {mismatch_dir}/ ({len(col_groups)} columns)")

    # ── mismatches.parquet (full row-level SDF — large, lazy-loaded) ─────────
    if mismatch_sdf is not None:
        parquet_path = str(run_dir / "mismatches.parquet")
        mismatch_sdf.write.mode("overwrite").parquet(parquet_path)
        print(f"    Written: {parquet_path}")

    # ── run_index.json (stream-level run history, used by dashboard trend) ────
    _update_run_index(result, manifest)

    return str(manifest_path)


def _update_run_index(result: ValidationResult, manifest: dict) -> None:
    """
    Append this run to the stream's run_index.json file.
    Keeps the last 100 runs, sorted newest-first.
    """
    index_path = Path(f"{VOLUME_REPORTS_PATH}/{result.stream_name}/run_index.json")

    existing: list[dict] = []
    if index_path.exists():
        try:
            existing = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            existing = []

    # Remove any stale entry for this run_id (re-run scenario)
    existing = [r for r in existing if r.get("run_id") != result.run_id]

    existing.append({
        "run_id"         : result.run_id,
        "stream_name"    : result.stream_name,
        "overall_status" : manifest.get("run", {}).get("overall_status", "UNKNOWN"),
        "created_ts"     : str(result._ts),
        "check_counts"   : result.counts(),
        "primary_keys"   : manifest.get("data_paths", {}).get("primary_keys", []),
    })

    # Sort newest-first, cap at 100 entries
    existing.sort(key=lambda r: r.get("created_ts", ""), reverse=True)
    existing = existing[:100]

    _write_json(index_path, existing)
    print(f"    Updated: {index_path}")
