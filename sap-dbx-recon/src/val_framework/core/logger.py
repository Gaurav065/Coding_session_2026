"""
logger.py
─────────
ValidationLogger: structured JSON logger that captures the exact
module, function, and line number of every log call — whether the
code is running from a notebook or from the compiled .so library.

Writes to:
  1. Python's stdlib logging (→ Databricks notebook stdout/stderr)
  2. In-memory buffer → flushed to Delta table at end of run

Usage:
    log = ValidationLogger(run_id, stream_name, spark)
    log.info("Starting row count check", check_name="row_count")
    log.error("Unexpected column type", check_name="data_type", exc=e)
    log.flush_to_delta()   # call once at end of run
"""

import logging
import traceback
import inspect
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from val_framework.core.constants import RUN_LOG_TABLE


class ValidationLogger:
    """
    Structured, location-aware logger for the validation framework.

    Parameters
    ----------
    run_id      : Unique run identifier string
    stream_name : The stream being validated
    spark       : Active SparkSession (used for Delta flush)
    """

    def __init__(self, run_id: str, stream_name: str, spark) -> None:
        self.run_id      = run_id
        self.stream_name = stream_name
        self.spark       = spark
        self._buffer: list[dict] = []

        # ── Standard Python logger (notebook stdout) ──────────────────────────
        self._log = logging.getLogger(f"val_framework.{stream_name}.{run_id[:8]}")
        if not self._log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                "[%(asctime)s][%(levelname)-7s] %(message)s",
                datefmt="%H:%M:%S",
            ))
            self._log.addHandler(handler)
        self._log.setLevel(logging.DEBUG)

    # ── Internal record builder ───────────────────────────────────────────────
    def _record(self, level: str, message: str,
                check_name: Optional[str] = None,
                extra: Optional[dict]    = None,
                exc: Optional[Exception] = None) -> dict:
        """Build a structured log record with full caller context."""
        caller = {"module": "unknown", "function": "unknown", "lineno": -1}
        try:
            for fi in inspect.stack()[3:]:     # skip _record, the log_* caller, and __init__
                if fi.filename != __file__:
                    caller = {
                        "module"   : fi.filename.split("/")[-1].replace(".py", "").replace(".so", ""),
                        "function" : fi.function,
                        "lineno"   : fi.lineno,
                    }
                    break
        except Exception:
            pass

        rec = {
            "log_id"          : str(uuid.uuid4()),
            "run_id"          : self.run_id,
            "stream_name"     : self.stream_name,
            "level"           : level,
            "check_name"      : check_name,
            "message"         : str(message)[:2000],
            "caller_module"   : caller["module"],
            "caller_function" : caller["function"],
            "caller_lineno"   : caller["lineno"],
            "traceback"       : (
                "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                if exc else None
            ),
            "extra"           : json.dumps(extra, default=str) if extra else None,
            "created_ts"      : datetime.now(timezone.utc).isoformat(),
        }
        self._buffer.append(rec)
        return rec

    # ── Public logging methods ────────────────────────────────────────────────
    def info(self, message: str, check_name: str = None,
             extra: dict = None) -> None:
        r = self._record("INFO", message, check_name, extra)
        self._log.info(
            f"[{r['caller_module']}:{r['caller_function']}:{r['caller_lineno']}] {message}"
        )

    def warning(self, message: str, check_name: str = None,
                extra: dict = None) -> None:
        r = self._record("WARNING", message, check_name, extra)
        self._log.warning(
            f"[{r['caller_module']}:{r['caller_function']}:{r['caller_lineno']}] {message}"
        )

    def error(self, message: str, check_name: str = None,
              exc: Exception = None, extra: dict = None) -> None:
        r = self._record("ERROR", message, check_name, extra, exc)
        tb = f"\n{r['traceback']}" if r["traceback"] else ""
        self._log.error(
            f"[{r['caller_module']}:{r['caller_function']}:{r['caller_lineno']}] {message}{tb}"
        )

    def debug(self, message: str, check_name: str = None,
              extra: dict = None) -> None:
        r = self._record("DEBUG", message, check_name, extra)
        self._log.debug(
            f"[{r['caller_module']}:{r['caller_function']}:{r['caller_lineno']}] {message}"
        )

    # ── Flush buffer to Delta ─────────────────────────────────────────────────
    def flush_to_delta(self) -> int:
        """
        Batch-write all buffered records to the Delta log table.
        Returns the number of records written. Clears the buffer.
        Call once at the end of each validation run.
        """
        if not self._buffer:
            return 0
        n = len(self._buffer)
        try:
            self.spark.createDataFrame(self._buffer) \
                .write.format("delta") \
                .mode("append") \
                .saveAsTable(RUN_LOG_TABLE)
            self._buffer.clear()
            self._log.debug(f"Flushed {n} log records → {RUN_LOG_TABLE}")
        except Exception as e:
            # Never let logger failure crash the validation run
            self._log.critical(f"Logger Delta flush FAILED ({n} records lost): {e}")
        return n