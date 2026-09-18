---
name: teradata-to-databricks-conversion
description: Convert Teradata BTEQ, FastExport, and MultiLoad scripts into verified Databricks notebooks by translating logical blocks, validating each checkpoint, and documenting every semantic gap.
---

# Teradata to Databricks conversion

Use this skill when converting one or more Teradata batch scripts into Databricks
notebooks. It is designed for batch conversion: process every supplied script in
one run, while validating each script block before moving to the next block.

## Required inputs

Before editing, locate and read:

1. The repository `README.md`.
2. The source scripts (`.btq`, `.fex`, and `.mld`).
3. The conversion exercise README or equivalent project conventions.
4. The verification file in the converted-scripts folder, such as
   `EXPECTED_RESULTS.md`.
5. Any setup/data-dictionary script that defines schemas, widgets, tables, input
   files, and reset behavior.

If the examples are in an archive, inspect the archive first and extract it to a
temporary directory. Do not modify the archive.

## Conversion contract

For each source script, produce one Databricks notebook source file:

- Use plain PySpark and Spark SQL only; do not add external libraries or shared
  utility modules unless the project explicitly requires them.
- Resolve the catalog and every environment schema from notebook widgets. Never
  hardcode environment-specific catalog or schema names.
- Keep separately supplied schemas separate. Do not collapse variables merely
  because their names look similar.
- Use fully qualified `{catalog}.{schema}.{table}` references.
- Preserve rerun behavior deliberately. Use overwrite/rebuild semantics where
  the source rebuilds a table, and call out source operations that are
  intrinsically non-idempotent.
- Fail loudly on invalid widgets, missing required inputs, failed checks, or
  unexpected row counts. Never hide an error with a broad catch or a success
  fallback.
- Include a migration-notes section in every notebook. Every source construct
  must be mapped, intentionally removed with a reason, or flagged as a semantic
  gap.

## Block-by-block procedure

### 1. Inventory the source

Create a source inventory before translating:

- script type and entry/exit behavior;
- runtime parameters and environment schemas;
- input and output tables/files;
- DDL, DML, joins, filters, window functions, set semantics, and date/string
  operations;
- control-flow commands, error handling, exports/imports, restart/log tables,
  reject handling, and comments describing business rules.

Do not translate shell-wrapper concerns that are explicitly outside the
conversion scope, but record their removal in migration notes.

### 2. Segment into logical blocks

Split the script at business or state boundaries, not arbitrary line counts.
Typical blocks are:

1. parameter and table resolution;
2. staging-table cleanup or initialization;
3. file parsing and record classification;
4. insert/select transformation;
5. joins and lookup resolution;
6. deduplication or Teradata `SET` behavior;
7. update/delete/merge;
8. reject/error output;
9. final materialization and control-table update.

Give each block a stable name and identify its inputs, outputs, invariants, and
expected checkpoint. A 200-line script should normally become several small,
independently reviewable blocks.

### 3. Translate one block at a time

For each block:

- translate the SQL/control flow without changing business predicates;
- use an explicit Spark equivalent for Teradata-specific behavior;
- preserve 1-based substring positions and date formats intentionally;
- make duplicate handling explicit (`DISTINCT`, `dropDuplicates`, or a
  documented alternative) when the source uses a `SET` table or otherwise
  suppresses duplicates;
- replace `EXISTS` deletes with a semantically equivalent anti join where that
  is clearer and safer;
- replace fixed-width file movement with a Delta table unless an external
  consumer truly requires a file;
- preserve rejects in a separate reject table or equivalent output;
- add a small checkpoint assertion immediately after the block.

Checkpoint assertions should verify the strongest available evidence:

- exact row count;
- required columns and data types;
- null/reject counts;
- key uniqueness;
- representative values or full expected contents when supplied;
- source-to-target row conservation for loads and deletes.

If a check cannot run without a live Databricks connection, still emit the
notebook check and clearly report it as not executed; do not claim success.

### 4. Validate the complete notebook

After every block passes:

1. Run syntax/format checks available locally.
2. Run the notebook in the target Databricks environment with the setup data.
3. Compare target tables against the verification file, including exact content
   checks where required, not only row counts.
4. Reset the test data and rerun to verify the documented rerun behavior.
5. Review migration notes against the source inventory for omissions.

Use the verification guide as the source of truth. Do not compare code
textually with a reference notebook when output equivalence is the criterion.

## Teradata-to-Spark review points

Explicitly inspect these common semantic gaps:

- `SET` table duplicate elimination versus Delta allowing duplicates;
- `CHAR` padding, trailing blanks, and case sensitivity;
- implicit casts, especially `DATE` versus `YYYYMMDD` strings;
- Teradata `SUBSTRING(x FROM p FOR n)` and `INDEX` equivalents;
- date arithmetic requiring `date_add`;
- `QUALIFY`, window ordering, and deterministic surrogate-key assignment;
- null behavior in joins and predicates;
- `FORMAT`, fixed-width export, and record layouts;
- FastExport restart/log commands;
- MultiLoad apply/delete/reject semantics;
- BTEQ `.IF ERRORCODE`, `.GOTO`, `.QUIT`, and export commands;
- `PARTITION BY RANGE_N` versus an appropriate Databricks layout;
- transactions and atomicity when replacing multiple sequential writes.

Do not silently “fix” a source quirk. Preserve it when it is business-relevant,
or document the intentional behavior change and its validation evidence.

## Completion report

Return a concise batch report containing:

- scripts converted and output paths;
- logical blocks per script;
- checkpoint results per block;
- final verification results against expected outputs;
- known semantic gaps and follow-up actions;
- any checks that could not execute because Databricks was unavailable.

Only call the conversion successful when every required script has a notebook,
every source construct is accounted for, and all executable verification checks
pass.

## Ready-to-use prompt

The standalone version of this prompt is in
[`TERADATA_TO_DATABRICKS_CONVERSION_PROMPT.md`](../../../TERADATA_TO_DATABRICKS_CONVERSION_PROMPT.md).
Use it after attaching the source scripts and verification materials.
