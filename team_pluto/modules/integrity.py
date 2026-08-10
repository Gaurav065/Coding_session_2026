"""
Stage 0 — Raw Zone Integrity Check.

Reads the pre-generated checksum manifests (Batch{N}_checksum_fast.sha256)
and verifies three checks against the actual ADLS batch folder:

  FILE_COUNT  — number of data files matches manifest
  TOTAL_SIZE  — sum of file sizes matches manifest
  FILE_HASH   — MD5 of sorted "filename:size" list matches manifest

The manifest file format (one check per line):
  FILE_COUNT|17
  TOTAL_SIZE|1367482901
  FILE_HASH|a3f7c2e8...
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType, LongType, StringType, StructField, StructType, TimestampType,
)


@dataclass
class BatchIntegrityResult:
    batch: str
    raw_folder: str
    expected_file_count: int
    actual_file_count: int
    expected_total_size: int
    actual_total_size: int
    expected_file_hash: str
    actual_file_hash: str
    hash_match: bool
    status: str          # PASS / FAIL / ERROR
    error_detail: str
    run_id: str


# ─── Manifest parsing ────────────────────────────────────────────────────────

def _parse_manifest(spark: SparkSession, manifest_path: str) -> dict:
    """Read Batch{N}_checksum_fast.sha256 and return {CHECK_TYPE: value} dict.

    Handles format:  FILE_COUNT  (Batch1) = 439
    Also handles legacy pipe format: FILE_COUNT|439
    Comment lines (starting with #) and blank lines are skipped.
    """
    try:
        lines = [row.value for row in spark.read.text(manifest_path).collect()]
    except Exception as e:
        raise FileNotFoundError(f"Manifest not found: {manifest_path}") from e

    result = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            # e.g. "FILE_COUNT  (Batch1) = 439"
            key_part, val = line.split("=", 1)
            # Strip the batch qualifier: "FILE_COUNT  (Batch1) " → "FILE_COUNT"
            key = key_part.split("(")[0].strip()
            result[key] = val.strip()
        elif "|" in line:
            # Legacy pipe format: "FILE_COUNT|439"
            key, val = line.split("|", 1)
            result[key.strip()] = val.strip()
    return result


# ─── ADLS file listing ───────────────────────────────────────────────────────

def _list_data_files(dbutils, folder_path: str) -> List[dict]:
    """List files in an ADLS folder via dbutils.fs.ls().

    dbutils must be passed from the notebook — UC shared clusters block
    all JVM-based access so dbutils cannot be obtained via spark._jvm.

    Returns list of {'name': str, 'size': int}.
    _audit.csv files ARE included — the manifests were generated with them.
    """
    files = []
    for f in dbutils.fs.ls(folder_path):
        name = f.name
        # Exclude only manifest files and subdirectory entries
        if name.endswith(".sha256") or name.endswith("/"):
            continue
        files.append({"name": name.rstrip("/"), "size": int(f.size)})
    return files


# ─── Hash computation ────────────────────────────────────────────────────────

def _compute_file_hash(files: List[dict]) -> str:
    """MD5 of sorted 'filename:size' list (matches manifest generation logic)."""
    sorted_files = sorted(files, key=lambda x: x["name"])
    content = "\n".join(f"{f['name']}:{f['size']}" for f in sorted_files)
    return hashlib.md5(content.encode()).hexdigest()


# ─── Core verification ────────────────────────────────────────────────────────

def verify_batch(
    spark: SparkSession,
    dbutils,
    batch_id: str,
    base_path: str,
    run_id: str,
) -> BatchIntegrityResult:
    """Run integrity check for one batch. Returns a BatchIntegrityResult.

    dbutils must be passed from the notebook — UC shared clusters block
    all JVM-based access so dbutils cannot be obtained via spark._jvm.
    """

    batch_folder = f"Batch{batch_id}"
    folder_path = f"{base_path}/{batch_folder}"
    manifest_path = f"{base_path}/Batch{batch_id}_checksum_fast.sha256"

    error_detail = ""
    status = "PASS"
    manifest = {}
    files = []

    try:
        manifest = _parse_manifest(spark, manifest_path)
    except FileNotFoundError as e:
        return BatchIntegrityResult(
            batch=batch_id, raw_folder=folder_path,
            expected_file_count=0, actual_file_count=0,
            expected_total_size=0, actual_total_size=0,
            expected_file_hash="", actual_file_hash="",
            hash_match=False, status="ERROR",
            error_detail=f"FAIL_NO_MANIFEST: {e}", run_id=run_id,
        )

    try:
        files = _list_data_files(dbutils, folder_path)
    except Exception as e:
        return BatchIntegrityResult(
            batch=batch_id, raw_folder=folder_path,
            expected_file_count=int(manifest.get("FILE_COUNT", 0)),
            actual_file_count=0,
            expected_total_size=int(manifest.get("TOTAL_SIZE", 0)),
            actual_total_size=0,
            expected_file_hash=manifest.get("FILE_HASH", ""),
            actual_file_hash="",
            hash_match=False, status="ERROR",
            error_detail=f"FOLDER_LIST_FAILED: {e}", run_id=run_id,
        )

    exp_count = int(manifest.get("FILE_COUNT", -1))
    exp_size = int(manifest.get("TOTAL_SIZE", -1))
    exp_hash = manifest.get("FILE_HASH", "")

    actual_count = len(files)
    actual_size = sum(f["size"] for f in files)
    actual_hash = _compute_file_hash(files)

    failures = []
    if exp_count != actual_count:
        failures.append(f"FILE_COUNT exp={exp_count} got={actual_count}")
    if exp_size != actual_size:
        failures.append(f"TOTAL_SIZE exp={exp_size} got={actual_size}")
    if exp_hash != actual_hash:
        failures.append(f"FILE_HASH exp={exp_hash[:16]}... got={actual_hash[:16]}...")

    if failures:
        status = "FAIL"
        error_detail = "; ".join(failures)

    return BatchIntegrityResult(
        batch=batch_id,
        raw_folder=folder_path,
        expected_file_count=exp_count,
        actual_file_count=actual_count,
        expected_total_size=exp_size,
        actual_total_size=actual_size,
        expected_file_hash=exp_hash,
        actual_file_hash=actual_hash,
        hash_match=(exp_hash == actual_hash),
        status=status,
        error_detail=error_detail,
        run_id=run_id,
    )


# ─── Result persistence ──────────────────────────────────────────────────────

_INTEGRITY_SCHEMA = StructType([
    StructField("raw_folder", StringType(), True),
    StructField("batch", StringType(), True),
    StructField("file_name", StringType(), True),
    StructField("expected_total_size", LongType(), True),
    StructField("actual_total_size", LongType(), True),
    StructField("expected_file_count", LongType(), True),
    StructField("actual_file_count", LongType(), True),
    StructField("hash_match", BooleanType(), True),
    StructField("status", StringType(), True),
    StructField("error_detail", StringType(), True),
    StructField("run_id", StringType(), True),
    StructField("check_timestamp", TimestampType(), True),
])


def results_to_df(spark: SparkSession, results: List[BatchIntegrityResult]) -> DataFrame:
    """Convert list of BatchIntegrityResult to DataFrame matching operations.integrity_check schema."""
    rows = []
    for r in results:
        rows.append((
            r.raw_folder, r.batch, "",
            r.expected_total_size, r.actual_total_size,
            r.expected_file_count, r.actual_file_count,
            r.hash_match, r.status, r.error_detail, r.run_id, None,
        ))
    df = spark.createDataFrame(rows, schema=_INTEGRITY_SCHEMA)
    return df.withColumn("check_timestamp", F.current_timestamp())


def persist_results(
    spark: SparkSession,
    results: List[BatchIntegrityResult],
    table: str,
) -> None:
    """Append integrity check results to operations.integrity_check Delta table."""
    df = results_to_df(spark, results)
    df.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(table)
