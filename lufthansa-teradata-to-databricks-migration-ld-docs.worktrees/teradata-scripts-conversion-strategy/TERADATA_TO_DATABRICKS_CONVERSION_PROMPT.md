# Teradata to Databricks conversion prompt

You are converting the attached Teradata batch scripts into Databricks
notebooks. Convert every supplied script in one run, but do not translate a
large script as one opaque block. First understand the complete script, then
split it into logical business blocks and validate each block before continuing.

## Materials to read first

Read the repository `README.md`, the exercise/project README, all source scripts,
the setup/data-dictionary script, and the converted-scripts verification file
(for example `EXPECTED_RESULTS.md`). Treat the verification file as the
acceptance criteria. If the materials are archived, inspect and extract them
without modifying the archive.

## Required output

For each `.btq`, `.fex`, or `.mld` source:

1. Create one Databricks notebook source file.
2. Use plain PySpark and Spark SQL only.
3. Resolve the catalog and every environment schema from notebook widgets.
4. Use fully qualified `{catalog}.{schema}.{table}` names.
5. Preserve the source business logic, filters, joins, date rules, duplicate
   behavior, rejects, and rerun semantics.
6. Add migration notes that account for every Teradata construct. If something
   has no Databricks equivalent, state that explicitly and explain the chosen
   replacement or why it was removed.
7. Fail loudly for invalid parameters, failed assertions, missing inputs, or
   unexpected results.

## Required workflow for each script

### A. Inventory

List the script type, parameters, environment schemas, inputs, outputs, DDL/DML,
joins, filters, windows, file layouts, rejects, control-flow commands, and
Teradata-only behavior.

### B. Segment

Split into named logical blocks such as parameter resolution, staging cleanup,
file parsing, transformation, joins/lookups, deduplication, updates/deletes,
reject handling, and final writes. Segment by business/state boundaries rather
than arbitrary line counts.

### C. Convert and checkpoint

Convert one block at a time. After each block, add an executable checkpoint
appropriate to the available environment. Prefer, in order:

- exact expected row count;
- schema and required-column checks;
- null and reject counts;
- key-uniqueness checks;
- representative or exact expected values;
- row-conservation checks for loads/deletes.

Use explicit equivalents for Teradata `SET` duplicate suppression, 1-based
substring positions, `INDEX`, date arithmetic, null predicates, `QUALIFY`,
window ordering, fixed-width records, FastExport, MultiLoad, and BTEQ error
commands. Do not rely on accidental Spark behavior or implicit casts.

### D. Full verification

After all blocks pass, run the complete notebook in Databricks, compare outputs
with the verification file, reset the test data, and rerun to verify the stated
idempotency/non-idempotency behavior. Do not claim a Databricks check passed if
Databricks was unavailable; report it as not executed.

## Acceptance criteria

The batch is successful only when:

- every supplied source has a corresponding notebook;
- every source construct is mapped, intentionally removed with a reason, or
  flagged as a semantic gap;
- every executable block checkpoint passes;
- final tables/files match the verification criteria for counts and contents;
- rejects and error behavior are preserved;
- rerun behavior is documented and verified;
- the final report lists output paths, block checks, known gaps, and any
  environment-limited checks.

At the end, provide the final conversion report and do not omit unresolved
differences.
