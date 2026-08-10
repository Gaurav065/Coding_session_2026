"""
data_quality.py
───────────────
Check 6 — Distinct value count comparison per column.
Check 7 — Duplicate row detection in SAP source.
Check 8 — Duplicate row detection in DBX target.

All checks are Spark-native aggregations.
"""

import pandas as pd
from pyspark.sql import DataFrame as SDF
from pyspark.sql import functions as F
from val_framework.core.result import ValidationResult
from val_framework.core.logger import ValidationLogger
from val_framework.core.constants import META_COLUMNS


def check_distinct_counts(
    sap_sdf: SDF,
    dbx_sdf: SDF,
    mapping_df: pd.DataFrame,
    result: ValidationResult,
    log: ValidationLogger,
) -> None:
    """
    Check 6 — Compare distinct value counts per mapped column.
    Uses Spark approxCountDistinct for large tables (exact for small ones).
    """
    try:
        confirmed = mapping_df[mapping_df["is_mapped"] == "Y"]
        issues    = 0

        for _, row in confirmed.iterrows():
            src_col = row["source_column_name"]
            tgt_col = row["target_column_name"]

            if src_col not in sap_sdf.columns or tgt_col not in dbx_sdf.columns:
                continue

            src_d = sap_sdf.select(F.countDistinct(F.col(src_col))).collect()[0][0]
            tgt_d = dbx_sdf.select(F.countDistinct(F.col(tgt_col))).collect()[0][0]
            diff  = abs(src_d - tgt_d)

            if diff == 0:
                status = "PASS"
            elif diff <= 3:
                status  = "WARNING"
                issues += 1
            else:
                status  = "FAIL"
                issues += 1

            result.add_column_result(
                src_col, tgt_col, "distinct_count", status,
                str(src_d), str(tgt_d), str(diff),
            )

        overall = "PASS" if issues == 0 else "WARNING"
        result.add_summary(
            "distinct_count_comparison", "DATA_QUALITY", overall,
            f"{issues} column(s) with distinct count differences",
        )
        log.info(
            f"distinct_count_comparison: {issues} issue(s)",
            check_name="distinct_count_comparison",
        )

    except Exception as e:
        result.add_summary("distinct_count_comparison", "DATA_QUALITY", "ERROR", str(e))
        log.error("distinct_count_comparison failed",
                  check_name="distinct_count_comparison", exc=e)


def check_duplicates(
    sap_sdf: SDF,
    dbx_sdf: SDF,
    result: ValidationResult,
    log: ValidationLogger,
) -> None:
    """
    Checks 7 & 8 — Duplicate row detection.
    Compares total row count vs distinct row count (excluding meta columns).
    """
    try:
        for label, sdf, check_name in [
            ("SAP source", sap_sdf, "source_duplicates"),
            ("DBX target", dbx_sdf, "target_duplicates"),
        ]:
            data_cols = [c for c in sdf.columns if c not in META_COLUMNS]
            total     = sdf.count()
            distinct  = sdf.select(data_cols).distinct().count()
            dup_count = total - distinct

            status = "PASS" if dup_count == 0 else "WARNING"
            result.add_summary(
                check_name, "DATA_QUALITY", status,
                f"{label} duplicate rows: {dup_count:,} "
                f"(total={total:,}, distinct={distinct:,})",
                str(dup_count), "",
            )
            log.info(
                f"{check_name}: {dup_count:,} duplicates",
                check_name=check_name,
            )

    except Exception as e:
        result.add_summary("duplicates", "DATA_QUALITY", "ERROR", str(e))
        log.error("duplicate check failed", check_name="duplicates", exc=e)