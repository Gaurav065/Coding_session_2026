import logging
import sys
import pyspark.sql.functions as F
from pyspark.sql import DataFrame
from pyspark.sql.types import StringType

def setup_logger(stream_name: str) -> logging.Logger:
    logger = logging.getLogger(f"Recon_{stream_name}")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

class ValidationEngine:
    def __init__(self, spark_session, stream_name: str):
        self.spark = spark_session
        self.stream_name = stream_name
        self.log = setup_logger(stream_name)

    def normalize_sap_data(self, df: DataFrame, columns_to_clean: list) -> DataFrame:
        self.log.info("Normalizing SAP string formats (stripping leading zeros)...")
        for c in columns_to_clean:
            if c in df.columns:
                df = df.withColumn(
                    c,
                    F.when(F.col(c).cast(StringType()).rlike("^0{4,}$"), F.lit("0"))
                    .otherwise(F.regexp_replace(F.trim(F.col(c).cast(StringType())), "^0+(?!$)", ""))
                )
        return df

    def get_exact_mismatches(self, src_df: DataFrame, tgt_df: DataFrame, pk_cols: list) -> DataFrame:
        self.log.info(f"Running X-Ray Mismatch Engine on PKs: {pk_cols}...")
        value_cols = [c for c in src_df.columns if c not in pk_cols]

        src_tagged = src_df.withColumn("__in_src", F.lit(True))
        tgt_tagged = tgt_df.withColumn("__in_tgt", F.lit(True))

        joined = src_tagged.alias("src").join(tgt_tagged.alias("tgt"), on=pk_cols, how="full_outer")

        joined = joined.withColumn(
            "issue_type",
            F.when(F.col("src.__in_src").isNull(), "MISSING_IN_SAP")
            .when(F.col("tgt.__in_tgt").isNull(), "MISSING_IN_DATABRICKS")
                .otherwise("EXISTS_IN_BOTH")
        )

        mismatch_conditions = []
        for col in value_cols:
            is_diff = ~F.col(f"src.{col}").cast("string").eqNullSafe(F.col(f"tgt.{col}").cast("string"))
            struct = F.when(
                (F.col("issue_type") == "EXISTS_IN_BOTH") & is_diff, 
                F.struct(
                    F.lit(col).alias("column_name"),
                    F.col(f"src.{col}").cast("string").alias("sap_value"),
                    F.col(f"tgt.{col}").cast("string").alias("dbx_value")
                )
            )
            mismatch_conditions.append(struct)

        mismatch_df = joined.withColumn("mismatches", F.array(*mismatch_conditions)) \
                            .withColumn("mismatches", F.expr("filter(mismatches, x -> x is not null)"))

        orphans = mismatch_df.filter(F.col("issue_type") != "EXISTS_IN_BOTH").select(
            *pk_cols, F.col("issue_type"), F.lit("-").alias("column_name"),
            F.lit(None).cast("string").alias("sap_value"), F.lit(None).cast("string").alias("dbx_value")
        )

        data_issues = mismatch_df.filter(F.size("mismatches") > 0).select(
            *pk_cols, F.lit("DATA_MISMATCH").alias("issue_type"), F.explode("mismatches").alias("issue")
        ).select(
            *pk_cols, "issue_type", F.col("issue.column_name"), F.col("issue.sap_value"), F.col("issue.dbx_value")
        )

        final_report = orphans.unionByName(data_issues)
        self.log.info(f"X-Ray Engine complete. Found {final_report.count()} anomalies.")
        return final_report