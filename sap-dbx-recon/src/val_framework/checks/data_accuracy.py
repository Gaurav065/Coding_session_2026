"""
data_accuracy.py
────────────────
Check 5 — Numeric aggregate SUM comparison (pure Spark, no toPandas).
Check 9 — Hash / PK-set comparison (pure Spark set operations).

Both checks operate entirely on Spark DataFrames so they scale to
any table size without driver OOM risk.

skip_columns parameter
──────────────────────
Pass a list of SAP column names to exclude from the numeric aggregate check.
Useful for date/timestamp columns stored as numeric epoch values that should
not be summed. Driven by the exclude_columns field in the stream config.
"""

import pandas as pd
from pyspark.sql import DataFrame as SDF
from pyspark.sql import functions as F
from val_framework.core.result import ValidationResult
from val_framework.core.logger import ValidationLogger
from val_framework.core.constants import DEFAULT_NUMERIC_PRECISION, DEFAULT_TOLERANCE_PCT


# ── Check 5: Numeric Aggregates ───────────────────────────────────────────────

def check_numeric_aggregates(
    sap_sdf: SDF,
    dbx_sdf: SDF,
    mapping_df: pd.DataFrame,
    result: ValidationResult,
    log: ValidationLogger,
    precision: int = DEFAULT_NUMERIC_PRECISION,
    tolerance_pct: float = DEFAULT_TOLERANCE_PCT,
    skip_columns: list[str] | None = None,
) -> None:
    """
    Compare SUM aggregates for every mapped numeric column.
    Fully Spark-native — no toPandas(), no driver memory pressure.
    FUZZY-mapped columns are SKIPPED (they may be silently mismapped).

    skip_columns : SAP column names to exclude from SUM comparison (e.g. epoch
                   timestamps stored as numbers that should not be aggregated).
    """
    _skip = set(skip_columns or [])

    try:
        # Only confirmed mappings (not FUZZY, not UNMAPPED)
        confirmed = mapping_df[
            (mapping_df["is_mapped"] == "Y") &
            (~mapping_df["mapping_method"].str.startswith("FUZZY", na=False))
        ]

        issues = 0
        for _, row in confirmed.iterrows():
            src_col = row["source_column_name"]
            tgt_col = row["target_column_name"]

            if src_col in _skip:
                continue

            if src_col not in sap_sdf.columns or tgt_col not in dbx_sdf.columns:
                continue

            # Check if source column is numeric
            src_dtype = dict(sap_sdf.dtypes).get(src_col, "string")
            if not any(t in src_dtype for t in ("int", "long", "double", "float", "decimal")):
                continue

            tgt_dtype = dict(dbx_sdf.dtypes).get(tgt_col, "string")
            if not any(t in tgt_dtype for t in ("int", "long", "double", "float", "decimal")):
                result.add_column_result(src_col, tgt_col, "aggregate_sum", "WARNING",
                                         src_dtype, tgt_dtype, "type mismatch")
                continue

            # Compute SUM on cluster — single .collect() per column
            src_sum = (
                sap_sdf
                .select(F.round(
                    F.sum(F.coalesce(F.col(src_col).cast("double"), F.lit(0.0))),
                    precision
                ).alias("s"))
                .collect()[0]["s"] or 0.0
            )
            tgt_sum = (
                dbx_sdf
                .select(F.round(
                    F.sum(F.coalesce(F.col(tgt_col).cast("double"), F.lit(0.0))),
                    precision
                ).alias("s"))
                .collect()[0]["s"] or 0.0
            )

            src_sum = round(float(src_sum), precision)
            tgt_sum = round(float(tgt_sum), precision)

            if src_sum == 0.0 and tgt_sum == 0.0:
                diff_pct = 0.0
            elif src_sum == 0.0:
                diff_pct = 100.0
            else:
                diff_pct = abs((src_sum - tgt_sum) / src_sum) * 100

            if diff_pct == 0.0:
                status = "PASS"
            elif diff_pct <= tolerance_pct:
                status = "WARNING"
                issues += 1
            else:
                status = "FAIL"
                issues += 1

            result.add_column_result(src_col, tgt_col, "aggregate_sum", status,
                                     str(src_sum), str(tgt_sum), f"{diff_pct:.4f}%")

        overall = "PASS" if issues == 0 else ("WARNING" if issues < 5 else "FAIL")
        result.add_summary(
            "numeric_aggregates", "DATA_ACCURACY", overall,
            f"{issues} SUM mismatches (tolerance: {tolerance_pct}%, precision: {precision})"
        )
        log.info(f"numeric_aggregates: {issues} issue(s)", check_name="numeric_aggregates")

    except Exception as e:
        result.add_summary("numeric_aggregates", "DATA_ACCURACY", "ERROR", str(e))
        log.error("numeric_aggregates check failed", check_name="numeric_aggregates", exc=e)


# ── Check 9: Hash / PK-set comparison ────────────────────────────────────────

def check_hash_comparison(sap_sdf: SDF, dbx_sdf: SDF,
                          mapping_df: pd.DataFrame,
                          pk_columns: list[str],
                          result: ValidationResult,
                          log: ValidationLogger,
                          precision: int = DEFAULT_NUMERIC_PRECISION) -> None:
    """
    PK-set comparison using Spark EXCEPT (not Python sets — no driver OOM).
    Counts how many PK tuples exist in SAP only, DBX only, or both.
    """
    if not pk_columns:
        result.add_summary("hash_comparison", "DATA_ACCURACY", "SKIP",
                           "No primary key columns configured.")
        return

    try:
        confirmed = mapping_df[mapping_df["is_mapped"] == "Y"]
        s2t       = dict(zip(confirmed["source_column_name"], confirmed["target_column_name"]))

        src_pk_cols = [pk for pk in pk_columns if pk in sap_sdf.columns and s2t.get(pk) in dbx_sdf.columns]
        tgt_pk_cols = [s2t[pk] for pk in src_pk_cols]

        if not src_pk_cols:
            result.add_summary("hash_comparison", "DATA_ACCURACY", "SKIP",
                               f"PK columns {pk_columns} not found in both datasets.")
            return

        # Build normalized PK concat column on both sides
        def _pk_concat(sdf: SDF, cols: list[str]) -> SDF:
            concat_expr = F.concat_ws(
                "|",
                *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in cols]
            )
            return sdf.select(concat_expr.alias("__pk__")).distinct()

        sap_keys = _pk_concat(sap_sdf, src_pk_cols)
        dbx_keys = _pk_concat(dbx_sdf, tgt_pk_cols)

        sap_only  = sap_keys.exceptAll(dbx_keys).count()
        dbx_only  = dbx_keys.exceptAll(sap_keys).count()
        common    = sap_keys.intersect(dbx_keys).count()
        total     = max(common + sap_only, 1)
        match_pct = (common / total) * 100

        status = (
            "PASS"    if sap_only == 0 and dbx_only == 0 else
            "WARNING" if match_pct >= 95                  else
            "FAIL"
        )
        pk_str = ", ".join(src_pk_cols)
        detail = (
            f"PK set ({len(src_pk_cols)} cols: {pk_str[:60]}): "
            f"Common={common:,}, SAP-only={sap_only:,}, "
            f"DBX-only={dbx_only:,}, Match={match_pct:.2f}%"
        )
        result.add_summary("hash_comparison", "DATA_ACCURACY", status, detail,
                           str(common + sap_only), str(common + dbx_only))
        log.info(detail, check_name="hash_comparison")

    except Exception as e:
        result.add_summary("hash_comparison", "DATA_ACCURACY", "ERROR", str(e))
        log.error("hash_comparison check failed", check_name="hash_comparison", exc=e)