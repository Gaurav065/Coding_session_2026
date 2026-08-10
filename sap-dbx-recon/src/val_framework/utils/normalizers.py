"""
normalizers.py
──────────────
Pure-Python value normalization helpers used by all check modules.
No Spark dependency — safe to unit-test locally.

Key concepts:
  - SAP blank  : All-zero string of length >= 4 (e.g. "0000", "00000000")
                 SAP uses these to represent NULL/empty in exports.
  - Leading zeros: SAP numeric IDs often have leading zeros (e.g. "00012")
                   that Databricks strips on load.
  - PK key tuple : Composite primary key serialized as pipe-separated string
                   for fast set operations (src_keys - tgt_keys).
"""

import pandas as pd
from val_framework.core.constants import SAP_BLANK_MIN_LENGTH, DEFAULT_NUMERIC_PRECISION


# ── SAP blank detection ───────────────────────────────────────────────────────

def is_sap_blank(val) -> bool:
    """
    Return True if val is a SAP blank indicator.
    SAP blank = all-zero string with length >= SAP_BLANK_MIN_LENGTH (default 4).
    Examples: "0000", "00000000", "0000000000" → True
              "000", "0001", None, 0 → False
    """
    if val is None or not isinstance(val, str):
        return False
    s = val.strip()
    return len(s) >= SAP_BLANK_MIN_LENGTH and s == "0" * len(s)


# ── Leading zeros ─────────────────────────────────────────────────────────────

def strip_leading_zeros(val) -> str:
    """
    Strip leading zeros from a numeric-looking string.
    Non-numeric strings are returned unchanged.

    "00012" → "12"
    "00012.50" → "12.50"
    "0" → "0"
    "ABC001" → "ABC001"  (non-numeric, unchanged)
    """
    if val is None:
        return ""
    s = str(val).strip()
    if not s:
        return s

    # Pure integer string
    if s.isdigit():
        stripped = s.lstrip("0")
        return stripped if stripped else "0"

    # Try float (handles "00012.50", "-001.5")
    try:
        float(s)
        if "." in s:
            int_part, dec_part = s.split(".", 1)
            int_stripped = int_part.lstrip("0") or "0"
            return f"{int_stripped}.{dec_part}"
        else:
            stripped = s.lstrip("0")
            return stripped if stripped else "0"
    except (ValueError, TypeError):
        return s


# ── PK value normalization ────────────────────────────────────────────────────

def normalize_pk_value(val) -> str:
    """
    Normalize a single primary key column value for join-key matching.

    Handles:
    - NaN/None → ""
    - SAP blanks ("0000", etc.) → ""
    - Trailing timestamps (" 00:00:00") stripped from date strings
    - Leading zeros stripped
    """
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if is_sap_blank(s):
        return ""
    # Strip trailing timestamp suffix common in SAP date exports
    if len(s) >= 19 and s[10:] == " 00:00:00":
        s = s[:10]
    return strip_leading_zeros(s)


def build_pk_key_series(df: pd.DataFrame, pk_cols: list[str]) -> pd.Series:
    """
    Build a normalized composite PK Series for a DataFrame.
    Each row becomes a pipe-separated string of normalized PK values.

    Example: pk_cols=["0CALWEEK","0MATERIAL"]
             row: ("202301", "00000123") → "202301|123"
    """
    parts = [df[col].apply(normalize_pk_value) for col in pk_cols]
    return pd.concat(parts, axis=1).apply(lambda r: "|".join(r.values), axis=1)


# ── Value pair normalization (for cell-by-cell comparison) ───────────────────

def normalize_value_pair(src_val, tgt_val,
                         precision: int = DEFAULT_NUMERIC_PRECISION) -> tuple[str, str]:
    """
    Normalize a (source_value, target_value) pair for comparison.

    Rules applied in order:
    1. SAP blanks → None
    2. Both null → ("NULL", "NULL")  [match]
    3. One null + other is numeric 0 → treat as equal
    4. Both numeric → round to precision, format as string
    5. Both string → strip leading zeros

    Returns a (src_str, tgt_str) tuple ready for direct equality check.
    """
    # Step 1: SAP blank → None
    if isinstance(src_val, str) and is_sap_blank(src_val):
        src_val = None
    if isinstance(tgt_val, str) and is_sap_blank(tgt_val):
        tgt_val = None

    # Step 2: Determine nullness
    def _is_null(v) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            return v.strip().upper() in ("", "NAN", "NONE", "NULL", "<NA>")
        try:
            return pd.isna(v)
        except Exception:
            return False

    src_null = _is_null(src_val)
    tgt_null = _is_null(tgt_val)

    if src_null and tgt_null:
        return "NULL", "NULL"

    # Step 3 & 4: Numeric handling
    def _to_rounded_str(v) -> str | None:
        try:
            n = float(v)
            r = round(n, precision)
            return str(int(r)) if r == int(r) else f"{r:.{precision}f}".rstrip("0").rstrip(".")
        except (ValueError, TypeError):
            return None

    if src_null:
        tgt_s = _to_rounded_str(tgt_val)
        if tgt_s is not None:
            tgt_zero = tgt_s == "0"
            return ("0" if tgt_zero else "NULL"), tgt_s
        return "NULL", str(tgt_val).strip()

    if tgt_null:
        src_s = _to_rounded_str(src_val)
        if src_s is not None:
            src_zero = src_s == "0"
            return src_s, ("0" if src_zero else "NULL")
        return str(src_val).strip(), "NULL"

    src_s = _to_rounded_str(src_val)
    tgt_s = _to_rounded_str(tgt_val)
    if src_s is not None and tgt_s is not None:
        return src_s, tgt_s

    # Step 5: String fallback — strip leading zeros
    return strip_leading_zeros(str(src_val).strip()), strip_leading_zeros(str(tgt_val).strip())