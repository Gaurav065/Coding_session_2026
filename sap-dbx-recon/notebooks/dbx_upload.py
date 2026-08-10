# Databricks notebook source
# MAGIC %pip install openpyxl
# MAGIC

# COMMAND ----------

import pandas as pd

# 1. Read the uploaded Excel file from the UC Volume
file_path = "/Volumes/recon_framework/validation_inputs/raw_files/GB_YRFORECAST (1).xlsx"
pdf = pd.read_excel(file_path, sheet_name="result")

# Clean up object types if necessary before Spark conversion
for c in pdf.columns:
    if pdf[c].dtype == object:
        pdf[c] = pdf[c].astype(str)

# 2. Convert to Spark DataFrame
sdf = spark.createDataFrame(pdf)

# Pro-Tip: If you plan to do heavy transformations or multiple joins on 'sdf' 
# before writing it to Delta, it is highly recommended to cache or persist it first:
# sdf.persist()

# 3. Write to Delta Table
table_name = "recon_framework.validation_data.dbx_manual_upload"

(sdf.write
  .format("delta")
  .mode("overwrite")
  .option("overwriteSchema", "true")
  # Pro-Tip: If this is a massive table, add partitioning to speed up future reads
  # .partitionBy("region_or_date_column")
  .saveAsTable(table_name))