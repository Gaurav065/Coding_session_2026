# Databricks Deep Dive & Interview Prep 🧱

## Core Focus Areas
1. **Lakehouse & Delta Lake**:
   - ACID transactions, Transaction Log (`_delta_log`), Time Travel, Vacuum, OPTIMIZE & Z-Ordering.
   - Liquid Clustering vs. Z-Ordering / Partitioning.
   - Change Data Feed (CDF), Merge schema, Schema evolution & enforcement.
2. **Unity Catalog & Governance**:
   - 3-level namespace (`catalog.schema.table`), Data Lineage, Row/Column level security, Managed vs. External tables.
   - Volumes, Grants, Storage Credentials, External Locations.
3. **Data Pipelines & Workflows**:
   - Delta Live Tables (DLT): Expectations, Materialized views, Streaming tables, CDC with `APPLY CHANGES INTO`.
   - Databricks Asset Bundles (DABs), Databricks Workflows, Task orchestration.
4. **Compute & Cluster Management**:
   - All-Purpose vs. Job Clusters, Single Node vs. Multi-node, Photon engine, Serverless Compute, Spot vs. On-Demand instances.
5. **Security & Networking**:
   - Secrets, Key Vault integration, Secure cluster connectivity (No Public IP).
