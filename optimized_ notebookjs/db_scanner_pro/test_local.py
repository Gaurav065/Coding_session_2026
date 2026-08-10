import pyspark
from delta import configure_spark_with_delta_pip
import pandas as pd
from reconciler import ValidationEngine

# 1. Initialize Local Spark with Delta Lake Support
builder = pyspark.sql.SparkSession.builder.appName("LocalReconTesting") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")

spark = configure_spark_with_delta_pip(builder).getOrCreate()

# 2. Create Mock Data (Simulating SAP vs DBX)
print("\n--- Creating Mock Data ---")
sap_data = pd.DataFrame({
    "MATERIAL": ["001001", "001002", "001003", "009999"], # Notice the leading zeros
    "PLANT": ["DC01", "DC01", "DC02", "DC01"],
    "QTY": [100.0, 50.5, 200.0, 10.0],
    "PRICE": ["12.50", "0000", "5.00", "1.00"] # Includes an "SAP Blank"
})

dbx_data = pd.DataFrame({
    "MATERIAL": ["1001", "1002", "1003", "5555"], # DBX has clean IDs
    "PLANT": ["DC01", "DC01", "DC02", "DC01"],
    "QTY": [100.0, 55.0, 200.0, 500.0], # 1002 has a mismatched QTY (55.0 instead of 50.5)
    "PRICE": ["12.50", "0", "5.00", "99.00"] # 1002 Price is "0"
})

sap_df = spark.createDataFrame(sap_data)
dbx_df = spark.createDataFrame(dbx_data)

print("SAP Data:")
sap_df.show()
print("Databricks Data:")
dbx_df.show()

# 3. Run the Engine
print("\n--- Running Validation Engine ---")
engine = ValidationEngine(spark, stream_name="local_test_stream")

# Normalize first!
pk_columns = ["MATERIAL", "PLANT"]
all_cols = sap_df.columns

sap_clean = engine.normalize_sap_data(sap_df, all_cols)
dbx_clean = engine.normalize_sap_data(dbx_df, all_cols)

# Run X-Ray
results_df = engine.get_exact_mismatches(sap_clean, dbx_clean, pk_columns)

# 4. Show the exact mismatched rows and columns!
print("\n--- Final Mismatch Ledger ---")
results_df.show(truncate=False)

# Stop Spark
spark.stop()