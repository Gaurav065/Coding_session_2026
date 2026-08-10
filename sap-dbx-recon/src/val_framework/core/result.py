"""
result.py
─────────
ValidationResult: in-memory collector for all check outputs
during a single validation run. Flushed to Delta at the end
via save_results() in the loaders module.
"""

from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Collects all validation results for one run across all check types."""

    run_id       : str
    stream_name  : str
    source_file  : str
    target_file  : str

    # Row buffers — one list per result output
    summary_rows          : list = field(default_factory=list)
    column_rows           : list = field(default_factory=list)
    pk_issue_rows         : list = field(default_factory=list)
    key_mismatch_rows     : list = field(default_factory=list)
    excluded_column_rows  : list = field(default_factory=list)
    minus_result_rows     : list = field(default_factory=list)
    # Column mismatch drill-down: actual SAP vs DBX values per mismatched column.
    # Written to column_mismatches/<col_name>.json by the exporter.
    column_mismatch_rows  : list = field(default_factory=list)

    _ts : datetime = field(default_factory=datetime.now, init=False, repr=False)

    # ── Summary (one row per check) ───────────────────────────────────────────
    def add_summary(self, check_name: str, category: str, status: str,
                    details: str, src_val: str = "", tgt_val: str = "") -> None:
        self.summary_rows.append({
            "run_id"         : self.run_id,
            "stream_name"    : self.stream_name,
            "source_file"    : self.source_file,
            "target_file"    : self.target_file,
            "check_name"     : check_name,
            "check_category" : category,
            "status"         : status,
            "details"        : str(details)[:2000],
            "source_value"   : str(src_val)[:500],
            "target_value"   : str(tgt_val)[:500],
            "created_ts"     : self._ts,
        })

    # ── Column-level (one row per column per check) ───────────────────────────
    def add_column_result(self, src_col: str, tgt_col: str, check_name: str,
                          status: str, src_val: str = "", tgt_val: str = "",
                          diff: str = "") -> None:
        self.column_rows.append({
            "run_id"          : self.run_id,
            "stream_name"     : self.stream_name,
            "source_column"   : str(src_col),
            "target_column"   : str(tgt_col),
            "check_name"      : check_name,
            "status"          : status,
            "source_value"    : str(src_val)[:500],
            "target_value"    : str(tgt_val)[:500],
            "difference"      : str(diff)[:500],
            "created_ts"      : self._ts,
        })

    # ── PK issue summary (MISSING_IN_DBX / MISSING_IN_SAP / DATA_MISMATCH) ───
    def add_pk_issue(self, issue_type: str, pk_values: str,
                     mismatched_columns: str, details: str) -> None:
        self.pk_issue_rows.append({
            "run_id"              : self.run_id,
            "stream_name"         : self.stream_name,
            "issue_type"          : issue_type,
            "primary_key_values"  : str(pk_values)[:500],
            "mismatched_columns"  : str(mismatched_columns)[:1000],
            "details"             : str(details)[:2000],
            "created_ts"          : self._ts,
        })

    # ── Key mismatches (SAP−DBX and DBX−SAP direction rows) ──────────────────
    def add_key_mismatch(self, check_type: str, pk_values: str,
                         column_name: str, src_val: str,
                         tgt_val: str, details: str = "") -> None:
        self.key_mismatch_rows.append({
            "run_id"             : self.run_id,
            "stream_name"        : self.stream_name,
            "check_type"         : check_type,   # 'SAP_MINUS_DBX' | 'DBX_MINUS_SAP'
            "primary_key_values" : str(pk_values)[:500],
            "column_name"        : str(column_name),
            "source_value"       : str(src_val)[:500],
            "target_value"       : str(tgt_val)[:500],
            "details"            : str(details)[:2000],
            "created_ts"         : self._ts,
        })

    # ── Excluded columns audit ────────────────────────────────────────────────
    def add_excluded_column(self, column_name: str,
                            exclusion_source: str, reason: str) -> None:
        self.excluded_column_rows.append({
            "run_id"           : self.run_id,
            "stream_name"      : self.stream_name,
            "column_name"      : str(column_name),
            "exclusion_source" : exclusion_source,  # 'META_SYSTEM' | 'USER_CONFIG' | 'UNMAPPED'
            "reason"           : str(reason)[:500],
            "created_ts"       : self._ts,
        })

    # ── MINUS query result rows ───────────────────────────────────────────────
    def add_minus_result(self, direction: str, row_data: str) -> None:
        self.minus_result_rows.append({
            "run_id"      : self.run_id,
            "stream_name" : self.stream_name,
            "direction"   : direction,         # 'SAP_MINUS_DBX' | 'DBX_MINUS_SAP'
            "row_data"    : str(row_data)[:4000],
            "created_ts"  : self._ts,
        })

    # ── Column mismatch drill-down (one row per mismatched cell) ─────────────
    def add_column_mismatch(self, column_name: str, pk_values: str,
                            sap_value: str, dbx_value: str) -> None:
        """
        Record a single cell-level mismatch for a DATA_MISMATCH PK row.
        Grouped by column_name in the exporter → column_mismatches/<col>.json.
        """
        self.column_mismatch_rows.append({
            "run_id"       : self.run_id,
            "stream_name"  : self.stream_name,
            "column_name"  : str(column_name),
            "pk_values"    : str(pk_values)[:500],
            "sap_value"    : str(sap_value)[:500],
            "dbx_value"    : str(dbx_value)[:500],
            "created_ts"   : self._ts,
        })

    # ── Overall status ────────────────────────────────────────────────────────
    def get_overall_status(self) -> str:
        statuses = {r["status"] for r in self.summary_rows}
        if "FAIL" in statuses:
            return "FAILED"
        if "WARNING" in statuses:
            return "PASSED_WITH_WARNINGS"
        if "ERROR" in statuses:
            return "ERROR"
        return "PASSED"

    # ── Counts helper (for logging) ───────────────────────────────────────────
    def counts(self) -> dict:
        from collections import Counter
        c = Counter(r["status"] for r in self.summary_rows)
        return {
            "total"   : len(self.summary_rows),
            "pass"    : c.get("PASS", 0),
            "warning" : c.get("WARNING", 0),
            "fail"    : c.get("FAIL", 0),
            "skip"    : c.get("SKIP", 0),
            "error"   : c.get("ERROR", 0),
        }