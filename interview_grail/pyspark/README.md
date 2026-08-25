# PySpark Deep Dive & Interview Prep ⚡

## Core Focus Areas
1. **Architecture & Internal Execution**: Driver, Executors, Tasks, Stages, Jobs, DAG, Catalyst Optimizer, Tungsten Engine.
2. **Transformations & Actions**: Narrow vs. Wide transformations, Lazy Evaluation, Lineage graph.
3. **Dataframe Operations**: Aggregations, Joins (Broadcast, Sort-Merge, Shuffle Hash), Window functions, Handling Nulls.
4. **Performance Tuning & Optimization**:
   - Skewness mitigation (Salting, AQE)
   - Shuffling & Partitioning (`repartition` vs `coalesce`, partition pruning, bucketBy)
   - Caching & Persistence (`cache()`, `persist()`, Storage levels)
   - Adaptive Query Execution (AQE)
5. **Memory Management**: Off-heap vs. On-heap, Storage vs. Execution memory, OOM issues (Driver OOM vs. Executor OOM).
6. **Structured Streaming**: Watermarking, Checkpointing, Triggers, Output Modes.
