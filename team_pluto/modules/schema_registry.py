"""
Schema registry — explicit StructType schemas for all 19 source files.

Landing schemas use StringType for all fields (schema inference is disabled
for performance on large files). Bronze schemas are identical at the column
level but all types are STRING. Audit columns (_ingest_ts etc.) are added
by audit_utils — not defined here.

Column naming follows the raw source files exactly so lineage is traceable.
"""
from __future__ import annotations

from pyspark.sql.types import StringType, StructField, StructType

S = StringType


def _str_schema(*col_names: str) -> StructType:
    return StructType([StructField(c, S(), True) for c in col_names])


# ─── DOMAIN 1: CONTROL ──────────────────────────────────────────────────────

# BatchDate.txt — single-line text, code creates these columns
BATCHDATE = _str_schema("batchdate", "batchid")

# ─── DOMAIN 2: CROSS-DOMAIN REFERENCE ───────────────────────────────────────

# Date.txt — pipe-delimited WITH header (header defines col names automatically)
DATE = _str_schema(
    "record_id", "source_date_string", "source_system_code",
    "extract_batch_id", "raw_load_timestamp",
)

# Time.txt — pipe-delimited WITH header
TIME = _str_schema(
    "record_id", "source_time_string", "source_system_code",
    "time_precision", "extract_batch_id", "raw_load_timestamp",
)

# StatusType.txt — pipe-delimited, NO header
STATUSTYPE = _str_schema("ST_ID", "ST_NAME")

# TaxRate.txt — pipe-delimited, NO header
TAXRATE = _str_schema("TX_ID", "TX_NAME", "TX_RATE")

# Industry.txt — pipe-delimited, NO header
INDUSTRY = _str_schema("IN_ID", "IN_NAME", "IN_SC_ID")

# TradeType.txt — pipe-delimited, NO header
TRADETYPE = _str_schema("TT_ID", "TT_NAME", "TT_IS_SELL", "TT_IS_MRKT")

# ─── DOMAIN 3: MARKET ───────────────────────────────────────────────────────

# FINWIRE — fixed-width text; read as raw lines (single column)
FINWIRE_RAW = _str_schema("line")

# DailyMarket.txt
# B1: 6 data cols (no CDC prefix)  → normalized by adding DM_ACTION + DM_RECID
# B2/B3: DM_ACTION, DM_RECID first, then 6 data cols
DAILYMARKET_B1 = _str_schema(
    "DM_DATE", "DM_S_SYMB", "DM_CLOSE", "DM_HIGH", "DM_LOW", "DM_VOL",
)
DAILYMARKET_B2B3 = _str_schema(
    "DM_ACTION", "DM_RECID",
    "DM_DATE", "DM_S_SYMB", "DM_CLOSE", "DM_HIGH", "DM_LOW", "DM_VOL",
)
# Normalized Bronze schema (all batches, 8 data cols)
DAILYMARKET = _str_schema(
    "DM_DATE", "DM_S_SYMB", "DM_CLOSE", "DM_HIGH", "DM_LOW", "DM_VOL",
    "DM_ACTION", "DM_RECID",
)

# ─── DOMAIN 4: HR/BROKER ─────────────────────────────────────────────────────

# HR.csv — comma-delimited, NO header, 9 columns
HR = _str_schema(
    "EMPLOYEE_ID", "MANAGER_ID", "LAST_NAME", "FIRST_NAME",
    "MIDDLE_INITIAL", "JOB_CODE", "BRANCH_ID", "OFFICE", "PHONE",
)

# ─── DOMAIN 5: CUSTOMER ──────────────────────────────────────────────────────

# CustomerMgmt.xml — nested XML flattened to wide schema
# All fields from Customer + Account sub-elements across 6 ActionTypes
CUSTOMERMGMT = _str_schema(
    "ActionType", "ActionTS",
    "C_ID", "C_TAX_ID", "C_GNDR", "C_TIER", "C_DOB",
    "C_L_NAME", "C_F_NAME", "C_M_NAME",
    "C_ADLINE1", "C_ADLINE2", "C_ZIPCODE", "C_CITY", "C_STATE_PROV", "C_CTRY",
    "C_PRIM_EMAIL", "C_ALT_EMAIL",
    "C_CTRY_1", "C_AREA_1", "C_LOCAL_1", "C_EXT_1",
    "C_CTRY_2", "C_AREA_2", "C_LOCAL_2", "C_EXT_2",
    "C_CTRY_3", "C_AREA_3", "C_LOCAL_3", "C_EXT_3",
    "C_LCL_TX_ID", "C_NAT_TX_ID",
    "CA_ID", "CA_TAX_ST", "CA_B_ID", "CA_NAME",
)

# Customer.txt — B2/B3 only, 33 pipe-delimited fields, NO header
CUSTOMER = _str_schema(
    "CDC_FLAG", "C_ID", "CDC_DSN",
    "C_TAX_ID", "C_ST_ID", "C_L_NAME", "C_F_NAME", "C_M_NAME",
    "C_GNDR", "C_TIER", "C_DOB",
    "C_ADLINE1", "C_ADLINE2", "C_ZIPCODE", "C_CITY", "C_STATE_PROV", "C_CTRY",
    "C_CTRY_1", "C_AREA_1", "C_LOCAL_1", "C_EXT_1",
    "C_CTRY_2", "C_AREA_2", "C_LOCAL_2", "C_EXT_2",
    "C_CTRY_3", "C_AREA_3", "C_LOCAL_3", "C_EXT_3",
    "C_EMAIL_1", "C_EMAIL_2",
    "C_LCL_TX_ID", "C_NAT_TX_ID",
)

# Prospect.json — 22 flattened fields (JSON or CSV fallback)
PROSPECT = _str_schema(
    "agencyid", "lastname", "firstname", "middleinitial",
    "gender", "addressline1", "addressline2",
    "postalcode", "city", "state", "country", "phone",
    "income", "numbercars", "numberchildren",
    "maritalstatus", "age", "creditrating",
    "ownorrentflag", "employer", "numbercreditcards", "networth",
)

# WatchHistory.txt
# B1: 4 cols (no CDC prefix); normalized by adding CDC_FLAG + CDC_DSN
WATCHHISTORY_B1 = _str_schema("W_C_ID", "W_S_SYMB", "W_DTS", "W_ACTION")
WATCHHISTORY_B2B3 = _str_schema("CDC_FLAG", "CDC_DSN", "W_C_ID", "W_S_SYMB", "W_DTS", "W_ACTION")
WATCHHISTORY = _str_schema("W_C_ID", "W_S_SYMB", "W_DTS", "W_ACTION", "CDC_FLAG", "CDC_DSN")

# ─── DOMAIN 6: ACCOUNT ───────────────────────────────────────────────────────

# Account.txt — B2/B3 only, 8 fields, NO header
ACCOUNT = _str_schema(
    "CDC_FLAG", "CDC_DSN", "CA_ID", "CA_C_ID",
    "CA_B_ID", "CA_NAME", "CA_TAX_ST", "CA_ST_ID",
)

# CashTransaction.txt
# B1: 4 data cols; normalized by adding CDC_FLAG + CDC_DSN
CASHTRANSACTION_B1 = _str_schema("CT_CA_ID", "CT_DTS", "CT_AMT", "CT_NAME")
CASHTRANSACTION_B2B3 = _str_schema("CDC_FLAG", "CDC_DSN", "CT_CA_ID", "CT_DTS", "CT_AMT", "CT_NAME")
CASHTRANSACTION = _str_schema("CT_CA_ID", "CT_DTS", "CT_AMT", "CT_NAME", "CDC_FLAG", "CDC_DSN")

# ─── DOMAIN 7: TRADE ─────────────────────────────────────────────────────────

# Trade.txt — B1: 14 cols; B2/B3: +CDC_FLAG + CDC_DSN = 16 cols
TRADE_DATA_COLS = (
    "T_ID", "T_DTS", "T_ST_ID", "T_TT_ID", "T_IS_CASH",
    "T_S_SYMB", "T_QTY", "T_BID_PRICE", "T_CA_ID", "T_EXEC_NAME",
    "T_TRADE_PRICE", "T_CHRG", "T_COMM", "T_TAX",
)
TRADE_B1 = _str_schema(*TRADE_DATA_COLS)
TRADE_B2B3 = _str_schema("CDC_FLAG", "CDC_DSN", *TRADE_DATA_COLS)
TRADE = _str_schema(*TRADE_DATA_COLS, "CDC_FLAG", "CDC_DSN")  # normalized Bronze

# TradeHistory.txt — B1 only, 3 fields, NO header
TRADEHISTORY = _str_schema("TH_T_ID", "TH_DTS", "TH_ST_ID")

# HoldingHistory.txt
# B1: 4 data cols; B2/B3: +CDC_FLAG + CDC_DSN
HOLDINGHISTORY_B1 = _str_schema("HH_H_T_ID", "HH_T_ID", "HH_BEFORE_QTY", "HH_AFTER_QTY")
HOLDINGHISTORY_B2B3 = _str_schema(
    "CDC_FLAG", "CDC_DSN", "HH_H_T_ID", "HH_T_ID", "HH_BEFORE_QTY", "HH_AFTER_QTY",
)
HOLDINGHISTORY = _str_schema(
    "HH_H_T_ID", "HH_T_ID", "HH_BEFORE_QTY", "HH_AFTER_QTY", "CDC_FLAG", "CDC_DSN",
)
