"""
key_validation.py
─────────────────
Check 10 — SAP − DBX   : rows in SAP missing from Databricks
Check 11 — DBX − SAP   : orphan rows in Databricks not in SAP
Check 12 — PK issue summary: MISSING_IN_DBX, MISSING_IN_SAP, DATA_MISMATCH

All three checks are Spark-native FULL OUTER JOIN + EXCEPT operations.
No toPandas() row-by-row loops.

skip_columns parameter
──────────────────────
Pass a list of SAP column names (e.g. timestamp/date columns) that should be
excluded from value-level comparison inside check_pk_issue_summary(). Those
columns are still loaded and available in the DataFrames — they are simply not
evaluated for DATA_MISMATCH. This is driven by the exclude_columns field stored
in the stream config JSON.
"""

import re as _re

import pandas as pd
from pyspark.sql import DataFrame as SDF
from pyspark.sql import functions as F
from pyspark.sql.window import Window

from val_framework.core.constants import (
    COLUMN_MISMATCH_MAX_ROWS_PER_COL,
    COLUMN_MISMATCH_MAX_TOTAL,
    DEFAULT_NUMERIC_PRECISION,
    PK_ISSUE_MAX_RECORDS,
)
from val_framework.core.logger import ValidationLogger
from val_framework.core.result import ValidationResult


# ── Shared helpers ────────────────────────────────────────────────────────────

def _build_pk_sdf(sdf: SDF, pk_cols: list[str]) -> SDF:
    """Return a single-column SDF of pipe-joined, normalized PK strings."""
    concat_expr = F.concat_ws(
        "|",
        *[F.coalesce(F.col(c).cast("string"), F.lit("")) for c in pk_cols],
    )
    return sdf.select(concat_expr.alias("__pk__"))


def _resolve_pk_cols(
    mapping_df: pd.DataFrame,
    pk_columns: list[str],
    sap_cols: list,
    dbx_cols: list,
) -> tuple[list, list]:
    """Return (src_pk, tgt_pk) after validating PKs exist in both DataFrames."""
    confirmed = mapping_df[mapping_df["is_mapped"] == "Y"]
    s2t       = dict(zip(confirmed["source_column_name"], confirmed["target_column_name"]))
    src_pk, tgt_pk = [], []
    for pk in pk_columns:
        pk  = pk.strip()
        tgt = s2t.get(pk)
        if pk in sap_cols and tgt and tgt in dbx_cols:
            src_pk.append(pk)
            tgt_pk.append(tgt)
    return src_pk, tgt_pk


# ── Check 10: SAP − DBX ───────────────────────────────────────────────────────

def check_sap_minus_dbx(
    sap_sdf: SDF,
    dbx_sdf: SDF,
    mapping_df: pd.DataFrame,
    pk_columns: list[str],
    result: ValidationResult,
    log: ValidationLogger,
    skip_columns: list[str] | None = None,
) -> tuple[int, SDF | None]:
    """Records present in SAP but missing in Databricks (PK-set EXCEPT)."""
    if not pk_columns:
        result.add_summary("sap_minus_dbx", "KEY_VALIDATION", "SKIP",
                           "No primary key columns configured.")
        return 0, None

    try:
        src_pk, tgt_pk = _resolve_pk_cols(
            mapping_df, pk_columns, sap_sdf.columns, dbx_sdf.columns
        )
        if not src_pk:
            result.add_summary("sap_minus_dbx", "KEY_VALIDATION", "SKIP",
                               f"PK columns {pk_columns} not found in both datasets.")
            return 0, None

        sap_keys = _build_pk_sdf(sap_sdf, src_pk).distinct()
        dbx_keys = _build_pk_sdf(dbx_sdf, tgt_pk).distinct()
        missing  = sap_keys.exceptAll(dbx_keys)
        miss_cnt = missing.count()
        total    = sap_keys.count()

        if miss_cnt == 0:
            result.add_summary(
                "sap_minus_dbx", "KEY_VALIDATION", "PASS",
                f"All {total:,} SAP PKs found in DBX. PK: {src_pk}",
                str(total), "0",
            )
        else:
            pct    = (miss_cnt / max(total, 1)) * 100
            status = "FAIL" if pct > 5 else "WARNING"
            result.add_summary(
                "sap_minus_dbx", "KEY_VALIDATION", status,
                f"{miss_cnt:,} SAP records missing in DBX ({pct:.2f}%)",
                str(total), str(miss_cnt),
            )

        missing_sdf = sap_sdf.join(
            missing.withColumnRenamed("__pk__", "__pk_miss__"),
            on=(
                F.concat_ws("|", *[F.coalesce(F.col(c).cast("string"), F.lit(""))
                                    for c in src_pk])
                == F.col("__pk_miss__")
            ),
            how="inner",
        ).drop("__pk_miss__")

        log.info(f"sap_minus_dbx: {miss_cnt:,} missing", check_name="sap_minus_dbx")
        return miss_cnt, missing_sdf

    except Exception as e:
        result.add_summary("sap_minus_dbx", "KEY_VALIDATION", "ERROR", str(e))
        log.error("sap_minus_dbx failed", check_name="sap_minus_dbx", exc=e)
        return 0, None


# ── Check 11: DBX − SAP ───────────────────────────────────────────────────────

def check_dbx_minus_sap(
    sap_sdf: SDF,
    dbx_sdf: SDF,
    mapping_df: pd.DataFrame,
    pk_columns: list[str],
    result: ValidationResult,
    log: ValidationLogger,
    skip_columns: list[str] | None = None,
) -> tuple[int, SDF | None]:
    """Orphan records in Databricks not found in SAP (PK-set EXCEPT)."""
    if not pk_columns:
        result.add_summary("dbx_minus_sap", "KEY_VALIDATION", "SKIP",
                           "No primary key columns configured.")
        return 0, None

    try:
        src_pk, tgt_pk = _resolve_pk_cols(
            mapping_df, pk_columns, sap_sdf.columns, dbx_sdf.columns
        )
        if not src_pk:
            result.add_summary("dbx_minus_sap", "KEY_VALIDATION", "SKIP",
                               f"PK columns {pk_columns} not found in both datasets.")
            return 0, None

        sap_keys = _build_pk_sdf(sap_sdf, src_pk).distinct()
        dbx_keys = _build_pk_sdf(dbx_sdf, tgt_pk).distinct()
        orphans  = dbx_keys.exceptAll(sap_keys)
        orph_cnt = orphans.count()
        total    = dbx_keys.count()

        if orph_cnt == 0:
            result.add_summary(
                "dbx_minus_sap", "KEY_VALIDATION", "PASS",
                f"No orphans. All {total:,} DBX PKs found in SAP.",
                "0", str(total),
            )
        else:
            pct    = (orph_cnt / max(total, 1)) * 100
            status = "FAIL" if pct > 5 else "WARNING"
            result.add_summary(
                "dbx_minus_sap", "KEY_VALIDATION", status,
                f"{orph_cnt:,} orphan records in DBX ({pct:.2f}%)",
                str(orph_cnt), str(total),
            )

        orphan_sdf = dbx_sdf.join(
            orphans.withColumnRenamed("__pk__", "__pk_orp__"),
            on=(
                F.concat_ws("|", *[F.coalesce(F.col(c).cast("string"), F.lit(""))
                                    for c in tgt_pk])
                == F.col("__pk_orp__")
            ),
            how="inner",
        ).drop("__pk_orp__")

        log.info(f"dbx_minus_sap: {orph_cnt:,} orphans", check_name="dbx_minus_sap")
        return orph_cnt, orphan_sdf

    except Exception as e:
        result.add_summary("dbx_minus_sap", "KEY_VALIDATION", "ERROR", str(e))
        log.error("dbx_minus_sap failed", check_name="dbx_minus_sap", exc=e)
        return 0, None


# ── Check 12: PK Issue Summary ────────────────────────────────────────────────

def check_pk_issue_summary(
    sap_sdf: SDF,
    dbx_sdf: SDF,
    mapping_df: pd.DataFrame,
    pk_columns: list[str],
    result: ValidationResult,
    log: ValidationLogger,
    precision: int = DEFAULT_NUMERIC_PRECISION,
    max_records: int = PK_ISSUE_MAX_RECORDS,
    skip_columns: list[str] | None = None,
) -> None:
    """
    Full PK-level audit via Spark FULL OUTER JOIN:
      - MISSING_IN_DBX  : PK in SAP, not in DBX
      - MISSING_IN_SAP  : PK in DBX, not in SAP
      - DATA_MISMATCH   : Same PK, at least one value column differs

    skip_columns : SAP column names to exclude from value comparison.
                   Useful for date/timestamp columns whose string representation
                   may differ between systems without being a real data issue.
                   Driven by the exclude_columns field in the stream config.
    """
    if not pk_columns:
        result.add_summary("pk_issue_summary", "KEY_VALIDATION", "SKIP",
                           "No primary key columns configured.")
        return

    try:
        src_pk, tgt_pk = _resolve_pk_cols(
            mapping_df, pk_columns, sap_sdf.columns, dbx_sdf.columns
        )
        if not src_pk:
            result.add_summary("pk_issue_summary", "KEY_VALIDATION", "SKIP",
                               f"PK columns {pk_columns} not resolved.")
            return

        _skip = set(skip_columns or [])

        # Confirmed (non-fuzzy) mappings only
        confirmed = mapping_df[
            (mapping_df["is_mapped"] == "Y") &
            (~mapping_df["mapping_method"].str.startswith("FUZZY", na=False))
        ]
        s2t = dict(zip(confirmed["source_column_name"], confirmed["target_column_name"]))

        # Non-PK value columns, excluding any in skip_columns
        val_pairs = [
            (sc, s2t[sc])
            for sc in confirmed["source_column_name"]
            if sc not in src_pk
            and sc not in _skip
            and sc in sap_sdf.columns
            and s2t.get(sc) in dbx_sdf.columns
        ]

        if _skip:
            log.info(
                f"pk_issue_summary: skipping {sorted(_skip)} from value comparison",
                check_name="pk_issue_summary",
            )

        # Build PK concat column on both sides
        sap_keyed = sap_sdf.withColumn(
            "__pk__",
            F.concat_ws("|", *[F.coalesce(F.col(c).cast("string"), F.lit(""))
                                for c in src_pk]),
        )
        dbx_keyed = dbx_sdf.withColumn(
            "__pk__",
            F.concat_ws("|", *[F.coalesce(F.col(c).cast("string"), F.lit(""))
                                for c in tgt_pk]),
        )

        # De-duplicate on PK (take first row per PK)
        win       = Window.partitionBy("__pk__").orderBy("__pk__")
        sap_dedup = sap_keyed.withColumn("_rn", F.row_number().over(win)).filter("_rn=1").drop("_rn")
        dbx_dedup = dbx_keyed.withColumn("_rn", F.row_number().over(win)).filter("_rn=1").drop("_rn")

        # Full outer join on PK
        joined = sap_dedup.alias("s").join(
            dbx_dedup.select(
                F.col("__pk__").alias("__pk_d__"),
                *[F.col(tc).alias(f"__d_{sc}__") for sc, tc in val_pairs],
            ).alias("d"),
            on=F.col("s.__pk__") == F.col("__pk_d__"),
            how="full_outer",
        )

        # Build per-column mismatch flags
        sap_dtypes     = dict(sap_sdf.dtypes)
        mismatch_flags = []

        for sc, _ in val_pairs:
            dt         = sap_dtypes.get(sc, "string").lower()
            is_numeric = any(
                t in dt for t in ("int", "long", "double", "float", "decimal", "short", "byte")
            )

            if is_numeric:
                cond = (
                    F.round(F.col(f"s.{sc}").cast("double"), precision) !=
                    F.round(F.col(f"__d_{sc}__").cast("double"), precision)
                )
            else:
                # Two-pass Unicode/control-character normalisation before comparing
                sap_str   = F.coalesce(F.col(f"s.{sc}").cast("string"),  F.lit(""))
                dbx_str   = F.coalesce(F.col(f"__d_{sc}__").cast("string"), F.lit(""))
                sap_clean = F.regexp_replace(
                    F.regexp_replace(sap_str, r"[^\x20-\x7E]", "?"),
                    r"[\x00-\x1F]", " ",
                )
                dbx_clean = F.regexp_replace(
                    F.regexp_replace(dbx_str, r"[^\x20-\x7E]", "?"),
                    r"[\x00-\x1F]", " ",
                )
                cond = sap_clean != dbx_clean

            mismatch_flags.append(
                F.when(cond, F.lit(sc)).otherwise(F.lit(None)).alias(f"_mm_{sc}")
            )

        issue_sdf = (
            joined
            .select(
                F.col("s.__pk__").alias("__pk__"),
                F.col("__pk_d__"),
                *mismatch_flags,
            )
            .withColumn(
                "issue_type",
                F.when(F.col("__pk__").isNull(),   F.lit("MISSING_IN_SAP"))
                 .when(F.col("__pk_d__").isNull(), F.lit("MISSING_IN_DBX"))
                 .otherwise(F.lit("DATA_MISMATCH")),
            )
            .withColumn(
                "mismatched_cols",
                F.concat_ws(",", *[F.col(f"_mm_{sc}") for sc, _ in val_pairs]),
            )
            .filter(
                F.col("issue_type").isin("MISSING_IN_SAP", "MISSING_IN_DBX") |
                (
                    (F.col("issue_type") == "DATA_MISMATCH") &
                    (F.col("mismatched_cols") != "")
                )
            )
        )

        counts = {
            row["issue_type"]: row["cnt"]
            for row in issue_sdf
            .groupBy("issue_type")
            .agg(F.count("*").alias("cnt"))
            .collect()
        }
        total_issues = sum(counts.values())

        if total_issues == 0:
            result.add_summary("pk_issue_summary", "KEY_VALIDATION", "PASS",
                               "All PKs clean — no missing or mismatched rows.")
        else:
            detail = (
                f"{total_issues:,} PK issues — "
                f"MISSING_IN_DBX={counts.get('MISSING_IN_DBX', 0):,}, "
                f"MISSING_IN_SAP={counts.get('MISSING_IN_SAP', 0):,}, "
                f"DATA_MISMATCH={counts.get('DATA_MISMATCH', 0):,}"
            )
            result.add_summary("pk_issue_summary", "KEY_VALIDATION", "FAIL", detail)

        # Collect sample rows for result logging (capped at max_records)
        for row in (
            issue_sdf
            .select(
                "issue_type",
                F.coalesce(F.col("__pk__"), F.col("__pk_d__")).alias("pk_val"),
                "mismatched_cols",
            )
            .limit(max_records)
            .collect()
        ):
            result.add_pk_issue(
                row["issue_type"],
                row["pk_val"] or "",
                row["mismatched_cols"] or "-",
                f"{row['issue_type']} for PK: {row['pk_val']}",
            )

        log.info(f"pk_issue_summary: {total_issues:,} issues", check_name="pk_issue_summary")

        # ── Column mismatch drill-down ─────────────────────────────────────────
        if val_pairs and counts.get("DATA_MISMATCH", 0) > 0:
            try:
                safe = lambda s: _re.sub(r"[^\w]", "_", s)

                col_select = [
                    F.coalesce(F.col("s.__pk__"), F.col("__pk_d__")).alias("__pk_val__"),
                    *[F.col(f"s.{sc}").cast("string").alias(f"sap_{safe(sc)}")
                      for sc, _ in val_pairs],
                    *[F.col(f"__d_{sc}__").cast("string").alias(f"dbx_{safe(sc)}")
                      for sc, _ in val_pairs],
                ]

                detail_rows = (
                    joined
                    .filter(
                        F.col("s.__pk__").isNotNull() &
                        F.col("__pk_d__").isNotNull()
                    )
                    .select(*col_select)
                    .limit(COLUMN_MISMATCH_MAX_TOTAL)
                    .collect()
                )

                per_col_count: dict[str, int] = {}

                for row in detail_rows:
                    pk_val = row["__pk_val__"] or ""
                    for sc, _ in val_pairs:
                        sap_v = row[f"sap_{safe(sc)}"] or ""
                        dbx_v = row[f"dbx_{safe(sc)}"] or ""

                        try:
                            sap_n = str(round(float(sap_v), precision)) if sap_v else ""
                            dbx_n = str(round(float(dbx_v), precision)) if dbx_v else ""
                        except (ValueError, TypeError):
                            sap_n, dbx_n = sap_v.strip(), dbx_v.strip()

                        if sap_n != dbx_n:
                            cnt = per_col_count.get(sc, 0)
                            per_col_count[sc] = cnt + 1
                            if cnt < COLUMN_MISMATCH_MAX_ROWS_PER_COL:
                                result.add_column_mismatch(sc, pk_val, sap_v, dbx_v)

                if per_col_count:
                    log.info(
                        f"Column mismatch detail: {len(per_col_count)} columns, "
                        f"{sum(per_col_count.values())} total mismatched cells",
                        check_name="pk_issue_summary",
                    )

            except Exception as cm_err:
                log.warning(
                    f"Column mismatch drill-down skipped: {cm_err}",
                    check_name="pk_issue_summary",
                )

    except Exception as e:
        result.add_summary("pk_issue_summary", "KEY_VALIDATION", "ERROR", str(e))
        log.error("pk_issue_summary failed", check_name="pk_issue_summary", exc=e)
