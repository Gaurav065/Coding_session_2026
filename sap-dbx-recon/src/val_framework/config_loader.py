"""
config_loader.py
────────────────
Load / save / list stream configuration JSON files from UC Volume.

Layout on UC Volume:
  /Volumes/<catalog>/config/streams/<stream_name>.json   ← stream config
  /Volumes/<catalog>/config/mappings/<stream_name>.json  ← column mapping

Both paths are POSIX-accessible on DBR 13.3 LTS+ cluster nodes.
For Databricks Apps, use the SDK Files API (w.files.download/upload).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from val_framework.core.constants import (
    VOLUME_CONFIG_PATH,
    VOLUME_MAPPINGS_PATH,
    DEFAULT_NUMERIC_PRECISION,
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _config_path(stream_name: str) -> Path:
    return Path(VOLUME_CONFIG_PATH) / f"{stream_name}.json"


def _mapping_path(stream_name: str) -> Path:
    return Path(VOLUME_MAPPINGS_PATH) / f"{stream_name}.json"


# ── Stream config CRUD ────────────────────────────────────────────────────────

def build_stream_config(
    stream_name: str,
    sap_file_path: str,
    dbx_source_delta_table: str,
    primary_key_columns: list[str],
    sap_sheet_name: str = "Sheet2",
    exclude_columns: list[str] | None = None,
    is_active: bool = True,
) -> dict:
    """
    Build a validated stream config dict ready to be saved by save_stream_config().

    sap_file_path          : UC Volume path to the SAP Excel file.
    dbx_source_delta_table : Three-level UC table name of the existing Databricks
                             Delta table (catalog.schema.table). No file upload needed.
    primary_key_columns    : SAP column names forming the composite PK.
    exclude_columns        : Columns to skip during value-level checks (e.g. timestamps).
    """
    if not stream_name.strip():
        raise ValueError("stream_name cannot be empty.")
    if not primary_key_columns:
        raise ValueError("primary_key_columns cannot be empty.")

    return {
        "stream_name"            : stream_name,
        "sap_file_path"          : sap_file_path,
        "sap_sheet_name"         : sap_sheet_name,
        "dbx_source_delta_table" : dbx_source_delta_table,
        "primary_key_columns"    : [c.strip() for c in primary_key_columns if c.strip()],
        "exclude_columns"        : [c.strip() for c in (exclude_columns or []) if c.strip()],
        "numeric_precision"      : DEFAULT_NUMERIC_PRECISION,
        "is_active"              : is_active,
        # Staging Delta tables — populated by 02_load_and_map after loading
        "sap_delta_table"        : "",
        "dbx_delta_table"        : "",
        "created_at"             : datetime.now().isoformat(),
        "updated_at"             : datetime.now().isoformat(),
    }


def save_stream_config(config: dict) -> str:
    """
    Write a stream config dict to its JSON file on UC Volume.
    Creates parent directories if needed. Returns the saved file path.
    """
    stream_name = config.get("stream_name", "").strip()
    if not stream_name:
        raise ValueError("Config must contain a non-empty 'stream_name'.")

    config["updated_at"] = datetime.now().isoformat()

    path = _config_path(stream_name)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, default=str)

    return str(path)


def load_stream_config(stream_name: str) -> dict:
    """
    Load and return the stream config dict for the given stream.
    Raises FileNotFoundError if the config doesn't exist.
    """
    path = _config_path(stream_name)
    if not path.exists():
        raise FileNotFoundError(
            f"Stream config not found: {path}\n"
            f"Run notebook 00_setup_metadata to register stream '{stream_name}'."
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def update_stream_config(stream_name: str, updates: dict) -> str:
    """
    Merge updates into an existing stream config and save.
    Use this to patch individual fields (e.g., after loading Delta tables).
    Returns the saved file path.
    """
    config = load_stream_config(stream_name)
    config.update(updates)
    return save_stream_config(config)


def list_stream_configs(active_only: bool = True) -> list[dict]:
    """
    Return all stream configs found in VOLUME_CONFIG_PATH.
    Sorted by stream_name. Skips files that fail to parse.
    """
    base = Path(VOLUME_CONFIG_PATH)
    if not base.exists():
        return []

    configs = []
    for p in sorted(base.glob("*.json")):
        try:
            with p.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            if active_only and not cfg.get("is_active", True):
                continue
            configs.append(cfg)
        except Exception:
            pass

    return configs


def get_primary_keys(stream_name: str, override_csv: str = "") -> list[str]:
    """
    Return the primary key columns for a stream.

    override_csv : If non-empty (e.g. from a widget), this takes precedence
                   over whatever is stored in the stream config. This allows
                   per-run PK overrides without editing the config file.
    """
    if override_csv and override_csv.strip():
        return [c.strip() for c in override_csv.split(",") if c.strip()]

    config = load_stream_config(stream_name)
    return config.get("primary_key_columns", [])


# ── Column mapping JSON CRUD ──────────────────────────────────────────────────

def save_column_mapping(stream_name: str, mapping_df: pd.DataFrame) -> str:
    """
    Serialize a mapping DataFrame to JSON and save to VOLUME_MAPPINGS_PATH.
    Returns the saved file path.
    """
    path = _mapping_path(stream_name)
    path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "stream_name" : stream_name,
        "saved_at"    : datetime.now().isoformat(),
        "rows"        : mapping_df.to_dict("records"),
    }

    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)

    return str(path)


def load_column_mapping(stream_name: str) -> pd.DataFrame:
    """
    Load the column mapping DataFrame from JSON.
    Raises FileNotFoundError if the mapping file doesn't exist.
    """
    path = _mapping_path(stream_name)
    if not path.exists():
        raise FileNotFoundError(
            f"Column mapping not found: {path}\n"
            f"Run notebook 02_load_and_map first."
        )

    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    df = pd.DataFrame(payload.get("rows", []))

    # Restore integer columns that JSON serializes as float
    for col in ("source_column_index", "target_column_index"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(-1).astype(int)

    return df
