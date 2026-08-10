"""
column_mapper.py
────────────────
Build and align column mappings between SAP source and DBX target.

Mapping methods (in priority order):
  EXACT      — column names match exactly
  NORMALIZED — match after stripping non-alphanumeric chars and lowercasing
  FUZZY      — SequenceMatcher ratio >= FUZZY_MATCH_THRESHOLD (WARNING: unconfirmed)
  UNMAPPED   — no match found in target

FUZZY mappings are flagged as WARNING and excluded from data accuracy checks
(check_numeric_aggregates, check_pk_issue_summary) until manually confirmed.
"""

import re
import pandas as pd
from difflib import SequenceMatcher
from pyspark.sql import DataFrame as SDF
from pyspark.sql import functions as F

from val_framework.core.constants import FUZZY_MATCH_THRESHOLD


def _normalize_name(name: str) -> str:
    """Strip SAP namespaces, non-alphanumeric chars, and lowercase."""
    # Remove standard SAP custom namespaces before normalizing
    clean_name = str(name).upper().replace("/BIC/", "").replace("/BA1/", "")
    return re.sub(r"[^a-z0-9]", "", clean_name.lower().strip())


def build_column_mapping(
    src_df: pd.DataFrame,
    tgt_df: pd.DataFrame,
    stream_name: str,
) -> pd.DataFrame:
    """
    Build a column mapping DataFrame from SAP source headers to DBX target headers.

    Parameters
    ----------
    src_df      : Pandas DataFrame (or header-only slice) of the SAP source.
    tgt_df      : Pandas DataFrame (or header-only slice) of the DBX target.
    stream_name : Stream identifier (stored in mapping table).

    Returns
    -------
    pd.DataFrame with columns matching dynamic_column_mapping schema.
    """
    tgt_cols   = list(tgt_df.columns)
    tgt_index  = {c: i for i, c in enumerate(tgt_cols)}
    tgt_norm   = {}   # normalized_name → (index, original_name)
    for i, tc in enumerate(tgt_cols):
        k = _normalize_name(tc)
        if k not in tgt_norm:
            tgt_norm[k] = (i, tc)

    matched_tgt = set()
    rows = []

    for si, sc in enumerate(src_df.columns):
        row = {
            "stream_name"         : stream_name,
            "source_column_name"  : sc,
            "source_column_index" : si,
            "target_column_name"  : "",
            "target_column_index" : -1,
            "mapping_method"      : "UNMAPPED",
            "source_dtype"        : _infer_dtype(src_df[sc]),
            "target_dtype"        : "",
            "sap_field_name"      : "",
            "sap_datatype"        : "",
            "is_mapped"           : "N",
            "is_active"           : "Y",
        }

        # 1. Exact match
        if sc in tgt_index and sc not in matched_tgt:
            row.update({
                "target_column_name"  : sc,
                "target_column_index" : tgt_index[sc],
                "target_dtype"        : _infer_dtype(tgt_df[sc]),
                "mapping_method"      : "EXACT",
                "is_mapped"           : "Y",
            })
            matched_tgt.add(sc)

        # 2. Normalized match
        elif _normalize_name(sc) in tgt_norm:
            ti, tc = tgt_norm[_normalize_name(sc)]
            if tc not in matched_tgt:
                row.update({
                    "target_column_name"  : tc,
                    "target_column_index" : ti,
                    "target_dtype"        : _infer_dtype(tgt_df[tc]),
                    "mapping_method"      : "NORMALIZED",
                    "is_mapped"           : "Y",
                })
                matched_tgt.add(tc)

        # 3. Fuzzy match (flagged as WARNING — excluded from accuracy checks)
        else:
            best_ratio, best_tc = 0.0, None
            for tc in tgt_cols:
                if tc in matched_tgt:
                    continue
                ratio = SequenceMatcher(None, _normalize_name(sc), _normalize_name(tc)).ratio()
                if ratio > best_ratio:
                    best_ratio, best_tc = ratio, tc

            if best_ratio >= FUZZY_MATCH_THRESHOLD and best_tc:
                row.update({
                    "target_column_name"  : best_tc,
                    "target_column_index" : tgt_index[best_tc],
                    "target_dtype"        : _infer_dtype(tgt_df[best_tc]),
                    "mapping_method"      : f"FUZZY({best_ratio:.2f})",
                    "is_mapped"           : "Y",
                })
                matched_tgt.add(best_tc)

        rows.append(row)

    # Add TARGET_ONLY rows for DBX columns with no SAP counterpart
    for tc in tgt_cols:
        if tc not in matched_tgt:
            rows.append({
                "stream_name"         : stream_name,
                "source_column_name"  : "",
                "source_column_index" : -1,
                "target_column_name"  : tc,
                "target_column_index" : tgt_index[tc],
                "mapping_method"      : "TARGET_ONLY",
                "source_dtype"        : "",
                "target_dtype"        : _infer_dtype(tgt_df[tc]),
                "sap_field_name"      : "",
                "sap_datatype"        : "",
                "is_mapped"           : "N",
                "is_active"           : "Y",
            })

    return pd.DataFrame(rows)


def build_aligned_column_order(
    src_columns: list[str],
    tgt_columns: list[str],
    mapping_df: pd.DataFrame,
) -> list[str]:
    """
    Return the target column list reordered to match the SAP source column order.
    Unmapped target columns are appended at the end.
    """
    confirmed = mapping_df[mapping_df["is_mapped"] == "Y"]
    s2t       = dict(zip(confirmed["source_column_name"], confirmed["target_column_name"]))

    aligned, used = [], set()
    for sc in src_columns:
        tc = s2t.get(sc)
        if tc and tc in tgt_columns:
            aligned.append(tc)
            used.add(tc)

    for tc in tgt_columns:
        if tc not in used:
            aligned.append(tc)

    return aligned


def _infer_dtype(series: pd.Series) -> str:
    """Map a Pandas series dtype to a simple Spark-style type label."""
    d = str(series.dtype)
    if "int"      in d: return "BIGINT"
    if "float"    in d: return "DOUBLE"
    if "datetime" in d: return "TIMESTAMP"
    if "bool"     in d: return "BOOLEAN"
    return "STRING"