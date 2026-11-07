<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0. See license.txt in the project root.
-->

# ClickHouse monitoring SQL: performance, slow queries, merges, replication and internal logs

## Scope and interpretation

Scope: self-managed ClickHouse 25.3 LTS, 25.8 LTS, 26.3 LTS and 26.8 LTS, with notes for ClickHouse Cloud. The queries use documented system tables common to these release families. Confirm columns with `DESCRIBE TABLE` on the exact build because ClickHouse adds observability fields frequently.

These are operational query patterns assembled from ClickHouse's documented interfaces. Thresholds, retention and polling intervals are recommendations to tune locally. A successful query against one replica does not establish cluster-wide health.

## What can be retrieved entirely through SQL?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Queries running slowly now | `system.processes` | Node-local current state; completed work disappears. |
| Historical slow or failed queries | `system.query_log` | Requires query logging, retention and a flushed log record. |
| Current merges and mutations | `system.merges`, `system.mutations` | Node-local state; poll every relevant replica. |
| Workload and resource counters | `system.events`, `system.metrics`, `system.asynchronous_metrics` | Mixed cumulative counters and gauges; semantics differ. |
| Table-part and disk pressure | `system.parts`, `system.disks`, `system.detached_parts` | SQL does not replace host/filesystem monitoring. |
| Replication lag and queue failures | `system.replicas`, `system.replication_queue` | Only replicated table engines; results are local to the queried server. |
| Internal warnings and errors | `system.text_log`, `system.error_log` | Availability and retention depend on server configuration and service restrictions. |

“Entirely through SQL” means accessible through a ClickHouse connection. Most system tables are local. On self-managed clusters, query each replica or use a deliberately configured `clusterAllReplicas` call. In ClickHouse Cloud, persistent `_log` system tables are replica-local; use the service's documented all-replica pattern where permitted.

## Prerequisites and collection rules

Use a dedicated read-only account with access only to the required system tables. Access to query text, stack traces and log messages is sensitive because literals can contain application data. Do not give a monitoring account `KILL QUERY`, DDL, mutation or configuration privileges.

Record `hostName()`, `version()`, server uptime, cluster/service identity and sample time with every sample. For cluster queries, preserve the source host instead of aggregating first. `system.events` counters are cumulative since process start; calculate rates as `delta(value) / elapsed_seconds` and discard deltas across restarts or counter decreases. `system.metrics` and `system.asynchronous_metrics` are gauges and should not be differenced.

System log tables are normally populated asynchronously. `SYSTEM FLUSH LOGS` is an administrative action and should not be issued on every poll. Query windows with overlap and deduplicate by host plus stable event identity such as `query_id`, event time and log type. Distributed queries can create coordinator and child records; use `is_initial_query` and `initial_query_id` deliberately.

The examples use a five-second slow-query threshold and one-hour history window. Use UTC in the collector, and store both `event_time` and `event_time_microseconds` when the latter is available. Query log retention is controlled by the table TTL/configuration, not by the queries below.

## Compatibility matrix

**Y** = common documented interface. **C** = configuration-dependent log table. **R** = replicated-engine context. No cell promises cloud permission or identical columns on every patch release.

| Query name | 25.3 LTS | 25.8 LTS | 26.3 LTS | 26.8 LTS |
| --- | --- | --- | --- | --- |
| Q01 Environment and configuration | Y | Y | Y | Y |
| Q02 Active slow queries | Y | Y | Y | Y |
| Q03 Activity summary | Y | Y | Y | Y |
| Q04 Historical slow queries | C | C | C | C |
| Q05 Expensive query patterns | C | C | C | C |
| Q06 Query-log collection health | C | C | C | C |
| Q07 Workload counters | Y | Y | Y | Y |
| Q08 Current and asynchronous metrics | Y | Y | Y | Y |
| Q09 Memory tracking | Y | Y | Y | Y |
| Q10 Table storage and active parts | Y | Y | Y | Y |
| Q11 Part-count pressure | Y | Y | Y | Y |
| Q12 Current merges | Y | Y | Y | Y |
| Q13 Pending or failed mutations | Y | Y | Y | Y |
| Q14 Part lifecycle failures | C | C | C | C |
| Q15 Disk capacity | Y | Y | Y | Y |
| Q16 Cache effectiveness | Y | Y | Y | Y |
| Q17 Replica health | R | R | R | R |
| Q18 Replication queue | R | R | R | R |
| Q19 Distributed-send queue | Y | Y | Y | Y |
| Q20 Internal text log | C | C | C | C |
| Q21 Error counters | Y | Y | Y | Y |

ClickHouse 26.8 adds `system.user_query_log`, which permits a user to inspect its own history without broad `system.query_log` access. Keep the common queries below on `system.query_log`; use the narrower table on 26.8+ when it meets the collector's scope. [26.8 release notes](https://clickhouse.com/blog/clickHouse-release-26-08).

## Query catalogue

### Q01 — Environment and configuration

```sql
SELECT hostName() AS host_name,
       version() AS server_version,
       timezone() AS server_timezone,
       uptime() AS uptime_seconds,
       now64(3) AS sampled_at;

SELECT name, value, changed, description
FROM system.settings
WHERE name IN ('log_queries', 'log_queries_min_type',
               'log_queries_min_query_duration_ms',
               'max_concurrent_queries', 'max_memory_usage',
               'max_threads', 'max_execution_time')
ORDER BY name;
```

Run at startup/reconnection and after configuration changes. Settings can vary by user/profile and a session override may differ from the server default. Source: [system settings](https://clickhouse.com/docs/operations/system-tables/settings).

### Q02 — Active slow queries

```sql
SELECT hostName() AS host_name,
       query_id,
       initial_query_id,
       user,
       elapsed,
       read_rows,
       read_bytes,
       written_rows,
       written_bytes,
       memory_usage,
       peak_memory_usage,
       query
FROM system.processes
WHERE elapsed >= 5
  AND query_id != currentQueryID()
ORDER BY elapsed DESC
LIMIT 100;
```

`elapsed` is current wall-clock age. A distributed statement may have work on several nodes, so preserve `initial_query_id`. This is observation only; do not automate `KILL QUERY` from duration alone. Source: [`system.processes`](https://clickhouse.com/docs/operations/system-tables/processes).

### Q03 — Activity summary

```sql
SELECT hostName() AS host_name,
       user,
       count() AS running_queries,
       sum(memory_usage) AS current_memory_bytes,
       sum(read_bytes) AS bytes_read_so_far,
       max(elapsed) AS oldest_query_seconds
FROM system.processes
WHERE query_id != currentQueryID()
GROUP BY host_name, user
ORDER BY current_memory_bytes DESC;
```

This is a point-in-time summary, not concurrency over an interval. Short queries between polls are absent.

### Q04 — Historical slow queries

```sql
SELECT hostName() AS host_name,
       event_time_microseconds,
       query_id,
       initial_query_id,
       user,
       query_kind,
       query_duration_ms,
       read_rows,
       read_bytes,
       written_rows,
       written_bytes,
       result_rows,
       memory_usage,
       exception_code,
       exception,
       query
FROM system.query_log
WHERE event_time >= now() - INTERVAL 1 HOUR
  AND type IN ('QueryFinish', 'ExceptionWhileProcessing')
  AND is_initial_query = 1
  AND query_duration_ms >= 5000
ORDER BY event_time_microseconds DESC
LIMIT 200;
```

`QueryFinish` records completion; exceptions can have a different set of final counters. Query text can contain secrets. Logging can sample or omit short work depending on settings. Source: [`system.query_log`](https://clickhouse.com/docs/operations/system-tables/query_log).

### Q05 — Expensive query patterns

```sql
SELECT normalized_query_hash,
       any(query_kind) AS query_kind,
       count() AS executions,
       round(avg(query_duration_ms), 2) AS mean_duration_ms,
       quantileTDigest(0.95)(query_duration_ms) AS p95_duration_ms,
       sum(read_bytes) AS total_read_bytes,
       sum(written_bytes) AS total_written_bytes,
       max(memory_usage) AS maximum_memory_bytes,
       any(query) AS example_query
FROM system.query_log
WHERE event_time >= now() - INTERVAL 1 HOUR
  AND type = 'QueryFinish'
  AND is_initial_query = 1
GROUP BY normalized_query_hash
ORDER BY total_read_bytes DESC
LIMIT 50;
```

The normalized hash groups structurally similar text but is not a permanent cross-version application identifier. Rank by total cost and tail latency separately.

### Q06 — Query-log collection health

```sql
SELECT min(event_time) AS oldest_event,
       max(event_time) AS newest_event,
       count() AS retained_records,
       countIf(type = 'QueryFinish') AS completed_records,
       countIf(type IN ('ExceptionBeforeStart', 'ExceptionWhileProcessing'))
         AS exception_records
FROM system.query_log;

SELECT name, value, changed
FROM system.settings
WHERE name LIKE 'log_queries%'
ORDER BY name;
```

A recent maximum timestamp does not prove completeness. Check retention, sampling, server restarts and every replica.

### Q07 — Workload counters

```sql
SELECT hostName() AS host_name, event, value, description
FROM system.events
WHERE event IN ('Query', 'SelectQuery', 'InsertQuery', 'FailedQuery',
                'ReadBufferFromFileDescriptorReadBytes',
                'WriteBufferFromFileDescriptorWriteBytes',
                'OSReadBytes', 'OSWriteBytes')
ORDER BY event;
```

Difference these counters between validated samples. Event availability can vary by build; missing rows should be reported as unsupported, not zero. Source: [`system.events`](https://clickhouse.com/docs/operations/system-tables/events).

### Q08 — Current and asynchronous metrics

```sql
SELECT metric, value, description
FROM system.metrics
WHERE metric IN ('Query', 'Merge', 'Mutation', 'ReplicatedFetch',
                 'ReplicatedSend', 'MemoryTracking', 'TCPConnection')
ORDER BY metric;

SELECT metric, value, description
FROM system.asynchronous_metrics
WHERE metric IN ('LoadAverage1', 'OSCPUWaitMicroseconds',
                 'OSCPUVirtualTimeMicroseconds', 'MemoryResident',
                 'MemoryAvailable', 'FilesystemMainPathUsedBytes',
                 'FilesystemMainPathAvailableBytes')
ORDER BY metric;
```

These are gauges sampled or calculated at different cadences. Do not treat all values as synchronized. Sources: [`system.metrics`](https://clickhouse.com/docs/operations/system-tables/metrics), [`system.asynchronous_metrics`](https://clickhouse.com/docs/operations/system-tables/asynchronous_metrics).

### Q09 — Memory tracking

```sql
SELECT user,
       count() AS running_queries,
       sum(memory_usage) AS tracked_current_memory_bytes,
       max(peak_memory_usage) AS largest_query_peak_memory_bytes
FROM system.processes
WHERE query_id != currentQueryID()
GROUP BY user
ORDER BY tracked_current_memory_bytes DESC;
```

Use this with the `MemoryTracking` metric from Q08. Allocator overhead, caches and process RSS need not equal the sum of query trackers, and completed queries disappear from this live view. Source: [`system.processes`](https://clickhouse.com/docs/operations/system-tables/processes).

### Q10 — Table storage and active parts

```sql
SELECT database,
       table,
       sum(rows) AS rows,
       sum(bytes_on_disk) AS bytes_on_disk,
       count() AS active_parts,
       min(min_date) AS oldest_partition_date,
       max(max_date) AS newest_partition_date
FROM system.parts
WHERE active
GROUP BY database, table
ORDER BY bytes_on_disk DESC
LIMIT 100;
```

Rows and bytes are part metadata, not a transactionally frozen table count. Date fields are meaningful only for engines/partition keys that populate them. Source: [`system.parts`](https://clickhouse.com/docs/operations/system-tables/parts).

### Q11 — Part-count pressure

```sql
SELECT database,
       table,
       partition,
       count() AS active_parts,
       sum(rows) AS rows,
       sum(bytes_on_disk) AS bytes_on_disk
FROM system.parts
WHERE active
GROUP BY database, table, partition
HAVING active_parts >= 100
ORDER BY active_parts DESC
LIMIT 100;
```

The threshold is a triage example. High counts can increase planning and merge pressure; the correct limit depends on ingest shape and table settings.

### Q12 — Current merges

```sql
SELECT database,
       table,
       elapsed,
       progress,
       num_parts,
       total_size_bytes_compressed,
       bytes_read_uncompressed,
       bytes_written_uncompressed,
       memory_usage,
       result_part_name
FROM system.merges
ORDER BY elapsed DESC;
```

This includes current merge/mutation work only. `progress` is an estimate and a restarted merge is a new observation. Source: [`system.merges`](https://clickhouse.com/docs/operations/system-tables/merges).

### Q13 — Pending or failed mutations

```sql
SELECT database,
       table,
       mutation_id,
       command,
       create_time,
       parts_to_do,
       is_done,
       latest_failed_part,
       latest_fail_time,
       latest_fail_reason
FROM system.mutations
WHERE NOT is_done OR latest_fail_time IS NOT NULL
ORDER BY create_time;
```

Mutations are asynchronous and can be expensive. Do not cancel or retry automatically from this result. Source: [`system.mutations`](https://clickhouse.com/docs/operations/system-tables/mutations).

### Q14 — Part lifecycle failures

```sql
SELECT event_time,
       database,
       table,
       event_type,
       part_name,
       rows,
       size_in_bytes,
       error,
       exception
FROM system.part_log
WHERE event_time >= now() - INTERVAL 1 HOUR
  AND (error != 0 OR exception != '')
ORDER BY event_time DESC
LIMIT 200;
```

`system.part_log` is configuration-dependent and local. Source: [`system.part_log`](https://clickhouse.com/docs/operations/system-tables/part_log).

### Q15 — Disk capacity

```sql
SELECT name,
       path,
       total_space,
       free_space,
       unreserved_space,
       keep_free_space,
       round(100 * (total_space - free_space) / nullIf(total_space, 0), 2)
         AS used_percent
FROM system.disks
ORDER BY used_percent DESC;
```

`unreserved_space` can be more operationally relevant than raw free space. Object-storage-backed disks and ClickHouse Cloud do not necessarily map to a local filesystem. Source: [`system.disks`](https://clickhouse.com/docs/operations/system-tables/disks).

### Q16 — Cache effectiveness

```sql
SELECT event, value
FROM system.events
WHERE event IN ('MarkCacheHits', 'MarkCacheMisses',
                'UncompressedCacheHits', 'UncompressedCacheMisses',
                'QueryCacheHits', 'QueryCacheMisses')
ORDER BY event;
```

Calculate interval hit ratios from counter deltas. A cache may be disabled, and a missing event is not a zero-valued measurement.

### Q17 — Replica health

```sql
SELECT database,
       table,
       is_readonly,
       is_session_expired,
       future_parts,
       parts_to_check,
       queue_size,
       inserts_in_queue,
       merges_in_queue,
       absolute_delay,
       total_replicas,
       active_replicas,
       zookeeper_exception
FROM system.replicas
WHERE is_readonly
   OR is_session_expired
   OR queue_size > 0
   OR active_replicas < total_replicas
ORDER BY absolute_delay DESC, queue_size DESC;
```

Query each replica. `absolute_delay` is an indicator, not a guaranteed end-user freshness measure. Source: [`system.replicas`](https://clickhouse.com/docs/operations/system-tables/replicas).

### Q18 — Replication queue

```sql
SELECT database,
       table,
       replica_name,
       position,
       node_name,
       type,
       create_time,
       num_tries,
       last_exception,
       last_attempt_time,
       num_postponed,
       postpone_reason
FROM system.replication_queue
WHERE num_tries > 0 OR num_postponed > 0
ORDER BY create_time
LIMIT 200;
```

This is queue state on the selected node. Preserve ordering and exception text for diagnosis. Source: [`system.replication_queue`](https://clickhouse.com/docs/operations/system-tables/replication_queue).

### Q19 — Distributed-send queue

```sql
SELECT database,
       table,
       data_path,
       is_blocked,
       error_count,
       data_files,
       data_compressed_bytes,
       last_exception,
       last_exception_time
FROM system.distribution_queue
WHERE data_files > 0 OR error_count > 0
ORDER BY error_count DESC, data_files DESC;
```

Relevant to `Distributed` tables that queue local files for remote delivery. It is not the replicated-table queue. Source: [`system.distribution_queue`](https://clickhouse.com/docs/operations/system-tables/distribution_queue).

## Internal server logs and historical events

### Recommended logging baseline

Enable `query_log`, `part_log`, `metric_log` and `text_log` only with retention, volume and privacy controls appropriate to the deployment. Keep `log_queries` enabled for production query history, set a local minimum duration/sampling policy, and protect statement text. `_log` tables consume storage and are not a substitute for exporting metrics and logs from every node.

### Q20 — Internal text log

```sql
SELECT event_time_microseconds,
       level,
       logger_name,
       thread_name,
       query_id,
       message,
       source_file,
       source_line
FROM system.text_log
WHERE event_time >= now() - INTERVAL 1 HOUR
  AND level IN ('Fatal', 'Critical', 'Error', 'Warning')
ORDER BY event_time_microseconds DESC
LIMIT 500;
```

The table must be configured. Messages and stack context can be sensitive; a row limit is diagnostic, not a complete ingestion strategy. Source: [`system.text_log`](https://clickhouse.com/docs/operations/system-tables/text_log).

### Q21 — Error counters

```sql
SELECT name,
       code,
       value,
       last_error_time,
       last_error_message,
       last_error_trace
FROM system.errors
WHERE value > 0
ORDER BY last_error_time DESC
LIMIT 200;
```

Counters describe errors observed by the current server process and reset on restart. Errors can be incremented during handled or test paths, so correlate them with query and text logs. Source: [`system.errors`](https://clickhouse.com/docs/operations/system-tables/errors).

## Deeper diagnosis and rollout

For a selected read query, use `EXPLAIN indexes = 1`, `EXPLAIN PIPELINE` or `EXPLAIN ESTIMATE` in a controlled session. Explain output and optimizer behavior can change between releases; do not build a stable parser around human-oriented output without version tests. [EXPLAIN reference](https://clickhouse.com/docs/sql-reference/statements/explain).

Suggested rollout:

1. Capture Q01 and prove access on every node/service replica.
2. Poll Q02–Q03 every 15–30 seconds and Q07–Q09 every 30–60 seconds.
3. Collect Q04–Q06 in overlapping windows, deduplicating coordinator and child records deliberately.
4. Check Q10–Q16 every 1–5 minutes, with table-specific thresholds for part counts and mutations.
5. Poll Q17–Q19 on every applicable replica and retain queue exception changes.
6. Enable Q20 only with bounded retention; use Q21 as a counter signal and correlate it with detailed records.
7. Load-test monitoring queries on production-sized system tables and validate exact columns after every upgrade.

SQL exposes substantial ClickHouse state but does not replace host/container CPU, memory, filesystem, network, ClickHouse Keeper, object-storage or cloud-service telemetry. Protect queries, exceptions and internal logs as application data.
