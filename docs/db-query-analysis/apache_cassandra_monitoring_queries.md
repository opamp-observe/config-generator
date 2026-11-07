<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0. See license.txt in the project root.
-->

# Apache Cassandra monitoring CQL: latency, thread pools, storage and internal logs

## Scope and interpretation

Scope: Apache Cassandra 4.0, 4.1 and 5.0. Cassandra 4.0 introduced node-local virtual tables under `system_views`. Later releases add tables and columns, so discover the schema on each supported version before fixing a collector projection.

These are operational CQL query patterns assembled from Apache Cassandra's documented system and virtual tables. Cassandra is not an OLTP SQL server: it does not expose a general list of executing CQL statements, row-lock blockers or durable query history through CQL. JMX, `nodetool`, metrics reporters, application-driver telemetry and logs remain first-class monitoring interfaces.

## What can be retrieved entirely through CQL?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Node identity and runtime settings | `system.local`, `system_views.settings` | Each query describes the contacted node. |
| Connected clients | `system_views.clients` | Connections, not currently executing statements. |
| Read/write latency and rates | latency virtual tables | Node-local rolling metrics, not per-request history. |
| Thread-pool backlog | `system_views.thread_pools` | Node-local; blocked/pending work needs workload context. |
| Table disk and partition indicators | `disk_usage`, `max_partition_size`, tombstone/row metrics | Estimates/metrics; not filesystem free space. |
| Current compaction/SSTable work | `system_views.sstable_tasks` | Current tasks only. |
| Internode messaging pressure | `internode_inbound`, `internode_outbound` | Node-local counters/gauges. |
| Selected traced request | `system_traces.sessions`, `system_traces.events` | Only explicitly/sampled traced requests, TTL-limited and high overhead. |
| Internal logs | `system_views.system_logs` with `CQLLOG` appender | Configuration and version dependent; not a default universal log table. |

“Entirely through CQL” does not imply cluster-wide data. Virtual tables are local, read-only, unreplicated and ignore consistency level. Query every node directly and attach node identity to each sample. [Virtual tables](https://cassandra.apache.org/doc/latest/cassandra/managing/operating/virtualtables.html).

## Prerequisites and collection rules

Use a dedicated role with `SELECT` on only the required system/virtual tables. CQL authorization configuration varies; verify that restricting system keyspaces does not break driver discovery. Protect client addresses, user names, trace parameters and log messages.

Connect directly to every node for virtual-table collection. Do not send these queries through a load-balanced session and assume one response represents the cluster. Store `host_id`, address, data center, rack, release version and collector timestamp. Cassandra metrics are node-local; aggregate only after preserving those dimensions.

Counters and rolling rates have different semantics. Difference cumulative counts only across continuous node uptime. Histograms expose recent quantiles plus counts and can reset at restart. Do not average per-node percentiles to obtain a cluster percentile. CQL queries against virtual tables can themselves consume resources; keep projections and cadence bounded.

## Compatibility matrix

**Y** = available from the documented 4.x virtual-table baseline. **V** = validate table/columns on the exact version. **L** = log appender required. **T** = request tracing required.

| Query name | 4.0 | 4.1 | 5.0 |
| --- | --- | --- | --- |
| Q01 Node identity and settings | Y | Y | Y |
| Q02 Connected clients | Y | Y | Y |
| Q03 Thread-pool backlog | Y | Y | Y |
| Q04 Coordinator read latency | Y | Y | Y |
| Q05 Coordinator write latency | Y | Y | Y |
| Q06 Local read/write latency | Y | Y | Y |
| Q07 Scan pressure | Y | Y | Y |
| Q08 Tombstones and rows per read | Y | Y | Y |
| Q09 Maximum partition size | Y | Y | Y |
| Q10 Table disk usage | Y | Y | Y |
| Q11 Cache health | Y | Y | Y |
| Q12 Current SSTable tasks | Y | Y | Y |
| Q13 Internode messaging | Y | Y | Y |
| Q14 Schema agreement | Y | Y | Y |
| Q15 Compaction history | Y | Y | Y |
| Q16 Selected trace | T | T | T |
| Q17 CQL-accessible server logs | V/L | V/L | L |

The latest-version documentation lists the full current virtual-table set; additions are not automatically backported. Use `SELECT * FROM system_virtual_schema.tables WHERE keyspace_name = 'system_views';` and the columns query before deployment.

## Query catalogue

### Q01 — Node identity and settings

```sql
SELECT cluster_name,
       data_center,
       rack,
       host_id,
       listen_address,
       native_protocol_version,
       partitioner,
       release_version,
       cql_version,
       schema_version
FROM system.local;

SELECT name, value
FROM system_views.settings
WHERE name IN ('cluster_name', 'num_tokens', 'partitioner',
               'concurrent_reads', 'concurrent_writes',
               'concurrent_compactors', 'compaction_throughput',
               'slow_query_log_timeout');
```

Run directly on each node at startup/reconnection. Setting names evolve; absent rows mean unsupported/renamed, not a zero setting.

### Q02 — Connected clients

```sql
SELECT address,
       port,
       hostname,
       username,
       connection_stage,
       driver_name,
       driver_version,
       protocol_version,
       request_count,
       ssl_enabled,
       ssl_protocol
FROM system_views.clients;
```

This lists connections, not active requests. Use it to find obsolete drivers/protocols, unexpected plaintext connections and high request-count connections. Request count is cumulative for the connection. Source: [clients virtual table](https://cassandra.apache.org/doc/latest/cassandra/managing/operating/virtualtables.html#clients-virtual-table).

### Q03 — Thread-pool backlog

```sql
SELECT name,
       active_tasks,
       active_tasks_limit,
       pending_tasks,
       completed_tasks,
       blocked_tasks,
       blocked_tasks_all_time
FROM system_views.thread_pools;
```

Sustained pending work and rising blocked counts are stronger signals than a single sample. Difference `completed_tasks` and `blocked_tasks_all_time` across continuous uptime.

### Q04 — Coordinator read latency

```sql
SELECT keyspace_name,
       table_name,
       count,
       per_second,
       p50th_ms,
       p99th_ms,
       max_ms
FROM system_views.coordinator_read_latency;
```

These are coordinator-side metrics on the contacted node. Do not average `p99th_ms` across nodes. Retain the count to assess whether a percentile has meaningful traffic.

### Q05 — Coordinator write latency

```sql
SELECT keyspace_name,
       table_name,
       count,
       per_second,
       p50th_ms,
       p99th_ms,
       max_ms
FROM system_views.coordinator_write_latency;
```

Coordinator latency includes consistency-level and replica behavior. Correlate with local latency and internode metrics.

### Q06 — Local read/write latency

```sql
SELECT keyspace_name, table_name, count, per_second,
       p50th_ms, p99th_ms, max_ms
FROM system_views.local_read_latency;

SELECT keyspace_name, table_name, count, per_second,
       p50th_ms, p99th_ms, max_ms
FROM system_views.local_write_latency;
```

Local and coordinator latency answer different questions. High coordinator latency with normal local latency can point to remote replicas, consistency, queueing or network behavior.

### Q07 — Scan pressure

```sql
SELECT keyspace_name,
       table_name,
       count,
       per_second,
       p50th_ms,
       p99th_ms,
       max_ms
FROM system_views.coordinator_scan;

SELECT keyspace_name,
       table_name,
       count,
       per_second,
       p50th_ms,
       p99th_ms,
       max_ms
FROM system_views.local_scan;
```

Scans are workload-dependent and not automatically faults. Unexpected scan rate or latency can reveal access patterns that do not fit the data model.

### Q08 — Tombstones and rows per read

```sql
SELECT keyspace_name, table_name, count, median, max
FROM system_views.tombstones_per_read;

SELECT keyspace_name, table_name, count, median, max
FROM system_views.rows_per_read;
```

Tombstone and row counts are distributions, not exact per-query logs. Investigate sustained high values with application query shape, TTL/deletion policy and compaction strategy.

### Q09 — Maximum partition size

```sql
SELECT keyspace_name,
       table_name,
       max_partition_size,
       max_partition_key
FROM system_views.max_partition_size;
```

Large partitions can cause latency, repair, streaming and compaction problems. The metric records an observed maximum, not a complete partition inventory; column names should be verified on the exact version.

### Q10 — Table disk usage

```sql
SELECT keyspace_name,
       table_name,
       mebibytes
FROM system_views.disk_usage;
```

This is table data usage reported by Cassandra, not filesystem capacity. Query every node and do not sum replicas unless the intended metric is physical replicated footprint.

### Q11 — Cache health

```sql
SELECT name,
       capacity_bytes,
       size_bytes,
       entry_count,
       request_count,
       hit_count,
       hit_ratio,
       recent_request_rate_per_second,
       recent_hit_rate_per_second
FROM system_views.caches;
```

A cache with zero configured capacity is disabled, not unhealthy. Use recent and lifetime fields according to their documented semantics.

### Q12 — Current SSTable tasks

```sql
SELECT keyspace_name,
       table_name,
       task_id,
       kind,
       progress,
       total,
       unit
FROM system_views.sstable_tasks;
```

This includes current compaction/upgrade-style tasks. `progress / total` is task progress, not completion time. Empty results do not prove the compaction backlog is empty; use compaction-pending metrics via JMX/reporters as well.

### Q13 — Internode messaging

```sql
SELECT * FROM system_views.internode_inbound;
SELECT * FROM system_views.internode_outbound;
```

Before production ingestion, replace `*` with the columns exposed by the target version. Monitor error, expired, pending/reserve, throttling and byte/count fields per remote endpoint. The virtual-table schema has evolved and is best discovered locally.

### Q14 — Schema agreement

```sql
SELECT schema_version FROM system.local;
SELECT peer, peer_port, data_center, rack, host_id, schema_version
FROM system.peers_v2;
```

Compare schema versions across all live nodes. Rows in `peers_v2` are each node's local peer view and do not replace gossip/live-node checks. A matching UUID indicates agreement on schema version, not overall cluster health.

### Q15 — Compaction history

```sql
SELECT id,
       keyspace_name,
       columnfamily_name,
       compacted_at,
       bytes_in,
       bytes_out,
       rows_merged
FROM system.compaction_history;
```

This is bounded local history. It does not expose current pending tasks; combine with Q12 and compaction metrics.

## Internal server logs and historical events

### Recommended logging baseline

Collect `system.log`, `debug.log` where enabled, garbage-collector logs and audit/FQL artifacts externally from every node with rotation and access controls. `slow_query_log_timeout` reports slow queries to logs but does not create a durable SQL query-history table. Full Query Logging is a bounded diagnostic feature that writes binary log segments for replay/analysis and must be capacity planned. [Full Query Logging](https://cassandra.apache.org/doc/latest/cassandra/managing/operating/fqllogging.html).

### Q16 — Selected request trace

After enabling tracing for a specific request and retaining its returned session UUID:

```sql
SELECT session_id,
       request,
       started_at,
       duration,
       coordinator,
       parameters
FROM system_traces.sessions
WHERE session_id = :trace_session_id;

SELECT session_id,
       event_id,
       activity,
       source,
       source_elapsed,
       thread
FROM system_traces.events
WHERE session_id = :trace_session_id;
```

Tracing adds overhead and trace rows expire. Trace only bounded requests or use a carefully chosen probability; never scan `system_traces` as a general history store. The `:trace_session_id` placeholder is supplied by the client.

### Q17 — CQL-accessible server logs

When `CQLLOG` is configured in `logback.xml` and the virtual table exists:

```sql
SELECT *
FROM system_views.system_logs
LIMIT 500;
```

Discover the exact primary key and columns first, then add a bounded key/time predicate appropriate to that version. The `system_logs` table is the exception to some implicit virtual-table filtering behavior and is not a substitute for complete external log collection.

## Deeper diagnosis and rollout

Use driver request metrics and query execution profiles to identify the exact prepared statement, consistency level, coordinator, retries/speculative executions and application latency. Cassandra deliberately does not expose arbitrary in-flight CQL text as a node-wide SQL process list.

Suggested rollout:

1. Connect directly to every node and capture Q01 plus the virtual-table schema.
2. Poll Q02–Q06 every 15–30 seconds, preserving node and table identity.
3. Collect Q07–Q13 every 30–60 seconds and aggregate only after node-level storage.
4. Check Q14 after schema changes/deployments and Q15 during compaction incidents.
5. Export the documented JMX metrics in parallel; Cassandra metrics are explicitly designed for JMX, virtual tables or reporters. [Monitoring metrics](https://cassandra.apache.org/doc/latest/cassandra/managing/operating/metrics.html).
6. Use Q16 for targeted traces and Q17 only when its log appender and retention are intentionally configured.
7. Validate table names, columns, histogram semantics and collector overhead against each exact release.

CQL-only monitoring cannot establish node liveness, ring ownership, repair health, filesystem free space, JVM/GC health or complete request history. Keep `nodetool`, JMX/reporters, logs, driver telemetry and host metrics in the monitoring design.
