"""
structural.py
─────────────
Checks 1, 2, 3: Row count, column count, mapping coverage.
All checks operate on Spark DataFrames — no toPandas() here.
"""

import pandas as pd
from pyspark.sql import DataFrame as SDF
from val_framework.core.result import ValidationResult
from val_framework.core.logger import ValidationLogger


def check_row_count(sap_sdf: SDF, dbx_sdf: SDF,
                    result: ValidationResult, log: ValidationLogger) -> None:
    """Check 1 — Row count comparison."""
    try:
        src_count = sap_sdf.count()
        tgt_count = dbx_sdf.count()
        diff      = abs(src_count - tgt_count)

        if src_count == tgt_count:
            status = "PASS"
            detail = f"Row counts match: {src_count:,}"
        else:
            pct    = (diff / max(src_count, 1)) * 100
            status = "FAIL" if pct > 5 else "WARNING"
            detail = (
                f"Row count mismatch: SAP={src_count:,}, "
                f"DBX={tgt_count:,}, diff={diff:,} ({pct:.2f}%)"
            )

        result.add_summary("row_count", "STRUCTURE", status, detail,
                           str(src_count), str(tgt_count))
        log.info(detail, check_name="row_count")

    except Exception as e:
        result.add_summary("row_count", "STRUCTURE", "ERROR", str(e))
        log.error("row_count check failed", check_name="row_count", exc=e)


def check_column_structure(sap_sdf: SDF, dbx_sdf: SDF,
                           mapping_df: pd.DataFrame,
                           result: ValidationResult,
                           log: ValidationLogger) -> None:
    """Check 2 — Column count. Check 3 — Mapping coverage."""
    try:
        # Exclude meta columns from count
        from val_framework.core.constants import META_COLUMNS
        src_cols = [c for c in sap_sdf.columns if c not in META_COLUMNS]
        tgt_cols = [c for c in dbx_sdf.columns if c not in META_COLUMNS]

        # Check 2: column count
        if len(src_cols) == len(tgt_cols):
            result.add_summary("column_count", "STRUCTURE", "PASS",
                               f"Column counts match: {len(src_cols)}",
                               str(len(src_cols)), str(len(tgt_cols)))
        else:
            result.add_summary("column_count", "STRUCTURE", "WARNING",
                               f"Column count: SAP={len(src_cols)}, DBX={len(tgt_cols)}",
                               str(len(src_cols)), str(len(tgt_cols)))

        # Check 3: mapping coverage
        mapped      = mapping_df[mapping_df["is_mapped"] == "Y"]
        unmapped    = mapping_df[mapping_df["mapping_method"] == "UNMAPPED"]
        fuzzy_unconfirmed = mapping_df[
            mapping_df["mapping_method"].str.startswith("FUZZY", na=False)
        ]
        tgt_only    = mapping_df[mapping_df["mapping_method"] == "TARGET_ONLY"]

        cov_status  = "PASS" if len(unmapped) == 0 else "WARNING"
        cov_detail  = (
            f"Mapped: {len(mapped)}, Unmapped(src): {len(unmapped)}, "
            f"Fuzzy(unconfirmed): {len(fuzzy_unconfirmed)}, Target-only: {len(tgt_only)}"
        )
        result.add_summary("mapping_coverage", "STRUCTURE", cov_status, cov_detail,
                           str(len(mapped)), str(len(unmapped)))

        # Flag each fuzzy mapping as a WARNING column result (don't silently use it)
        for _, row in fuzzy_unconfirmed.iterrows():
            result.add_column_result(
                row["source_column_name"], row.get("target_column_name", ""),
                "mapping_coverage", "WARNING",
                row["mapping_method"], "",
                "FUZZY mapping — excluded from accuracy checks until confirmed",
            )

        log.info(cov_detail, check_name="mapping_coverage")

    except Exception as e:
        result.add_summary("mapping_coverage", "STRUCTURE", "ERROR", str(e))
        log.error("column_structure check failed", check_name="column_structure", exc=e)