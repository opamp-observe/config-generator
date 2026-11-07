<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0. See license.txt in the project root.
-->

# MariaDB monitoring SQL: performance, slow queries, locks and internal logs

## Scope and interpretation

Scope: maintained MariaDB Community Server LTS series 10.11, 11.4, 11.8 and 12.3. MariaDB 10.6 reached community end of life in July 2026 and is not in the primary matrix. Storage-engine-specific queries below target InnoDB.

These are operational query patterns assembled from MariaDB's documented Information Schema, Performance Schema and status interfaces. Thresholds and polling intervals are recommendations to tune locally. Do not assume MySQL 8.0 monitoring columns are present in MariaDB merely because table names are similar.

## What can be retrieved entirely through SQL?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Queries running slowly now | `information_schema.PROCESSLIST` or `performance_schema.threads` | Current observation; short activity between polls is missed. |
| Long transactions and row-lock blockers | InnoDB transaction/lock-wait tables | InnoDB only; current waits disappear when resolved. |
| Metadata locks | `performance_schema.metadata_locks` | Requires Performance Schema and enabled instrumentation. |
| Expensive statement patterns | `events_statements_summary_by_digest` | Bounded digest table; normalized aggregates are not individual executions. |
| Recent completed statements | `events_statements_history_long` | Small in-memory ring; consumer and sizing must be enabled. |
| Historical slow queries | `mysql.slow_log` with `log_output=TABLE` | Slow logging and table output must be enabled; table logging has overhead. |
| Internal server warnings/errors | Error log file/syslog | No general SQL table for the full error log. |
| Latest InnoDB deadlock | `SHOW ENGINE INNODB STATUS` | Only the retained latest deadlock text unless file logging is enabled. |

“Entirely through SQL” excludes file-only error and slow logs. Missing historical instrumentation cannot be reconstructed from counters after the event.

## Prerequisites and collection rules

Use a dedicated account with the minimum `PROCESS` and `SELECT` access needed for the selected `information_schema`, `performance_schema` and `mysql` tables. Restrict slow-log and statement-text access more tightly than numeric metrics. Do not grant global administrative privileges merely for monitoring.

Performance Schema must be enabled at server start, and its instruments/consumers must collect the desired events. Enabling every instrument can add overhead. Validate configuration with Q09 and stage related live tables before joins on busy servers. `information_schema.PROCESSLIST` itself can be locking; prefer Performance Schema threads for high-frequency collection when its columns meet the use case. [SHOW PROCESSLIST](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/show/show-processlist).

Timer fields in Performance Schema are picoseconds unless the table documents otherwise; divide by `1000000000` for milliseconds. Difference cumulative status variables between continuous samples and discard deltas across restart, reset, counter decrease or a changed server identity. Record `@@server_uuid` where available, host, port, version and uptime.

## Compatibility matrix

**Y** = common interface. **P** = Performance Schema/configuration required. **I** = InnoDB only. **L** = logging configuration required.

| Query name | 10.11 | 11.4 | 11.8 | 12.3 |
| --- | --- | --- | --- | --- |
| Q01 Environment and configuration | Y | Y | Y | Y |
| Q02 Active slow statements | Y | Y | Y | Y |
| Q03 Long and idle transactions | I | I | I | I |
| Q04 Session summary | Y | Y | Y | Y |
| Q05 Row-lock blockers | I | I | I | I |
| Q06 Metadata locks | P | P | P | P |
| Q07 Expensive statement patterns | P | P | P | P |
| Q08 Statement counter snapshot | P | P | P | P |
| Q09 Collection health | P | P | P | P |
| Q10 Workload and connection counters | Y | Y | Y | Y |
| Q11 Table size and maintenance candidates | Y | Y | Y | Y |
| Q12 Index usage | P | P | P | P |
| Q13 InnoDB cache pressure | I | I | I | I |
| Q14 Stage progress | P | P | P | P |
| Q15 Redo and commit pressure | Y | Y | Y | Y |
| Q16 File I/O counters | P | P | P | P |
| Q17 Spill and scan candidates | P | P | P | P |
| Q18 Replication state | Y | Y | Y | Y |
| Q19 Replication worker errors | P | P | P | P |
| Q20 Historical slow statements | L | L | L | L |
| Q21 Latest InnoDB deadlock | I | I | I | I |

The maintained-series dates are published by the MariaDB Foundation. Exact enterprise/extended support differs from community maintenance. [MariaDB maintenance policy](https://mariadb.org/about/).

## Query catalogue

### Q01 — Environment and configuration

```sql
SELECT VERSION() AS server_version,
       @@hostname AS host_name,
       @@port AS server_port,
       @@server_id AS server_id,
       @@server_uuid AS server_uuid,
       @@read_only AS read_only,
       @@performance_schema AS performance_schema_enabled,
       NOW(6) AS sampled_at;

SELECT VARIABLE_NAME, VARIABLE_VALUE
FROM information_schema.GLOBAL_VARIABLES
WHERE VARIABLE_NAME IN ('LOG_OUTPUT', 'SLOW_QUERY_LOG',
                        'LONG_QUERY_TIME', 'MIN_EXAMINED_ROW_LIMIT',
                        'LOG_SLOW_VERBOSITY', 'BINLOG_FORMAT',
                        'GTID_STRICT_MODE', 'INNODB_FLUSH_LOG_AT_TRX_COMMIT');
```

Run at startup/reconnection and after configuration changes. Names around slow-query logging gained preferred `log_slow_*` forms in newer MariaDB while compatibility aliases remain; inspect the exact series. [Server system variables](https://mariadb.com/docs/server/server-management/variables-and-modes/server-system-variables).

### Q02 — Active slow statements

```sql
SELECT ID,
       USER,
       HOST,
       DB,
       COMMAND,
       TIME_MS,
       STATE,
       STAGE,
       MAX_STAGE,
       PROGRESS,
       INFO
FROM information_schema.PROCESSLIST
WHERE COMMAND != 'Sleep'
  AND TIME_MS >= 5000
  AND ID != CONNECTION_ID()
ORDER BY TIME_MS DESC;
```

`TIME_MS` is time in the current command/state and offers subsecond precision. `INFO` can contain sensitive literals. Progress semantics differ between Information Schema and `SHOW PROCESSLIST`.

### Q03 — Long and idle transactions

```sql
SELECT transaction.TRX_ID,
       transaction.TRX_MYSQL_THREAD_ID,
       transaction.TRX_STATE,
       transaction.TRX_STARTED,
       TIMESTAMPDIFF(SECOND, transaction.TRX_STARTED, NOW())
         AS TRANSACTION_AGE_SECONDS,
       transaction.TRX_ROWS_LOCKED,
       transaction.TRX_ROWS_MODIFIED,
       process.USER,
       process.HOST,
       process.COMMAND,
       process.TIME_MS,
       process.INFO
FROM information_schema.INNODB_TRX AS transaction
LEFT JOIN information_schema.PROCESSLIST AS process
  ON process.ID = transaction.TRX_MYSQL_THREAD_ID
WHERE transaction.TRX_STARTED < NOW() - INTERVAL 60 SECOND
   OR process.COMMAND = 'Sleep'
ORDER BY transaction.TRX_STARTED;
```

An idle connection owning a transaction can retain locks/undo. Do not kill it without application ownership and recovery context.

### Q04 — Session summary

```sql
SELECT USER,
       COMMAND,
       STATE,
       COUNT(*) AS SESSION_COUNT,
       MAX(TIME_MS) AS MAX_STATE_AGE_MS
FROM information_schema.PROCESSLIST
GROUP BY USER, COMMAND, STATE
ORDER BY SESSION_COUNT DESC;
```

This is a gauge. Connection pools can make sleeping sessions normal.

### Q05 — Row-lock blockers

```sql
SELECT wait.REQUESTING_TRX_ID,
       requesting.TRX_MYSQL_THREAD_ID AS WAITING_THREAD_ID,
       requesting.TRX_STARTED AS WAITING_TRX_STARTED,
       requesting.TRX_QUERY AS WAITING_QUERY,
       wait.BLOCKING_TRX_ID,
       blocking.TRX_MYSQL_THREAD_ID AS BLOCKING_THREAD_ID,
       blocking.TRX_STARTED AS BLOCKING_TRX_STARTED,
       blocking.TRX_QUERY AS BLOCKING_QUERY
FROM information_schema.INNODB_LOCK_WAITS AS wait
JOIN information_schema.INNODB_TRX AS requesting
  ON requesting.TRX_ID = wait.REQUESTING_TRX_ID
JOIN information_schema.INNODB_TRX AS blocking
  ON blocking.TRX_ID = wait.BLOCKING_TRX_ID;
```

Samples can race with transaction completion and thread reuse. Preserve transaction IDs, not only thread IDs.

### Q06 — Metadata locks

```sql
SELECT OBJECT_TYPE,
       OBJECT_SCHEMA,
       OBJECT_NAME,
       LOCK_TYPE,
       LOCK_DURATION,
       LOCK_STATUS,
       OWNER_THREAD_ID,
       OWNER_EVENT_ID
FROM performance_schema.metadata_locks
WHERE LOCK_STATUS != 'GRANTED'
ORDER BY OBJECT_SCHEMA, OBJECT_NAME, OWNER_THREAD_ID;
```

Available from MariaDB 10.5.2 and requires metadata-lock instrumentation. A pending lock needs thread/event correlation to identify its blocker. [metadata locks table](https://mariadb.com/docs/server/reference/system-tables/performance-schema/performance-schema-tables/performance-schema-metadata_locks-table).

### Q07 — Expensive statement patterns

```sql
SELECT SCHEMA_NAME,
       DIGEST,
       DIGEST_TEXT,
       COUNT_STAR,
       ROUND(SUM_TIMER_WAIT / 1000000000, 2) AS TOTAL_WAIT_MS,
       ROUND(AVG_TIMER_WAIT / 1000000000, 2) AS MEAN_WAIT_MS,
       ROUND(MAX_TIMER_WAIT / 1000000000, 2) AS MAX_WAIT_MS,
       SUM_ROWS_EXAMINED,
       SUM_ROWS_SENT,
       SUM_CREATED_TMP_DISK_TABLES,
       SUM_NO_INDEX_USED,
       SUM_ERRORS,
       FIRST_SEEN,
       LAST_SEEN
FROM performance_schema.events_statements_summary_by_digest
WHERE DIGEST IS NOT NULL AND COUNT_STAR > 0
ORDER BY SUM_TIMER_WAIT DESC
LIMIT 50;
```

The digest table is bounded. Events beyond capacity accumulate under a null digest, so Q09 must detect saturation. Source: [digest summary](https://mariadb.com/docs/server/reference/system-tables/performance-schema/performance-schema-tables/performance-schema-events_statements_summary_by_digest-table).

### Q08 — Statement counter snapshot

```sql
SELECT SCHEMA_NAME,
       DIGEST,
       COUNT_STAR,
       SUM_TIMER_WAIT,
       SUM_LOCK_TIME,
       SUM_ERRORS,
       SUM_WARNINGS,
       SUM_ROWS_AFFECTED,
       SUM_ROWS_SENT,
       SUM_ROWS_EXAMINED,
       SUM_CREATED_TMP_DISK_TABLES,
       SUM_SELECT_SCAN,
       SUM_NO_INDEX_USED,
       FIRST_SEEN,
       LAST_SEEN
FROM performance_schema.events_statements_summary_by_digest;
```

Calculate deltas only while digest identity and server uptime are continuous. A statement that begins before one sample and ends after it makes interval means approximate.

### Q09 — Collection health

```sql
SELECT NAME, ENABLED
FROM performance_schema.setup_consumers
WHERE NAME IN ('events_statements_current',
               'events_statements_history',
               'events_statements_history_long');

SELECT COUNT_STAR AS DIGESTS_LOST_TO_OVERFLOW
FROM performance_schema.events_statements_summary_by_digest
WHERE DIGEST IS NULL;

SELECT VARIABLE_NAME, VARIABLE_VALUE
FROM information_schema.GLOBAL_STATUS
WHERE VARIABLE_NAME IN ('UPTIME', 'PERFORMANCE_SCHEMA_DIGEST_LOST',
                        'PERFORMANCE_SCHEMA_STATEMENT_CLASSES_LOST');
```

The null-digest row and lost counters reveal incomplete attribution. A disabled consumer means absence of records is not absence of activity.

### Q10 — Workload and connection counters

```sql
SELECT VARIABLE_NAME, VARIABLE_VALUE
FROM information_schema.GLOBAL_STATUS
WHERE VARIABLE_NAME IN ('UPTIME', 'THREADS_CONNECTED', 'THREADS_RUNNING',
                        'CONNECTIONS', 'ABORTED_CONNECTS',
                        'QUESTIONS', 'QUERIES', 'COM_SELECT',
                        'COM_INSERT', 'COM_UPDATE', 'COM_DELETE',
                        'CREATED_TMP_TABLES', 'CREATED_TMP_DISK_TABLES',
                        'SLOW_QUERIES', 'TABLE_LOCKS_WAITED');
```

Connections/threads are gauges; most other fields are cumulative counters. `QUESTIONS` and `QUERIES` have different inclusion rules.

### Q11 — Table size and maintenance candidates

```sql
SELECT TABLE_SCHEMA,
       TABLE_NAME,
       ENGINE,
       TABLE_ROWS,
       DATA_LENGTH,
       INDEX_LENGTH,
       DATA_FREE,
       UPDATE_TIME
FROM information_schema.TABLES
WHERE TABLE_SCHEMA NOT IN ('information_schema', 'performance_schema',
                           'mysql', 'sys')
ORDER BY DATA_LENGTH + INDEX_LENGTH DESC
LIMIT 100;
```

InnoDB row counts and free-space values are estimates. Fragmentation-looking values are investigation candidates, not an instruction to rebuild tables.

### Q12 — Index usage

```sql
SELECT OBJECT_SCHEMA,
       OBJECT_NAME,
       INDEX_NAME,
       COUNT_READ,
       COUNT_WRITE,
       SUM_TIMER_READ,
       SUM_TIMER_WRITE
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE OBJECT_SCHEMA NOT IN ('mysql', 'performance_schema')
ORDER BY COUNT_READ ASC, COUNT_WRITE DESC;
```

Low observed reads do not prove an index is unused across seasonal, failover or maintenance workloads. Resets/restarts bound the observation window.

### Q13 — InnoDB cache pressure

```sql
SELECT POOL_ID,
       POOL_SIZE,
       FREE_BUFFERS,
       DATABASE_PAGES,
       MODIFIED_DATABASE_PAGES,
       PENDING_READS,
       PENDING_FLUSH_LRU,
       PENDING_FLUSH_LIST,
       NUMBER_PAGES_READ,
       NUMBER_PAGES_WRITTEN
FROM information_schema.INNODB_BUFFER_POOL_STATS;
```

Use counter deltas for I/O rates and gauges for occupancy. A low free-buffer count alone is normal for a cache.

### Q14 — Stage progress

```sql
SELECT stage.THREAD_ID,
       stage.EVENT_ID,
       stage.EVENT_NAME,
       stage.WORK_COMPLETED,
       stage.WORK_ESTIMATED,
       ROUND(100 * stage.WORK_COMPLETED /
             NULLIF(stage.WORK_ESTIMATED, 0), 1) AS STAGE_PERCENT,
       thread.PROCESSLIST_ID,
       thread.PROCESSLIST_USER,
       thread.PROCESSLIST_INFO
FROM performance_schema.events_stages_current AS stage
JOIN performance_schema.threads AS thread
  ON thread.THREAD_ID = stage.THREAD_ID
WHERE stage.WORK_ESTIMATED > 0;
```

Only instrumented stages report estimates. Stage percentage is not whole-query completion.

### Q15 — Redo and commit pressure

```sql
SELECT VARIABLE_NAME, VARIABLE_VALUE
FROM information_schema.GLOBAL_STATUS
WHERE VARIABLE_NAME IN ('INNODB_OS_LOG_WRITTEN', 'INNODB_LOG_WAITS',
                        'INNODB_LOG_WRITE_REQUESTS', 'INNODB_LOG_WRITES',
                        'INNODB_OS_LOG_FSYNCS', 'COM_COMMIT', 'COM_ROLLBACK');
```

Difference counters and correlate log waits with transaction rate, storage latency and durability settings.

### Q16 — File I/O counters

```sql
SELECT FILE_NAME,
       EVENT_NAME,
       COUNT_READ,
       SUM_NUMBER_OF_BYTES_READ,
       SUM_TIMER_READ,
       COUNT_WRITE,
       SUM_NUMBER_OF_BYTES_WRITE,
       SUM_TIMER_WRITE
FROM performance_schema.file_summary_by_instance
ORDER BY SUM_TIMER_READ + SUM_TIMER_WRITE DESC
LIMIT 100;
```

Use interval deltas. Instrumentation may exclude some storage paths and does not replace device-level latency/error monitoring.

### Q17 — Spill and scan candidates

```sql
SELECT SCHEMA_NAME,
       DIGEST,
       DIGEST_TEXT,
       COUNT_STAR,
       SUM_CREATED_TMP_TABLES,
       SUM_CREATED_TMP_DISK_TABLES,
       SUM_SELECT_SCAN,
       SUM_SELECT_FULL_JOIN,
       SUM_NO_INDEX_USED,
       SUM_ROWS_EXAMINED
FROM performance_schema.events_statements_summary_by_digest
WHERE SUM_CREATED_TMP_DISK_TABLES > 0
   OR SUM_SELECT_SCAN > 0
   OR SUM_NO_INDEX_USED > 0
ORDER BY SUM_ROWS_EXAMINED DESC
LIMIT 100;
```

These counters identify candidates, not automatic indexing prescriptions. Small scans and reporting queries can be appropriate.

### Q18 — Replication state

```sql
SHOW ALL REPLICAS STATUS;
```

Capture connection/channel name, I/O and SQL thread state, GTID positions, lag, last error and relay-log space. Some clients display this wide result better vertically. Lag can be null or misleading when replication is stopped or idle; evaluate thread/error state first.

### Q19 — Replication worker errors

```sql
SELECT CHANNEL_NAME,
       THREAD_ID,
       SERVICE_STATE,
       LAST_ERROR_NUMBER,
       LAST_ERROR_MESSAGE,
       LAST_ERROR_TIMESTAMP
FROM performance_schema.replication_applier_status_by_worker
WHERE LAST_ERROR_NUMBER != 0 OR SERVICE_STATE != 'ON';
```

Parallel replication can fail on one worker while other status remains healthy-looking. Validate column availability on the exact series.

## Internal server logs and historical events

### Recommended logging baseline

Keep the error log file/syslog under external rotation and collection. Enable the slow query log with a locally justified duration, row and sampling policy. Prefer file output for high-volume production logging; `TABLE` output makes SQL retrieval possible but adds database work and stores sensitive text. The general log records every received statement and can grow rapidly, so use it only for bounded troubleshooting. [MariaDB log overview](https://mariadb.com/docs/server/server-management/server-monitoring-logs/overview-of-mariadb-logs).

### Q20 — Historical slow statements

Requires slow logging and `log_output` containing `TABLE`:

```sql
SELECT start_time,
       query_time,
       lock_time,
       rows_sent,
       rows_examined,
       db,
       last_insert_id,
       insert_id,
       server_id,
       sql_text,
       thread_id,
       rows_affected
FROM mysql.slow_log
WHERE start_time >= NOW() - INTERVAL 1 HOUR
ORDER BY start_time DESC
LIMIT 500;
```

The slow log is not a complete execution history. Threshold, filters, sampling, admin/replica statement settings and log rotation determine coverage. Source: [slow query log](https://mariadb.com/docs/server/server-management/server-monitoring-logs/slow-query-log).

### Q21 — Latest InnoDB deadlock

```sql
SHOW ENGINE INNODB STATUS;
```

Parse the `LATEST DETECTED DEADLOCK` section only with version-aware tooling. This status text is human-oriented and contains only retained diagnostic context. Configure `innodb_print_all_deadlocks` when all detected deadlocks must reach the error log. Source: [`SHOW ENGINE`](https://mariadb.com/docs/server/reference/sql-statements/administrative-sql-statements/show/show-engine).

## Deeper diagnosis and rollout

Use `EXPLAIN FORMAT=JSON` for a chosen statement and `ANALYZE FORMAT=JSON` only when it is safe to execute the statement: `ANALYZE` runs it. Never run mutating or expensive production SQL solely to collect a plan without understanding side effects.

Suggested rollout:

1. Capture Q01 and prove Performance Schema consumers/instruments with Q09.
2. Poll Q02–Q06 every 15–30 seconds, using Performance Schema alternatives where process-list overhead matters.
3. Snapshot Q08/Q10/Q12/Q15/Q16 every 30–60 seconds and calculate validated deltas.
4. Check Q11/Q13/Q14/Q17 every 1–5 minutes.
5. Poll Q18/Q19 on every replica/channel and preserve error transitions.
6. Enable Q20 only with a retention/privacy plan; collect the file error log externally and use Q21 for bounded diagnosis.
7. Validate exact columns, timer units, storage engine, instrumentation overhead and replication terminology on every supported series.

SQL exposes extensive MariaDB state but does not replace host CPU, memory, filesystem capacity, storage latency, network or file-log telemetry. Protect SQL text and diagnostic records as application data.
