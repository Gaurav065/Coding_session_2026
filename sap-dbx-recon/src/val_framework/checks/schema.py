"""
schema.py
─────────
Check 4 — Data type comparison between SAP and DBX columns.

Uses Spark DataFrame schema (dtypes dict) — no data scan needed,
this is purely a metadata-level check.

Special rule: int→float promotion caused by Spark's handling of
nullable integers (NaN forces upcast to float64) is treated as PASS,
not a mismatch.
"""

import pandas as pd
from pyspark.sql import DataFrame as SDF
from val_framework.core.result import ValidationResult
from val_framework.core.logger import ValidationLogger


def check_data_types(
    sap_sdf: SDF,
    dbx_sdf: SDF,
    mapping_df: pd.DataFrame,
    result: ValidationResult,
    log: ValidationLogger,
) -> None:
    """Check 4 — Column-level data type comparison."""
    try:
        sap_dtypes = dict(sap_sdf.dtypes)
        dbx_dtypes = dict(dbx_sdf.dtypes)

        confirmed  = mapping_df[mapping_df["is_mapped"] == "Y"]
        mismatches = 0

        for _, row in confirmed.iterrows():
            src_col = row["source_column_name"]
            tgt_col = row["target_column_name"]

            if src_col not in sap_dtypes or tgt_col not in dbx_dtypes:
                continue

            src_type = sap_dtypes[src_col]
            tgt_type = dbx_dtypes[tgt_col]

            if src_type == tgt_type:
                status = "PASS"
            else:
                # int → float caused by Spark NaN promotion is acceptable
                nan_promotion = (
                    any(t in src_type for t in ("int", "bigint", "long")) and
                    "double" in tgt_type
                )
                if nan_promotion:
                    status = "PASS"
                else:
                    # Numeric ↔ numeric is a warning, not a fail
                    both_numeric = all(
                        any(t in dt for t in ("int", "long", "double", "float", "decimal"))
                        for dt in (src_type, tgt_type)
                    )
                    status = "WARNING" if both_numeric else "FAIL"
                    mismatches += 1

            result.add_column_result(
                src_col, tgt_col, "data_type_check", status,
                src_type, tgt_type,
            )

        overall = (
            "PASS"    if mismatches == 0 else
            "WARNING" if mismatches < 3  else
            "FAIL"
        )
        result.add_summary(
            "data_type_comparison", "SCHEMA", overall,
            f"{mismatches} type mismatches out of {len(confirmed)} mapped columns",
        )
        log.info(
            f"data_type_comparison: {mismatches} mismatch(es)",
            check_name="data_type_comparison",
        )

    except Exception as e:
        result.add_summary("data_type_comparison", "SCHEMA", "ERROR", str(e))
        log.error("data_type_comparison failed", check_name="data_type_comparison", exc=e)