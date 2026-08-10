import React, { useState, useRef, useLayoutEffect, useEffect } from "react";
import {
  Pause, Brain, GitBranch, ArrowLeftRight, Cpu, Save,
  Server, Network, Boxes, Database,
  AlertTriangle, FileWarning, Skull, Snowflake, Radio,
  X, ChevronRight, Code2, Layers, Filter, Gauge, Flame,
  HardDrive, Zap, MemoryStick, ArrowDown, Activity, Workflow,
  Search, Hash, ShieldAlert
} from "lucide-react";

/* ────────────────────────────────────────────────────────────────────────
   Typography & atmosphere
   ──────────────────────────────────────────────────────────────────── */
const STYLES = `
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600;9..144,700&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

.font-display { font-family: 'Fraunces', Georgia, serif; font-optical-sizing: auto; }
.font-body    { font-family: 'Inter', system-ui, sans-serif; }
.font-mono    { font-family: 'JetBrains Mono', ui-monospace, monospace; }

.bp-grid {
  background-image:
    linear-gradient(rgba(94,234,212,0.04) 1px, transparent 1px),
    linear-gradient(90deg, rgba(94,234,212,0.04) 1px, transparent 1px);
  background-size: 32px 32px;
}
.glow-cyan   { box-shadow: 0 0 0 1px rgba(94,234,212,0.25), 0 8px 32px -12px rgba(94,234,212,0.35); }
.glow-amber  { box-shadow: 0 0 0 1px rgba(251,191,36,0.25), 0 8px 32px -12px rgba(251,191,36,0.30); }
.glow-rose   { box-shadow: 0 0 0 1px rgba(244,114,182,0.30), 0 8px 32px -12px rgba(244,114,182,0.35); }
.glow-red    { box-shadow: 0 0 0 1px rgba(239,68,68,0.45),  0 0 24px -4px rgba(239,68,68,0.55); }
.glow-emerald{ box-shadow: 0 0 0 1px rgba(52,211,153,0.30), 0 8px 32px -12px rgba(52,211,153,0.35); }

@keyframes pulse-soft {
  0%, 100% { opacity: 0.55; }
  50% { opacity: 1; }
}
.pulse-soft { animation: pulse-soft 2.4s ease-in-out infinite; }

@keyframes flow {
  to { stroke-dashoffset: -24; }
}
.line-flow { stroke-dasharray: 4 6; animation: flow 1.6s linear infinite; }

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(200%); }
}
.shimmer::after {
  content: ''; position: absolute; inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.06), transparent);
  animation: shimmer 3s ease-in-out infinite;
}

@keyframes drift {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-2px); }
}
.drift { animation: drift 3s ease-in-out infinite; }

.scrollbar-tame::-webkit-scrollbar { width: 8px; }
.scrollbar-tame::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.08); border-radius: 4px; }
.scrollbar-tame::-webkit-scrollbar-track { background: transparent; }
`;

/* ────────────────────────────────────────────────────────────────────────
   Phase + infra metadata
   ──────────────────────────────────────────────────────────────────── */
const PHASES = [
  { id: "p1", num: "01", title: "Lazy Evaluation",      sub: "Build the recipe",       icon: Pause },
  { id: "p2", num: "02", title: "Catalyst Optimizer",   sub: "The brain",              icon: Brain, expanded: true },
  { id: "p3", num: "03", title: "DAG Scheduler",        sub: "Stage decomposition",    icon: GitBranch },
  { id: "p4", num: "04", title: "Task Scheduler",       sub: "Resource negotiation",   icon: ArrowLeftRight },
  { id: "p5", num: "05", title: "Execution Engines",    sub: "The muscle",             icon: Cpu, accent: "rose" },
  { id: "p6", num: "06", title: "Return / Write",       sub: "Persist output",         icon: Save },
];

const PHYSICAL = [
  { id: "driver",  title: "Driver Node",       sub: "Coordinator",      icon: Server  },
  { id: "cm",      title: "Cluster Manager",   sub: "Resource broker",  icon: Network },
  { id: "workers", title: "Worker Nodes",      sub: "Compute fleet",    icon: Boxes   },
  { id: "storage", title: "ADLS Gen2",         sub: "Data lake",        icon: Database},
];

/* Connections from logical (left) to physical (right) */
const CONNECTIONS = [
  { from: "p1", to: "storage", kind: "read"    },
  { from: "p1", to: "driver",  kind: "control" },
  { from: "p2", to: "driver",  kind: "control" },
  { from: "p3", to: "driver",  kind: "control" },
  { from: "p4", to: "driver",  kind: "control" },
  { from: "p4", to: "cm",      kind: "control" },
  { from: "p5", to: "workers", kind: "execute" },
  { from: "p6", to: "storage", kind: "write"   },
];

/* ────────────────────────────────────────────────────────────────────────
   Deep-dive content for the right-side detail drawer
   ──────────────────────────────────────────────────────────────────── */
const DETAIL = {
  p1: {
    eyebrow: "Phase 01 · Logical",
    title: "Lazy Evaluation",
    blurb: "Spark builds a lineage graph but defers execution until an action is called. The delay is what gives the optimizer a global view.",
    sections: [
      { h: "Transformations (deferred)",
        p: "select · filter · withColumn · groupBy · join · repartition. Each call returns a new DataFrame and only mutates the lineage graph.",
        code: `df2 = (df
  .filter(col("age") > 30)
  .select("name", "salary"))
# nothing has executed yet` },
      { h: "Actions (trigger)",
        p: "show · count · collect · write · take · foreach · toPandas. They materialise results and trigger plan compilation + execution.",
        code: `df2.write.format("delta").save(path)
# now Catalyst kicks in` },
      { h: "Why lazy?",
        p: "The optimizer can reorder, fuse, prune and push down operators across the entire pipeline rather than each step in isolation." },
    ],
    pitfalls: [
      "Calling actions in a loop forces full recomputation — cache between calls.",
      "`.count()` on a long chain re-executes from source unless an intermediate `persist()` exists.",
    ],
  },
  p2: {
    eyebrow: "Phase 02 · Logical",
    title: "Catalyst Optimizer",
    blurb: "A rule + cost-based optimizer. It walks a tree of TreeNodes through four stages and picks a physical plan, then routes to Photon or Tungsten.",
    sections: [
      { h: "Pipeline",
        p: "Unresolved Logical Plan → Catalog Resolution → Optimized Logical Plan → Physical Plans → Cost Model → Selected Plan." },
      { h: "Predicate Pushdown",
        p: "Filters are pushed into the data source so Parquet/Delta reads skip row groups using min/max stats — often 10–100× less I/O.",
        code: `# logical:
df.filter(col("year")=2024).select("id","ts")
# physical → reader sees:
PushedFilters: [EqualTo(year, 2024)]
ReadSchema: struct<id:long, ts:timestamp>` },
      { h: "Photon vs JVM decision",
        p: "If every operator in the plan is Photon-supported, the executor runs vectorized C++ code. Otherwise the plan falls back to whole-stage codegen on the JVM (Tungsten)." },
    ],
    pitfalls: [
      "UDFs (especially Python) opt out of Photon and break codegen — prefer built-in expressions.",
      "Non-deterministic functions (rand, current_timestamp) inhibit several rewrite rules.",
    ],
  },
  p3: {
    eyebrow: "Phase 03 · Logical",
    title: "DAG Scheduler",
    blurb: "The selected physical plan is split into a DAG of stages. Stage boundaries are exactly the wide transformations.",
    sections: [
      { h: "Narrow vs Wide",
        p: "Narrow (map, filter, union): each output partition depends on one input partition — pipelined inside a stage. Wide (groupBy, join, distinct, repartition): require a shuffle — they create stage boundaries." },
      { h: "Shuffle = boundary",
        p: "A shuffle materialises map-output files on disk on every executor and the next stage reads them across the network. It is the single most expensive operation in Spark." },
      { h: "ShuffleMapStage / ResultStage",
        p: "All stages except the last are ShuffleMapStages writing shuffle output. The terminal stage is a ResultStage producing the action's output." },
    ],
    pitfalls: [
      "Wide transformations 10× more expensive than narrow — minimise them.",
      "Default `spark.sql.shuffle.partitions = 200` is rarely right; tune to data volume or rely on AQE.",
    ],
  },
  p4: {
    eyebrow: "Phase 04 · Logical",
    title: "Task Scheduler & Negotiation",
    blurb: "Each stage becomes N tasks (N = partitions). The driver's TaskScheduler hands tasks to executors, the Cluster Manager allocates the executors themselves.",
    sections: [
      { h: "Locality preference order",
        p: "PROCESS_LOCAL → NODE_LOCAL → RACK_LOCAL → ANY. Spark waits `spark.locality.wait` (3s default) for a better slot before falling back." },
      { h: "Speculative execution",
        p: "Slow tasks (stragglers) are duplicated on another executor; whichever finishes first wins. Helps tail latency but doubles work." },
      { h: "Dynamic allocation",
        p: "On Databricks / YARN / K8s, the cluster manager can scale executors up/down based on pending tasks." },
    ],
    pitfalls: [
      "Long locality waits with bad data placement add seconds per task.",
      "Speculation amplifies skew — a slow task spawned by skew is just slow on the duplicate too.",
    ],
  },
  p5: {
    eyebrow: "Phase 05 · Execution",
    title: "Tungsten + Photon",
    blurb: "Tasks run on executor JVMs. Spark uses one of two engines depending on the plan and runtime.",
    sections: [
      { h: "Project Tungsten (JVM)",
        p: "Whole-stage code generation fuses operators into a single JVM bytecode loop. Off-heap memory + cache-aware sort/aggregation. Universal — runs anywhere Spark runs." },
      { h: "Photon (Native, Databricks-only)",
        p: "Vectorized C++ engine. Operates on columnar batches with SIMD instructions. Roughly 2-4× faster than Tungsten on supported workloads (joins, aggregates, scans)." },
      { h: "Shuffle write/read",
        p: "Inside a wide stage, tasks produce shuffle files (map side) consumed by the next stage's tasks (reduce side). Sort-based shuffle is the default since 2.0." },
    ],
    pitfalls: [
      "PySpark UDFs cross the JVM↔Python boundary per row — use pandas UDFs / arrow when unavoidable.",
      "Photon falls back partially: any unsupported op forces that subtree onto JVM, surfacing in the plan as `RowToColumnar` / `ColumnarToRow`.",
    ],
  },
  p6: {
    eyebrow: "Phase 06 · Logical",
    title: "Return / Write",
    blurb: "The terminal action writes data back to ADLS Gen2 (Parquet, Delta) or returns it to the driver.",
    sections: [
      { h: "Commit protocols",
        p: "v1 (legacy) renames staged files. v2 / DBIO (Databricks) uses a transaction log. Delta's protocol gives ACID via the `_delta_log` directory." },
      { h: "Partitioning vs Z-Order",
        p: "Partition columns = directory layout. Z-Order = data layout inside files via Hilbert curves — good for high-cardinality filters." },
      { h: "Driver-bound returns",
        p: "`.collect()` / `.toPandas()` pull all rows to the driver heap. Anything > a few hundred MB risks Driver OOM." },
    ],
    pitfalls: [
      "Many small files crush ADLS metadata + downstream readers.",
      "Overwriting partitions without `replaceWhere` rewrites everything.",
    ],
  },
  driver: {
    eyebrow: "Physical · Coordinator",
    title: "Driver Node",
    blurb: "The single JVM that hosts SparkContext. Compiles your code, plans the job, schedules tasks, tracks lineage, returns results.",
    sections: [
      { h: "What lives on the driver",
        p: "SparkContext · SQLContext · Catalyst · DAGScheduler · TaskScheduler · BlockManagerMaster · BroadcastManager · the web UI." },
      { h: "Why it's a SPOF",
        p: "Lose the driver and the application is gone — even if 1000 executors are healthy. On Databricks the cluster restarts; on YARN/K8s the AppMaster terminates." },
    ],
    pitfalls: [
      "`.collect()` on a 5GB DataFrame ≫ default `spark.driver.memory` → OOM.",
      "Heavy broadcast variables (>1 GB) bloat driver heap before they're shipped.",
    ],
  },
  cm: {
    eyebrow: "Physical · Resource broker",
    title: "Cluster Manager",
    blurb: "Decides which physical machines run executors. The driver requests, the manager allocates.",
    sections: [
      { h: "Implementations",
        p: "Standalone · YARN · Mesos (deprecated) · Kubernetes · Databricks (proprietary control plane). The Spark API is identical; only deployment differs." },
      { h: "On Databricks",
        p: "The control plane provisions VMs (Standard / Compute / Photon) from the cloud provider, installs the Databricks Runtime, and registers them as executors with the driver." },
    ],
    pitfalls: [
      "Spot/preemptible VMs save money but can be reclaimed mid-job — the driver must rebuild lost shuffle data.",
      "Wrong VM family (memory-bound workload on compute-optimised SKUs) destroys throughput.",
    ],
  },
  workers: {
    eyebrow: "Physical · Compute",
    title: "Worker Nodes & Executors",
    blurb: "Each worker VM runs one or more executor JVMs. Executors hold task slots, on-heap memory and a BlockManager.",
    sections: [
      { h: "The strict memory model",
        p: "1 — Reserved (~300 MB system overhead). 2 — User Memory (25% of remaining): UDF state, user data structures. 3 — Unified Memory (75% of remaining): Execution ⇄ Storage, dynamically rebalanced." },
      { h: "Execution vs Storage",
        p: "Execution memory holds shuffle/sort/aggregation buffers — it can EVICT cached blocks if it needs the room. Storage cannot evict Execution. Cache is a hint, not a guarantee." },
      { h: "Slots = parallelism",
        p: "Slots per executor = `spark.executor.cores`. Each slot runs one task at a time. Total parallelism ≈ `executors × cores`." },
    ],
    pitfalls: [
      "GC pauses > heartbeat interval (10s) → driver marks executor dead → stage retry.",
      "Unified Memory pressure causes Spill to Disk: graceful but 10-100× slower than RAM.",
    ],
  },
  storage: {
    eyebrow: "Physical · Persistence",
    title: "ADLS Gen2",
    blurb: "Azure Data Lake Storage Gen2 — hierarchical-namespace blob storage. Sources for Phase 1 reads, target for Phase 6 writes.",
    sections: [
      { h: "File layout that matters",
        p: "Parquet stripes (row groups) hold min/max stats — that's what enables predicate pushdown. Files of 128 MB – 1 GB hit the sweet spot for both read parallelism and metadata cost." },
      { h: "Delta Lake adds…",
        p: "ACID via `_delta_log` JSON commits, time travel, MERGE/UPSERT, schema evolution, OPTIMIZE for compaction, Z-Order for multi-column locality." },
    ],
    pitfalls: [
      "Many tiny files: every read is a separate HTTPS round-trip + driver-side metadata enumeration.",
      "Lots of partitions × small partitions: combinatorial directory explosion.",
    ],
  },
};

/* ────────────────────────────────────────────────────────────────────────
   Scenario-toggle dossiers (the "real-world extras" panel)
   ──────────────────────────────────────────────────────────────────── */
const SCENARIOS = {
  dataSkew: {
    title: "Data Skew & Spill to Disk",
    icon: Snowflake,
    accent: "rose",
    blurb: "One key value (e.g. NULL or a bot user) ends up in one partition. That task processes orders of magnitude more rows than its peers, exhausts execution memory and spills to disk.",
    bullets: [
      "Symptom: one task in a stage takes 90% of the wall-clock time.",
      "Spill = sort/agg buffers serialised to local SSD. Graceful but 10-100× slower than RAM.",
      "Mitigations: AQE skew-join (auto), key salting, broadcast small side, custom partitioner, isolate hot keys.",
    ],
    code: `# AQE handles it for you on DBR 7.3+
spark.conf.set("spark.sql.adaptive.enabled", true)
spark.conf.set("spark.sql.adaptive.skewJoin.enabled", true)`,
  },
  smallFiles: {
    title: "The Small Files Problem",
    icon: FileWarning,
    accent: "amber",
    blurb: "Writing a DataFrame with 10 000 partitions to ADLS produces 10 000 tiny files. The driver enumerates every one on read; ADLS bills per metadata operation.",
    bullets: [
      "Each file = an HTTPS round-trip + a row-group fetch. Latency dominates throughput.",
      "Over-partitioning at write time (`partitionBy` on a high-cardinality column) is the usual cause.",
      "Fix: `repartition(n)` or `coalesce(n)` before write. On Delta, `OPTIMIZE table ZORDER BY (col)` compacts in place.",
    ],
    code: `# before write
df.repartition(64).write.format("delta").save(path)

# or post-hoc on Delta
spark.sql("OPTIMIZE my_table ZORDER BY (user_id)")`,
  },
  oom: {
    title: "Driver & Executor OOM",
    icon: Skull,
    accent: "red",
    blurb: "Two distinct failure modes with different fixes — confusing them is a classic production mis-diagnosis.",
    bullets: [
      "Driver OOM: usually `.collect()`, `.toPandas()`, or massive broadcast. Fix: don't collect; raise `spark.driver.memory`; broadcast smarter.",
      "Executor OOM: skewed shuffles, fat partitions, leaky UDF state, GC death-spiral. Fix: more partitions, fewer cores per executor (smaller slot pressure), spillable structures.",
      "Lost executor heartbeat = `ExecutorLostFailure` in the driver log — not the same as OOM but often the consequence of a long GC pause.",
    ],
    code: `# don't do this on a billion-row DataFrame
rows = df.collect()   # ← Driver OOM
pdf  = df.toPandas()  # ← Driver OOM`,
  },
  optimizations: {
    title: "Cache & Broadcast",
    icon: Zap,
    accent: "emerald",
    blurb: "Two cheap wins that move work off the critical path.",
    bullets: [
      "`cache()` / `persist()` materialise a DataFrame in Storage Memory — re-used by every subsequent action without recomputation.",
      "Broadcast join: a small table (< `autoBroadcastJoinThreshold`, default 10 MB) is shipped in full to every executor. Skips shuffle entirely.",
      "Use `EXPLAIN` to confirm `BroadcastHashJoin` vs `SortMergeJoin` — and to confirm your cache is actually hit (`InMemoryTableScan`).",
    ],
    code: `from pyspark.sql.functions import broadcast

big.join(broadcast(small), "user_id")
# Phase 3 sees no shuffle for the small side`,
  },
};

/* ────────────────────────────────────────────────────────────────────────
   Geometry helper for connection lines
   ──────────────────────────────────────────────────────────────────── */
const bezier = (x1, y1, x2, y2) => {
  const dx = Math.max(40, Math.abs(x2 - x1) * 0.55);
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
};
const KIND_STROKE = {
  read:    "#5eead4",
  write:   "#fbbf24",
  control: "rgba(180,190,210,0.45)",
  execute: "#f472b6",
};

/* ────────────────────────────────────────────────────────────────────────
   Tiny visual primitives
   ──────────────────────────────────────────────────────────────────── */
const Dot = ({ className = "" }) => (
  <span className={`inline-block w-1.5 h-1.5 rounded-full ${className}`} />
);

const Tag = ({ children, tone = "slate" }) => {
  const tones = {
    slate:   "bg-slate-500/10 text-slate-300 ring-slate-400/20",
    cyan:    "bg-teal-400/10 text-teal-200 ring-teal-300/30",
    amber:   "bg-amber-400/10 text-amber-200 ring-amber-300/30",
    rose:    "bg-rose-400/10 text-rose-200 ring-rose-300/30",
    emerald: "bg-emerald-400/10 text-emerald-200 ring-emerald-300/30",
    red:     "bg-red-500/10 text-red-200 ring-red-400/30",
    indigo:  "bg-indigo-400/10 text-indigo-200 ring-indigo-300/30",
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-mono uppercase tracking-wider ring-1 ${tones[tone]}`}>
      {children}
    </span>
  );
};

const Toggle = ({ on, onClick, icon: Icon, label, accent }) => {
  const accents = {
    rose:    on ? "ring-rose-400/60 bg-rose-500/10 text-rose-100"       : "ring-white/10 text-slate-300 hover:ring-rose-300/30",
    amber:   on ? "ring-amber-400/60 bg-amber-500/10 text-amber-100"    : "ring-white/10 text-slate-300 hover:ring-amber-300/30",
    red:     on ? "ring-red-400/60 bg-red-500/10 text-red-100"          : "ring-white/10 text-slate-300 hover:ring-red-300/30",
    emerald: on ? "ring-emerald-400/60 bg-emerald-500/10 text-emerald-100" : "ring-white/10 text-slate-300 hover:ring-emerald-300/30",
  };
  return (
    <button
      onClick={onClick}
      className={`group flex items-center gap-2 px-3 py-2 rounded-lg ring-1 transition font-mono text-xs uppercase tracking-wider ${accents[accent]}`}
    >
      <span className={`relative inline-flex w-7 h-3.5 rounded-full transition ${on ? "bg-current/30" : "bg-white/5"}`}>
        <span className={`absolute top-0.5 w-2.5 h-2.5 rounded-full bg-current transition-all ${on ? "left-3.5" : "left-0.5 opacity-50"}`} />
      </span>
      <Icon className="w-3.5 h-3.5" />
      {label}
    </button>
  );
};

const WarningBadge = ({ icon: Icon, label, tone = "amber", className = "" }) => {
  const tones = {
    amber:   "bg-amber-500/15 text-amber-200 ring-amber-400/40",
    rose:    "bg-rose-500/15 text-rose-200 ring-rose-400/40",
    red:     "bg-red-500/20 text-red-100 ring-red-400/50 glow-red",
    emerald: "bg-emerald-500/15 text-emerald-200 ring-emerald-400/40",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md ring-1 text-[10px] font-mono uppercase tracking-wider ${tones[tone]} ${className}`}>
      <Icon className="w-3 h-3" />
      {label}
    </span>
  );
};

/* ────────────────────────────────────────────────────────────────────────
   Phase card (left column)
   ──────────────────────────────────────────────────────────────────── */
const PhaseCard = React.forwardRef(({ phase, onClick, scenarios, children, isActive }, ref) => {
  const Icon = phase.icon;
  const accent = phase.accent === "rose" ? "rose" : "cyan";

  return (
    <div
      ref={ref}
      onClick={onClick}
      className={`group relative cursor-pointer transition-all
        bg-gradient-to-br from-white/[0.04] to-white/[0.01]
        ring-1 rounded-xl p-5
        ${isActive ? "ring-teal-300/60 glow-cyan" : "ring-white/10 hover:ring-teal-300/30"}
      `}
    >
      <div className="flex items-start gap-4">
        <div className={`shrink-0 w-12 h-12 rounded-lg flex items-center justify-center ring-1 ${
          accent === "rose"
            ? "bg-rose-500/10 ring-rose-400/30 text-rose-200"
            : "bg-teal-500/10 ring-teal-400/30 text-teal-200"
        }`}>
          <Icon className="w-5 h-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">Phase {phase.num}</span>
            <Dot className="bg-slate-600" />
            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-400">{phase.sub}</span>
          </div>
          <h3 className="font-display text-2xl text-slate-100 leading-tight">{phase.title}</h3>
          {children}
        </div>
        <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-teal-300 group-hover:translate-x-0.5 transition mt-1" />
      </div>
    </div>
  );
});

/* ────────────────────────────────────────────────────────────────────────
   Catalyst sub-pipeline (inside Phase 02)
   ──────────────────────────────────────────────────────────────────── */
const CatalystSubPipeline = () => {
  const stages = [
    { label: "Unresolved", note: "parser" },
    { label: "Catalog",    note: "metastore" },
    { label: "Optimized",  note: "predicate pushdown", highlight: true },
    { label: "Physical",   note: "candidates" },
    { label: "Cost Model", note: "select cheapest" },
  ];
  return (
    <div className="mt-4 -ml-16">
      <div className="grid grid-cols-5 gap-1.5">
        {stages.map((s) => (
          <div
            key={s.label}
            className={`relative rounded-md px-2 py-2 ring-1 ${
              s.highlight
                ? "bg-teal-500/15 ring-teal-400/50 text-teal-100"
                : "bg-white/[0.03] ring-white/10 text-slate-300"
            }`}
          >
            <div className="font-mono text-[10px] uppercase tracking-wider truncate">{s.label}</div>
            <div className="font-mono text-[9px] text-slate-500 truncate">{s.note}</div>
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-md ring-1 ring-amber-400/30 bg-amber-500/10 text-amber-200">
          <Hash className="w-3 h-3" />
          <span className="font-mono text-[10px] uppercase tracking-wider">Photon supported?</span>
        </div>
        <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-wider">
          <span className="px-2 py-1 rounded ring-1 ring-emerald-400/40 bg-emerald-500/10 text-emerald-200">Yes → Photon</span>
          <span className="text-slate-600">/</span>
          <span className="px-2 py-1 rounded ring-1 ring-slate-400/30 bg-slate-500/10 text-slate-300">No → JVM</span>
        </div>
      </div>
    </div>
  );
};

/* ────────────────────────────────────────────────────────────────────────
   DAG Scheduler illustration (Phase 03 inline diagram)
   ──────────────────────────────────────────────────────────────────── */
const StageBoundaryDiagram = ({ broadcast }) => (
  <div className="mt-3 -ml-16 flex items-center gap-1.5 font-mono text-[10px]">
    {[1, 2, 3].map((s, i) => (
      <React.Fragment key={s}>
        <div className="px-2 py-1.5 rounded bg-white/[0.04] ring-1 ring-white/10 text-slate-300">
          <div className="uppercase tracking-wider text-slate-500 text-[9px]">Stage {s}</div>
          <div className="text-slate-200">map · filter · select</div>
        </div>
        {i < 2 && (
          <div className={`flex flex-col items-center ${broadcast && i === 1 ? "opacity-30 line-through" : ""}`}>
            <Snowflake className="w-3 h-3 text-rose-400" />
            <span className="text-rose-300/80 uppercase tracking-wider text-[9px]">shuffle</span>
          </div>
        )}
      </React.Fragment>
    ))}
    {broadcast && (
      <div className="ml-2 flex items-center gap-1 px-2 py-1 rounded ring-1 ring-emerald-400/40 bg-emerald-500/10 text-emerald-200">
        <Radio className="w-3 h-3" />
        <span className="uppercase tracking-wider text-[9px]">broadcast bypass</span>
      </div>
    )}
  </div>
);

/* ────────────────────────────────────────────────────────────────────────
   Execution engines block (Phase 05)
   ──────────────────────────────────────────────────────────────────── */
const EnginesBlock = ({ skew }) => (
  <div className="mt-3 -ml-16 grid grid-cols-2 gap-2">
    <div className="rounded-md ring-1 ring-slate-400/20 bg-slate-500/[0.04] p-2.5">
      <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-slate-300 mb-1">
        <Code2 className="w-3 h-3" /> Tungsten · JVM
      </div>
      <div className="text-[11px] text-slate-400 leading-snug">whole-stage codegen, off-heap, cache-aware</div>
    </div>
    <div className="rounded-md ring-1 ring-amber-400/30 bg-amber-500/[0.06] p-2.5">
      <div className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wider text-amber-200 mb-1">
        <Zap className="w-3 h-3" /> Photon · Native C++
      </div>
      <div className="text-[11px] text-amber-100/70 leading-snug">vectorized SIMD, columnar batches</div>
    </div>

    <div className="col-span-2 mt-1 flex items-center gap-1">
      {[0, 1, 2, 3].map((i) => (
        <div
          key={i}
          className={`relative h-7 flex-1 rounded ring-1 ${
            skew && i === 1
              ? "bg-rose-500/30 ring-rose-400/60 glow-rose"
              : "bg-teal-500/15 ring-teal-400/30"
          }`}
        >
          <span className="absolute inset-0 flex items-center justify-center font-mono text-[10px] text-slate-200/80">
            T{i}
          </span>
          {skew && i === 1 && (
            <span className="absolute -top-2 -right-2 bg-rose-500 text-white text-[9px] font-mono px-1 rounded">SPILL</span>
          )}
        </div>
      ))}
    </div>
    {skew && (
      <div className="col-span-2 -mt-1 font-mono text-[9px] uppercase tracking-wider text-rose-300 flex items-center gap-1">
        <ArrowDown className="w-3 h-3" /> Task 1 overloaded · execution memory full · spill to local SSD
      </div>
    )}
  </div>
);

/* ────────────────────────────────────────────────────────────────────────
   Physical cards (right column)
   ──────────────────────────────────────────────────────────────────── */
const PhysicalCard = React.forwardRef(({ id, title, sub, icon: Icon, onClick, isActive, badges = [], children }, ref) => (
  <div
    ref={ref}
    onClick={onClick}
    className={`group cursor-pointer transition-all relative
      bg-gradient-to-br from-amber-500/[0.04] to-white/[0.01]
      ring-1 rounded-xl p-5
      ${isActive ? "ring-amber-300/60 glow-amber" : "ring-white/10 hover:ring-amber-300/30"}
    `}
  >
    <div className="flex items-start gap-3">
      <div className="shrink-0 w-11 h-11 rounded-lg bg-amber-500/10 ring-1 ring-amber-400/30 text-amber-200 flex items-center justify-center">
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-amber-300/70 mb-0.5">{sub}</div>
        <h3 className="font-display text-xl text-slate-100 leading-tight">{title}</h3>
        {badges.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {badges.map((b, i) => <span key={i}>{b}</span>)}
          </div>
        )}
      </div>
      <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-amber-300 group-hover:translate-x-0.5 transition" />
    </div>
    {children}
  </div>
));

/* ────────────────────────────────────────────────────────────────────────
   Executor memory zoom — the centrepiece of the right column
   ──────────────────────────────────────────────────────────────────── */
const ExecutorMemoryZoom = ({ skew, oom, optimize }) => (
  <div className="mt-4 rounded-lg ring-1 ring-amber-400/20 bg-black/30 p-3 space-y-2">
    <div className="flex items-center justify-between">
      <span className="font-mono text-[10px] uppercase tracking-wider text-amber-300/80 flex items-center gap-1">
        <MemoryStick className="w-3 h-3" /> Executor JVM Heap
      </span>
      {oom && <WarningBadge icon={Skull} label="OOM" tone="red" />}
    </div>

    {/* Reserved 300MB */}
    <div className="rounded ring-1 ring-slate-500/30 bg-slate-500/10 px-2 py-1.5 flex items-center justify-between">
      <span className="font-mono text-[10px] text-slate-400 uppercase tracking-wider">Reserved</span>
      <span className="font-mono text-[10px] text-slate-300">300 MB</span>
    </div>

    {/* User Memory 25% */}
    <div className="rounded ring-1 ring-slate-400/30 bg-slate-400/[0.07] px-2 py-2 flex items-center justify-between">
      <span className="font-mono text-[10px] text-slate-300 uppercase tracking-wider">User Memory</span>
      <span className="font-mono text-[10px] text-slate-300">25%</span>
    </div>

    {/* Unified Memory 75% */}
    <div className="rounded-md ring-1 ring-amber-400/40 bg-amber-500/[0.07] p-2">
      <div className="flex items-center justify-between mb-1.5">
        <span className="font-mono text-[10px] uppercase tracking-wider text-amber-200">Unified Memory</span>
        <span className="font-mono text-[10px] text-amber-200">75%</span>
      </div>

      <div className="h-7 rounded overflow-hidden flex ring-1 ring-amber-400/30">
        <div className={`relative flex-1 flex items-center justify-center font-mono text-[10px] uppercase tracking-wider ${
          skew ? "bg-rose-500/35 text-rose-50" : "bg-rose-500/20 text-rose-100"
        }`}>
          Execution
          {skew && <span className="absolute right-1 text-[9px] pulse-soft">⚠ full</span>}
        </div>
        <div className="w-px bg-amber-400/30" />
        <div className="flex-1 flex items-center justify-center gap-1.5 font-mono text-[10px] uppercase tracking-wider bg-teal-500/20 text-teal-100 relative">
          Storage
          {optimize && <Bookmark className="w-3 h-3 text-emerald-300" />}
        </div>
      </div>
      <div className="mt-1.5 font-mono text-[9px] text-slate-500 flex items-center justify-between">
        <span>← shuffle / sort / agg</span>
        <span>cache · broadcast →</span>
      </div>

      {optimize && (
        <div className="mt-1.5 flex items-center gap-1 font-mono text-[9px] uppercase tracking-wider text-emerald-300">
          <Bookmark className="w-3 h-3" /> df.cache() pinned in storage memory
        </div>
      )}
    </div>

    {/* Slots */}
    <div>
      <div className="font-mono text-[10px] uppercase tracking-wider text-slate-400 mb-1">Task Slots</div>
      <div className="flex gap-1">
        {[0, 1, 2, 3].map((i) => (
          <div
            key={i}
            className={`flex-1 h-5 rounded ring-1 font-mono text-[9px] flex items-center justify-center ${
              skew && i === 1
                ? "bg-rose-500/40 ring-rose-400/60 text-rose-50 glow-rose"
                : "bg-teal-500/20 ring-teal-400/30 text-teal-100"
            }`}
          >
            slot{i}
          </div>
        ))}
      </div>
    </div>
  </div>
);

/* ────────────────────────────────────────────────────────────────────────
   Connection layer (SVG)
   ──────────────────────────────────────────────────────────────────── */
const ConnectionLayer = ({ conns, hovered, hoverItem }) => (
  <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 1 }}>
    <defs>
      {Object.entries(KIND_STROKE).map(([k, c]) => (
        <marker
          key={k}
          id={`arrow-${k}`}
          viewBox="0 0 10 10"
          refX="9" refY="5"
          markerWidth="6" markerHeight="6"
          orient="auto-start-reverse"
        >
          <path d="M 0 0 L 10 5 L 0 10 z" fill={c} />
        </marker>
      ))}
    </defs>
    {conns.map((c, i) => {
      const isHot = hoverItem && (c.from === hoverItem || c.to === hoverItem);
      return (
        <g key={i} opacity={hoverItem && !isHot ? 0.25 : 1}>
          <path
            d={bezier(c.x1, c.y1, c.x2, c.y2)}
            fill="none"
            stroke={KIND_STROKE[c.kind]}
            strokeWidth={isHot ? 2 : 1.25}
            strokeLinecap="round"
            className={c.kind === "execute" || c.kind === "read" ? "line-flow" : ""}
            markerEnd={`url(#arrow-${c.kind})`}
            style={{ transition: "stroke-width 200ms" }}
          />
        </g>
      );
    })}
  </svg>
);

/* ────────────────────────────────────────────────────────────────────────
   Detail drawer
   ──────────────────────────────────────────────────────────────────── */
const DetailDrawer = ({ id, onClose }) => {
  if (!id || !DETAIL[id]) return null;
  const d = DETAIL[id];
  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-xl h-full bg-[#0c0e12] ring-1 ring-white/10 overflow-y-auto scrollbar-tame"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 z-10 px-6 py-4 bg-[#0c0e12]/95 backdrop-blur border-b border-white/5 flex items-start justify-between gap-4">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-teal-300/80 mb-1">{d.eyebrow}</div>
            <h2 className="font-display text-3xl text-slate-50 leading-tight">{d.title}</h2>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-md ring-1 ring-white/10 hover:ring-white/20 hover:bg-white/5 text-slate-400">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="px-6 py-6 space-y-6">
          <p className="text-slate-300 leading-relaxed font-body">{d.blurb}</p>

          {d.sections.map((s, i) => (
            <div key={i} className="space-y-2">
              <div className="flex items-center gap-2">
                <Dot className="bg-teal-400" />
                <h4 className="font-display text-lg text-slate-100">{s.h}</h4>
              </div>
              <p className="text-slate-400 text-sm leading-relaxed pl-3.5">{s.p}</p>
              {s.code && (
                <pre className="ml-3.5 mt-2 p-3 rounded-md bg-black/50 ring-1 ring-white/5 overflow-x-auto scrollbar-tame">
                  <code className="font-mono text-[12px] text-teal-200 leading-relaxed whitespace-pre">{s.code}</code>
                </pre>
              )}
            </div>
          ))}

          {d.pitfalls && (
            <div className="rounded-lg ring-1 ring-rose-400/30 bg-rose-500/[0.06] p-4 space-y-2">
              <div className="flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.2em] text-rose-300">
                <AlertTriangle className="w-3.5 h-3.5" /> Production Pitfalls
              </div>
              <ul className="space-y-1.5 text-sm text-rose-100/85">
                {d.pitfalls.map((p, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="text-rose-400 mt-0.5">→</span>
                    <span>{p}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/* ────────────────────────────────────────────────────────────────────────
   Scenario dossier (footer panel that opens when toggles are flipped)
   ──────────────────────────────────────────────────────────────────── */
const ScenarioDossier = ({ active }) => {
  const ones = Object.entries(active).filter(([, v]) => v).map(([k]) => k);
  if (ones.length === 0) return null;
  return (
    <div className="mt-12 grid md:grid-cols-2 gap-4">
      {ones.map((key) => {
        const s = SCENARIOS[key];
        const Icon = s.icon;
        const tone = s.accent;
        const ring = {
          rose:    "ring-rose-400/40 bg-rose-500/[0.05]",
          amber:   "ring-amber-400/40 bg-amber-500/[0.05]",
          red:     "ring-red-400/50 bg-red-500/[0.06]",
          emerald: "ring-emerald-400/40 bg-emerald-500/[0.05]",
        }[tone];
        return (
          <div key={key} className={`rounded-xl ring-1 ${ring} p-5`}>
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-9 h-9 rounded-md ring-1 flex items-center justify-center ${
                {
                  rose:    "bg-rose-500/15 ring-rose-400/40 text-rose-200",
                  amber:   "bg-amber-500/15 ring-amber-400/40 text-amber-200",
                  red:     "bg-red-500/15 ring-red-400/40 text-red-200",
                  emerald: "bg-emerald-500/15 ring-emerald-400/40 text-emerald-200",
                }[tone]
              }`}>
                <Icon className="w-4 h-4" />
              </div>
              <h3 className="font-display text-2xl text-slate-100">{s.title}</h3>
            </div>
            <p className="text-slate-300/90 text-sm leading-relaxed mb-3">{s.blurb}</p>
            <ul className="space-y-1.5 text-sm text-slate-300/80 mb-3">
              {s.bullets.map((b, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-slate-500 mt-0.5">→</span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>
            {s.code && (
              <pre className="p-3 rounded bg-black/40 ring-1 ring-white/5 overflow-x-auto scrollbar-tame">
                <code className="font-mono text-[12px] text-teal-200 whitespace-pre">{s.code}</code>
              </pre>
            )}
          </div>
        );
      })}
    </div>
  );
};

/* ────────────────────────────────────────────────────────────────────────
   Main App
   ──────────────────────────────────────────────────────────────────── */
export default function App() {
  const [selectedId, setSelectedId] = useState(null);
  const [hoverId, setHoverId] = useState(null);
  const [toggles, setToggles] = useState({
    dataSkew: false,
    smallFiles: false,
    oom: false,
    optimizations: false,
  });

  const containerRef = useRef(null);
  const cardRefs = useRef({});
  const [conns, setConns] = useState([]);

  const setCardRef = (id) => (el) => { if (el) cardRefs.current[id] = el; };

  const recompute = () => {
    if (!containerRef.current) return;
    const cRect = containerRef.current.getBoundingClientRect();
    const list = CONNECTIONS.map((c) => {
      const a = cardRefs.current[c.from];
      const b = cardRefs.current[c.to];
      if (!a || !b) return null;
      const ar = a.getBoundingClientRect();
      const br = b.getBoundingClientRect();
      const x1 = ar.right - cRect.left;
      const y1 = ar.top + ar.height / 2 - cRect.top;
      const x2 = br.left - cRect.left;
      const y2 = br.top + br.height / 2 - cRect.top;
      return { ...c, x1, y1, x2, y2 };
    }).filter(Boolean);
    setConns(list);
  };

  useLayoutEffect(() => {
    recompute();
    const ro = new ResizeObserver(recompute);
    if (containerRef.current) ro.observe(containerRef.current);
    window.addEventListener("scroll", recompute, true);
    return () => {
      ro.disconnect();
      window.removeEventListener("scroll", recompute, true);
    };
  }, []);

  // Recompute when toggles change layout heights
  useEffect(() => { const t = setTimeout(recompute, 50); return () => clearTimeout(t); }, [toggles]);

  const tg = (k) => setToggles((s) => ({ ...s, [k]: !s[k] }));

  return (
    <div className="min-h-screen bg-[#0a0b0e] text-slate-200 font-body relative overflow-x-hidden">
      <style dangerouslySetInnerHTML={{ __html: STYLES }} />

      {/* Atmospheric background */}
      <div className="absolute inset-0 bp-grid opacity-50" />
      <div className="absolute inset-0 bg-gradient-to-b from-teal-500/[0.03] via-transparent to-amber-500/[0.03]" />
      <div className="absolute top-0 left-1/4 w-[40rem] h-[40rem] bg-teal-500/[0.04] rounded-full blur-3xl" />
      <div className="absolute bottom-0 right-1/4 w-[40rem] h-[40rem] bg-amber-500/[0.04] rounded-full blur-3xl" />

      <div className="relative max-w-[1400px] mx-auto px-6 py-10">

        {/* ─── HEADER ────────────────────────────────────────────────── */}
        <header className="mb-10">
          <div className="flex items-center gap-2 mb-3">
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-teal-400/40 to-transparent" />
            <span className="font-mono text-[10px] uppercase tracking-[0.3em] text-teal-300/70 px-3">
              Senior data engineering · reference schematic
            </span>
            <div className="h-px flex-1 bg-gradient-to-r from-transparent via-amber-400/40 to-transparent" />
          </div>
          <h1 className="font-display text-5xl md:text-7xl text-slate-50 leading-[0.95] tracking-tight text-center">
            PySpark Execution
            <span className="italic font-light text-teal-300/90"> Lifecycle </span>
            <span className="text-slate-400">&</span>
            <span className="italic font-light text-amber-300/90"> Architecture</span>
          </h1>
          <p className="mt-4 max-w-3xl mx-auto text-center text-slate-400 leading-relaxed">
            How logical PySpark code becomes physical work on Azure Databricks. Six phases on the left, the hardware on the right,
            wired together — every node clickable, every red flag explainable.
          </p>

          <div className="mt-8 flex items-center justify-center gap-6 font-mono text-[10px] uppercase tracking-wider text-slate-500">
            <div className="flex items-center gap-1.5"><span className="w-3 h-px bg-teal-400" />read</div>
            <div className="flex items-center gap-1.5"><span className="w-3 h-px bg-amber-400" />write</div>
            <div className="flex items-center gap-1.5"><span className="w-3 h-px bg-rose-400" />execute</div>
            <div className="flex items-center gap-1.5"><span className="w-3 h-px bg-slate-500" />control</div>
          </div>
        </header>

        {/* ─── CONTROL BAR ──────────────────────────────────────────── */}
        <div className="mb-8 flex flex-wrap items-center justify-center gap-2">
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500 mr-2">Real-world overlays:</span>
          <Toggle on={toggles.dataSkew}      onClick={() => tg("dataSkew")}      icon={Snowflake}    label="Data Skew & Spill" accent="rose" />
          <Toggle on={toggles.smallFiles}    onClick={() => tg("smallFiles")}    icon={FileWarning}  label="Small Files"      accent="amber" />
          <Toggle on={toggles.oom}           onClick={() => tg("oom")}           icon={Skull}        label="OOM Crashes"      accent="red" />
          <Toggle on={toggles.optimizations} onClick={() => tg("optimizations")} icon={Zap}          label="Cache + Broadcast" accent="emerald" />
        </div>

        {/* ─── SECTION HEADERS ──────────────────────────────────────── */}
        <div className="grid grid-cols-12 gap-6 mb-4">
          <div className="col-span-7 flex items-center gap-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-teal-300/80 flex items-center gap-2">
              <Brain className="w-3.5 h-3.5" /> Logical flow · catalyst territory
            </div>
            <div className="flex-1 h-px bg-gradient-to-r from-teal-400/40 to-transparent" />
          </div>
          <div className="col-span-5 flex items-center gap-3">
            <div className="font-mono text-[10px] uppercase tracking-[0.3em] text-amber-300/80 flex items-center gap-2">
              <HardDrive className="w-3.5 h-3.5" /> Physical infrastructure
            </div>
            <div className="flex-1 h-px bg-gradient-to-r from-amber-400/40 to-transparent" />
          </div>
        </div>

        {/* ─── MAIN DIAGRAM ─────────────────────────────────────────── */}
        <div ref={containerRef} className="relative grid grid-cols-12 gap-6">
          <ConnectionLayer conns={conns} hoverItem={hoverId} />

          {/* LEFT — Logical phases */}
          <div className="col-span-7 space-y-6 relative" style={{ zIndex: 2 }}>

            {/* Phase 1 */}
            <div onMouseEnter={() => setHoverId("p1")} onMouseLeave={() => setHoverId(null)}>
              <PhaseCard
                ref={setCardRef("p1")}
                phase={PHASES[0]}
                onClick={() => setSelectedId("p1")}
                isActive={selectedId === "p1"}
              >
                <div className="mt-3 -ml-16 flex items-center gap-2 flex-wrap">
                  <Tag tone="cyan">transformations · lazy</Tag>
                  <Tag tone="amber">actions · trigger</Tag>
                  <span className="font-mono text-[11px] text-slate-500">→ build lineage graph</span>
                </div>
              </PhaseCard>
            </div>

            {/* Phase 2 — Catalyst with sub-pipeline */}
            <div onMouseEnter={() => setHoverId("p2")} onMouseLeave={() => setHoverId(null)}>
              <PhaseCard
                ref={setCardRef("p2")}
                phase={PHASES[1]}
                onClick={() => setSelectedId("p2")}
                isActive={selectedId === "p2"}
              >
                <CatalystSubPipeline />
              </PhaseCard>
            </div>

            {/* Phase 3 */}
            <div onMouseEnter={() => setHoverId("p3")} onMouseLeave={() => setHoverId(null)}>
              <PhaseCard
                ref={setCardRef("p3")}
                phase={PHASES[2]}
                onClick={() => setSelectedId("p3")}
                isActive={selectedId === "p3"}
              >
                <StageBoundaryDiagram broadcast={toggles.optimizations} />
              </PhaseCard>
            </div>

            {/* Phase 4 */}
            <div onMouseEnter={() => setHoverId("p4")} onMouseLeave={() => setHoverId(null)}>
              <PhaseCard
                ref={setCardRef("p4")}
                phase={PHASES[3]}
                onClick={() => setSelectedId("p4")}
                isActive={selectedId === "p4"}
              >
                <div className="mt-3 -ml-16 flex items-center gap-2 flex-wrap font-mono text-[10px] uppercase tracking-wider">
                  <Tag tone="cyan">PROCESS_LOCAL</Tag>
                  <span className="text-slate-600">›</span>
                  <Tag tone="cyan">NODE_LOCAL</Tag>
                  <span className="text-slate-600">›</span>
                  <Tag tone="slate">RACK_LOCAL</Tag>
                  <span className="text-slate-600">›</span>
                  <Tag tone="slate">ANY</Tag>
                </div>
              </PhaseCard>
            </div>

            {/* Phase 5 — Execution (with skew overlay) */}
            <div onMouseEnter={() => setHoverId("p5")} onMouseLeave={() => setHoverId(null)}>
              <PhaseCard
                ref={setCardRef("p5")}
                phase={PHASES[4]}
                onClick={() => setSelectedId("p5")}
                isActive={selectedId === "p5"}
              >
                {toggles.dataSkew && (
                  <div className="absolute -top-2 -right-2 z-10">
                    <WarningBadge icon={Snowflake} label="Skew" tone="rose" />
                  </div>
                )}
                <EnginesBlock skew={toggles.dataSkew} />
              </PhaseCard>
            </div>

            {/* Phase 6 — Write (with small files overlay) */}
            <div onMouseEnter={() => setHoverId("p6")} onMouseLeave={() => setHoverId(null)}>
              <PhaseCard
                ref={setCardRef("p6")}
                phase={PHASES[5]}
                onClick={() => setSelectedId("p6")}
                isActive={selectedId === "p6"}
              >
                {toggles.smallFiles && (
                  <div className="absolute -top-2 -right-2 z-10">
                    <WarningBadge icon={FileWarning} label="Small files" tone="amber" />
                  </div>
                )}
                <div className="mt-3 -ml-16 flex items-center gap-2 flex-wrap">
                  <Tag tone="amber">parquet</Tag>
                  <Tag tone="emerald">delta · ACID</Tag>
                  <Tag tone="slate">commit protocol</Tag>
                </div>
              </PhaseCard>
            </div>
          </div>

          {/* RIGHT — Physical infrastructure */}
          <div className="col-span-5 space-y-6 relative" style={{ zIndex: 2 }}>

            {/* Driver */}
            <div onMouseEnter={() => setHoverId("driver")} onMouseLeave={() => setHoverId(null)}>
              <PhysicalCard
                ref={setCardRef("driver")}
                id="driver"
                title={PHYSICAL[0].title}
                sub={PHYSICAL[0].sub}
                icon={PHYSICAL[0].icon}
                onClick={() => setSelectedId("driver")}
                isActive={selectedId === "driver"}
                badges={[
                  <Tag key="a" tone="cyan">SparkContext</Tag>,
                  <Tag key="b" tone="cyan">Catalyst</Tag>,
                  <Tag key="c" tone="cyan">DAGScheduler</Tag>,
                  <Tag key="d" tone="cyan">TaskScheduler</Tag>,
                ]}
              >
                {toggles.oom && (
                  <div className="absolute -top-2 -right-2 z-10">
                    <WarningBadge icon={Skull} label="Driver OOM · .collect()" tone="red" />
                  </div>
                )}
                <div className="mt-3 font-mono text-[11px] text-slate-400/80 leading-relaxed">
                  Hosts every coordination service. Connects to phases 01–04. SPOF for the application.
                </div>
              </PhysicalCard>
            </div>

            {/* Cluster Manager */}
            <div onMouseEnter={() => setHoverId("cm")} onMouseLeave={() => setHoverId(null)}>
              <PhysicalCard
                ref={setCardRef("cm")}
                id="cm"
                title={PHYSICAL[1].title}
                sub={PHYSICAL[1].sub}
                icon={PHYSICAL[1].icon}
                onClick={() => setSelectedId("cm")}
                isActive={selectedId === "cm"}
                badges={[
                  <Tag key="a" tone="amber">Databricks</Tag>,
                  <Tag key="b" tone="slate">YARN</Tag>,
                  <Tag key="c" tone="slate">K8s</Tag>,
                ]}
              >
                <div className="mt-3 font-mono text-[11px] text-slate-400/80 leading-relaxed">
                  Allocates executors. Dynamic scaling. Connects to phase 04.
                </div>
              </PhysicalCard>
            </div>

            {/* Workers + Executor zoom */}
            <div onMouseEnter={() => setHoverId("workers")} onMouseLeave={() => setHoverId(null)}>
              <PhysicalCard
                ref={setCardRef("workers")}
                id="workers"
                title={PHYSICAL[2].title}
                sub={PHYSICAL[2].sub}
                icon={PHYSICAL[2].icon}
                onClick={() => setSelectedId("workers")}
                isActive={selectedId === "workers"}
                badges={[
                  <Tag key="a" tone="amber">JVM</Tag>,
                  <Tag key="b" tone="rose">Tungsten</Tag>,
                  <Tag key="c" tone="emerald">Photon</Tag>,
                ]}
              >
                {toggles.oom && (
                  <div className="absolute -top-2 -right-2 z-10">
                    <WarningBadge icon={Skull} label="Executor OOM · GC" tone="red" />
                  </div>
                )}
                <ExecutorMemoryZoom
                  skew={toggles.dataSkew}
                  oom={toggles.oom}
                  optimize={toggles.optimizations}
                />
              </PhysicalCard>
            </div>

            {/* Storage */}
            <div onMouseEnter={() => setHoverId("storage")} onMouseLeave={() => setHoverId(null)}>
              <PhysicalCard
                ref={setCardRef("storage")}
                id="storage"
                title={PHYSICAL[3].title}
                sub={PHYSICAL[3].sub}
                icon={PHYSICAL[3].icon}
                onClick={() => setSelectedId("storage")}
                isActive={selectedId === "storage"}
                badges={[
                  <Tag key="a" tone="amber">parquet</Tag>,
                  <Tag key="b" tone="emerald">delta lake</Tag>,
                  <Tag key="c" tone="slate">HNS blob</Tag>,
                ]}
              >
                {toggles.smallFiles && (
                  <div className="absolute -top-2 -right-2 z-10">
                    <WarningBadge icon={FileWarning} label="Metadata storm" tone="amber" />
                  </div>
                )}
                <div className="mt-3 font-mono text-[11px] text-slate-400/80 leading-relaxed">
                  Read at phase 01. Write at phase 06. Predicate pushdown lives or dies on row-group stats.
                </div>
              </PhysicalCard>
            </div>
          </div>
        </div>

        {/* ─── SCENARIO DOSSIER ────────────────────────────────────── */}
        <ScenarioDossier active={toggles} />

        {/* ─── FOOTER ──────────────────────────────────────────────── */}
        <footer className="mt-16 pt-6 border-t border-white/5 grid md:grid-cols-3 gap-6">
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-2">Mental model</div>
            <p className="font-display text-lg text-slate-300 italic leading-snug">
              "Catalyst is the brain. Tungsten + Photon are the muscle. Everything in between is plumbing — and the plumbing is where production breaks."
            </p>
          </div>
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-2">When something is slow</div>
            <ol className="space-y-1 text-sm text-slate-400">
              <li><span className="text-teal-400 font-mono">1.</span> Look at the Spark UI stages — find the long one.</li>
              <li><span className="text-teal-400 font-mono">2.</span> Long stage with one slow task → skew.</li>
              <li><span className="text-teal-400 font-mono">3.</span> Many short stages → too many shuffles.</li>
              <li><span className="text-teal-400 font-mono">4.</span> Small task durations → over-partitioned.</li>
            </ol>
          </div>
          <div>
            <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500 mb-2">First place to read</div>
            <ul className="space-y-1 text-sm text-slate-400 font-mono">
              <li>· EXPLAIN FORMATTED</li>
              <li>· Spark UI · SQL tab</li>
              <li>· Spark UI · Stages tab (skew detector)</li>
              <li>· Executor logs · GC time</li>
            </ul>
          </div>
        </footer>
      </div>

      <DetailDrawer id={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}