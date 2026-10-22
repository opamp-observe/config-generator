# PostgreSQL monitoring SQL: performance, slow queries, locks and internal logs

## Scope and interpretation

Scope: community PostgreSQL 14–18. PostgreSQL 19 is pre-release and excluded; versions 13 and earlier are outside this matrix. [Version policy](https://www.postgresql.org/support/versioning/).

These are recommended operational query patterns assembled from PostgreSQL's documented interfaces, rather than a claim that PostgreSQL publishes this exact query pack. Thresholds, ranking choices and polling intervals below are starting recommendations to tune against your workload. The queries were reviewed against the versioned documentation; they have not been executed against live servers of every version.

## What can be retrieved entirely through SQL?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Queries running slowly now | `pg_stat_activity` | A point-in-time observation; short executions between samples are missed. |
| Expensive or slow completed statement patterns | `pg_stat_statements` | Aggregates normalized statements, rather than retaining every execution. |
| Processes waiting on locks and their blockers | `pg_stat_activity`, `pg_blocking_pids()`, `pg_locks` | Current state; resolved deadlocks disappear. |
| Exact historical slow executions, errors, deadlocks and lock-wait messages | PostgreSQL server logs | Core PostgreSQL does not automatically maintain a queryable log-history table. |
| Server log files without SSH or external forwarding | Privileged file functions, or server-side CSV import | Requires files accessible to the server and additional privileges; hosting providers may restrict this. |

I interpret “logging that isn't exposed to the outside of the DB” as server diagnostic information obtainable through a database connection, including messages that have never been forwarded to an external log service. Retaining everything inside PostgreSQL is possible with controlled imports, but logs must first be generated and retained. Missing historical messages cannot be reconstructed from counters.

## Prerequisites and collection rules

Use a dedicated monitoring account with `CONNECT` on each monitored database. A DBA can grant the existing account the following role:

```sql
GRANT pg_monitor TO monitoring_user;
```

`pg_monitor` includes `pg_read_all_stats` and `pg_read_all_settings`. It exposes other sessions' query information and monitoring settings, but does **not** by itself grant arbitrary server-file contents. Restrict access to collected SQL text. [Predefined roles](https://www.postgresql.org/docs/18/predefined-roles.html).

For statement history, a DBA must add `pg_stat_statements` to the existing `shared_preload_libraries` list, restart the server, and then install its SQL interface in the monitoring database:

```sql
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
```

Keep `compute_query_id = auto` or `on`. Do not replace an existing preload list accidentally. These examples assume the extension schema is on `search_path`; otherwise schema-qualify its views. Record its installed `extversion`, and update the extension during upgrades: server major version alone does not guarantee an upgraded extension definition. [PostgreSQL 14 extension setup](https://www.postgresql.org/docs/14/pgstatstatements.html).

Execute polls in autocommit or short transactions. Long-lived transactions can reuse statistics snapshots. Cumulative counters require two samples: `rate = (new_counter - old_counter) / elapsed_seconds`. Discard a delta if the reset marker changes, a counter decreases, or an entry disappears/reappears. Do not reset statistics as part of polling. [PostgreSQL 15 statistics](https://www.postgresql.org/docs/15/monitoring-stats.html).

Table, index and vacuum queries run in **each application database**. Activity, I/O, WAL and checkpoint views have cluster-wide scope; statement statistics include database identifiers. For multi-cluster collection, attach a stable cluster identity, major version and sample timestamp to every result.

## Compatibility matrix

**Y** = exact SQL below uses documented interfaces for that major release. **E** = Y with `pg_stat_statements` installed/preloaded and its matching extension SQL version. **F** = server-file access and suitable logging configuration needed. **I** = the example imported log table must exist. **—** = use the named alternative. These are documentation-based compatibility findings, not a five-version execution test.

| Query name | PG14 | PG15 | PG16 | PG17 | PG18 |
| --- | --- | --- | --- | --- | --- |
| Q01 Environment and configuration | Y | Y | Y | Y | Y |
| Q02 Active slow queries | Y | Y | Y | Y | Y |
| Q03 Long and idle transactions | Y | Y | Y | Y | Y |
| Q04 Session and wait summary | Y | Y | Y | Y | Y |
| Q05 Blocking relationships | Y | Y | Y | Y | Y |
| Q06 Waiting lock detail | Y | Y | Y | Y | Y |
| Q07 Slow statement patterns | E | E | E | E | E |
| Q08 Statement counter snapshot | E | E | E | E | E |
| Q09 Statement collection health | E | E | E | E | E |
| Q10 Database workload and spill counters | Y | Y | Y | Y | Y |
| Q11 Table maintenance candidates | Y | Y | Y | Y | Y |
| Q12 Index usage and size | Y | Y | Y | Y | Y |
| Q13 Transaction ID age | Y | Y | Y | Y | Y |
| Q14 Vacuum progress | Y | Y | Y | Y | Y |
| Q15 WAL generation counters | Y | Y | Y | Y | Y |
| Q16a Checkpoints, legacy view | Y | Y | Y | — | — |
| Q16b Checkpoints, dedicated view | — | — | — | Y | Y |
| Q17a I/O bytes, fixed operation size | — | — | Y | Y | — |
| Q17b I/O bytes, explicit byte counters | — | — | — | — | Y |
| Q18 Replication sender lag | Y | Y | Y | Y | Y |
| Q19 Replication slot WAL retention | Y | Y | Y | Y | Y |
| Q20 Server log discovery | Y | Y | Y | Y | Y |
| Q21 Bounded server log read | F | F | F | F | F |
| Q22 Historical errors from imported CSV | I | I | I | I | I |
| Q23 Historical slow executions from imported CSV | I | I | I | I | I |

Compatibility evidence: [PG14 statistics](https://www.postgresql.org/docs/14/monitoring-stats.html), [PG15 statistics](https://www.postgresql.org/docs/15/monitoring-stats.html), [PG16 statistics](https://www.postgresql.org/docs/16/monitoring-stats.html), [PG17 statistics](https://www.postgresql.org/docs/17/monitoring-stats.html), [PG18 statistics](https://www.postgresql.org/docs/18/monitoring-stats.html), and the extension/function references beside each query.

Key changes:

- PG16 introduced `pg_stat_io`; PG14–15 can use Q10's database block counters, but those do not provide the same backend/context breakdown. [Release 16](https://www.postgresql.org/docs/16/release-16.html).
- PG17 exposes checkpoint statistics through `pg_stat_checkpointer`; use Q16b. [PG17 view definition](https://www.postgresql.org/docs/17/monitoring-stats.html#MONITORING-PG-STAT-CHECKPOINTER-VIEW).
- PG18 removed `pg_stat_io.op_bytes` and added explicit byte totals. It also moved WAL I/O timing/reporting out of `pg_stat_wal` into `pg_stat_io`; Q15 deliberately uses only surviving columns. [Release 18](https://www.postgresql.org/docs/18/release-18.html).
- `jsonlog` is available from PG15; `csvlog` works throughout this matrix. The examples use CSV for a common import format. [PG14 logging](https://www.postgresql.org/docs/14/runtime-config-logging.html), [PG15 logging](https://www.postgresql.org/docs/15/runtime-config-logging.html).

## Query catalogue

### Q01 — Environment and configuration

Run at connection/startup and after configuration changes. Missing optional extension settings simply produce no row.

```sql
SELECT version(), current_setting('server_version_num')::integer AS version_num,
       pg_postmaster_start_time() AS server_started,
       pg_is_in_recovery() AS is_standby;
SELECT extname, extversion FROM pg_extension
WHERE extname = 'pg_stat_statements';
SELECT name, setting, unit, context, pending_restart
FROM pg_settings
WHERE name IN (
  'track_activities', 'track_counts', 'track_activity_query_size',
  'track_io_timing', 'track_wal_io_timing', 'compute_query_id',
  'shared_preload_libraries', 'pg_stat_statements.track',
  'pg_stat_statements.track_planning', 'logging_collector',
  'log_destination', 'log_directory', 'log_min_duration_statement',
  'log_min_error_statement', 'log_lock_waits', 'deadlock_timeout',
  'log_temp_files', 'max_connections', 'superuser_reserved_connections'
)
ORDER BY name;
```

Source: [`pg_settings`](https://www.postgresql.org/docs/18/view-pg-settings.html). `context` and `pending_restart` help distinguish settings that require restart from those changeable at runtime.

### Q02 — Active slow queries

```sql
SELECT pid, datname, usename, application_name, query_id,
       statement_timestamp() - query_start AS elapsed,
       wait_event_type, wait_event, left(query, 4000) AS query
FROM pg_stat_activity
WHERE state = 'active' AND pid <> pg_backend_pid()
  AND query_start < statement_timestamp() - interval '5 seconds'
ORDER BY query_start;
```

The filter on `state` is essential: idle sessions retain their last query. Elapsed time includes waits, rather than measuring CPU time. Query text may already be truncated by `track_activity_query_size`. Source: [`pg_stat_activity`, PG14](https://www.postgresql.org/docs/14/monitoring-stats.html#MONITORING-PG-STAT-ACTIVITY-VIEW).

### Q03 — Long and idle transactions

```sql
SELECT pid, datname, usename, state,
       statement_timestamp() - xact_start AS transaction_age,
       statement_timestamp() - state_change AS time_in_state,
       backend_xmin, wait_event_type, wait_event, left(query, 2000) AS last_query
FROM pg_stat_activity
WHERE xact_start IS NOT NULL AND pid <> pg_backend_pid()
  AND (xact_start < statement_timestamp() - interval '1 minute'
       OR state IN ('idle in transaction', 'idle in transaction (aborted)'))
ORDER BY xact_start;
```

Investigate idle transactions that retain locks or delay cleanup. Age is a triage signal; legitimate batch transactions may be long. Source: [PG15 activity statistics](https://www.postgresql.org/docs/15/monitoring-stats.html#MONITORING-PG-STAT-ACTIVITY-VIEW).

### Q04 — Session and wait summary

```sql
SELECT datname, backend_type, state, wait_event_type, wait_event,
       count(*) AS sessions
FROM pg_stat_activity
WHERE pid <> pg_backend_pid()
GROUP BY datname, backend_type, state, wait_event_type, wait_event
ORDER BY sessions DESC;
```

Track client-backend totals against the configured connection budget, allowing for reserved slots. Wait-event names can change between major releases; retain them as labels rather than hard-coding a fixed list. A null wait event alone does not prove CPU saturation. Source: [PG16 activity/wait documentation](https://www.postgresql.org/docs/16/monitoring-stats.html#MONITORING-PG-STAT-ACTIVITY-VIEW).

### Q05 — Blocking relationships

```sql
SELECT w.pid AS waiting_pid, w.datname, w.usename AS waiting_user,
       statement_timestamp() - w.query_start AS waiting_query_age,
       p.blocker_pid, b.usename AS blocker_user, b.state AS blocker_state,
       statement_timestamp() - b.xact_start AS blocker_transaction_age,
       left(w.query, 2000) AS waiting_query,
       left(b.query, 2000) AS blocker_last_query
FROM pg_stat_activity AS w
CROSS JOIN LATERAL (
  SELECT DISTINCT unnest(pg_blocking_pids(w.pid)) AS blocker_pid
) AS p
LEFT JOIN pg_stat_activity AS b ON b.pid = p.blocker_pid
WHERE w.wait_event_type = 'Lock'
ORDER BY w.query_start;
```

Use the documented blocker function rather than inferring conflicts from a simplistic self-join of `pg_locks`. It handles conflicting holders and ahead-of-queue waiters. PID zero denotes a prepared transaction, so the left join preserves it. `waiting_query_age` is not lock-wait duration. Avoid very aggressive polling because this function accesses lock-manager state. Source: [`pg_blocking_pids()`](https://www.postgresql.org/docs/18/functions-info.html#FUNCTIONS-INFO-SESSION-TABLE).

### Q06 — Waiting lock detail

```sql
SELECT l.pid, a.datname, l.locktype, l.mode, l.waitstart,
       statement_timestamp() - l.waitstart AS lock_wait_age,
       l.database AS lock_database_oid, l.relation AS relation_oid,
       CASE WHEN l.database = (SELECT oid FROM pg_database
                               WHERE datname = current_database())
            THEN l.relation::regclass::text END AS local_relation,
       l.transactionid, l.virtualxid,
       a.wait_event, left(a.query, 2000) AS query
FROM pg_locks AS l
LEFT JOIN pg_stat_activity AS a ON a.pid = l.pid
WHERE NOT l.granted
ORDER BY l.waitstart NULLS LAST;
```

`pg_locks` spans databases; resolve relation OIDs only for the connected database. Row-lock waits often appear as transaction-ID waits. `waitstart` can briefly be null. Source: [`pg_locks`](https://www.postgresql.org/docs/18/view-pg-locks.html). For the broader diagnostic approach see [Viewing Locks](https://www.postgresql.org/docs/18/monitoring-locks.html).

### Q07 — Slow statement patterns

```sql
SELECT dbid, userid, queryid, toplevel, calls,
       round(mean_exec_time::numeric, 2) AS mean_ms,
       round(max_exec_time::numeric, 2) AS max_ms,
       round(total_exec_time::numeric, 2) AS total_ms,
       rows, left(query, 4000) AS representative_query
FROM pg_stat_statements
WHERE calls >= 5 AND mean_exec_time >= 1000
ORDER BY mean_exec_time DESC
LIMIT 50;
```

To find infrequent outliers, replace the predicate with `calls > 0 AND max_exec_time >= 1000`; to prioritize total workload cost, rank by `total_exec_time DESC`. These are accumulated summaries, not “the last hour”, percentiles, or individual executions. Source: [`pg_stat_statements`, PG18](https://www.postgresql.org/docs/18/pgstatstatements.html).

### Q08 — Statement counter snapshot

```sql
SELECT statement_timestamp() AS sampled_at,
       dbid, userid, queryid, toplevel,
       calls, total_exec_time, rows,
       shared_blks_hit, shared_blks_read,
       temp_blks_read, temp_blks_written, wal_bytes
FROM pg_stat_statements;
```

Keep consecutive samples keyed by cluster, `dbid`, `userid`, `queryid`, and `toplevel`. Calculate interval mean execution time as `delta(total_exec_time) / delta(calls)` where delta calls is positive. Never difference `mean_exec_time` or `max_exec_time`. Query IDs are not durable identities across major upgrades. Source: [PG18 statement statistics](https://www.postgresql.org/docs/18/pgstatstatements.html). Missing/evicted/recreated entries make some intervals unusable; do not assume a reset timestamp alone detects every discontinuity.

### Q09 — Statement collection health

```sql
SELECT dealloc, stats_reset FROM pg_stat_statements_info;
```

A rising `dealloc` indicates statement-entry eviction and incomplete coverage; review `pg_stat_statements.max`. Execution statistics do not provide a complete history of failing statements. Planning counters need `track_planning`; nested SQL needs `track = all`, which can introduce overlap with top-level work. Source: [PG14 statement collection and configuration](https://www.postgresql.org/docs/14/pgstatstatements.html).

### Q10 — Database workload and spill counters

```sql
SELECT datid, datname, numbackends, xact_commit, xact_rollback,
       blks_read, blks_hit, temp_files, temp_bytes, deadlocks,
       blk_read_time, blk_write_time, stats_reset
FROM pg_stat_database
WHERE datname IS NOT NULL;
```

Difference counters to obtain transaction, rollback, deadlock and temporary-file rates. Compute interval buffer-hit ratio from delta hits and reads; this is PostgreSQL's buffer cache, not the OS cache. Timing requires `track_io_timing`; measure its overhead before enabling it. Source: [PG15 database statistics](https://www.postgresql.org/docs/15/monitoring-stats.html#MONITORING-PG-STAT-DATABASE-VIEW).

### Q11 — Table maintenance candidates

```sql
SELECT schemaname, relname, n_live_tup, n_dead_tup, n_mod_since_analyze,
       last_autovacuum, last_autoanalyze,
       last_vacuum, last_analyze, seq_scan, idx_scan
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC
LIMIT 50;
```

Treat row counts as estimates. Dead tuples and stale analyze activity identify investigation candidates, not an exact bloat measurement. Check table-specific autovacuum settings and workload before changing maintenance. Sources: [PG14 table statistics](https://www.postgresql.org/docs/14/monitoring-stats.html#MONITORING-PG-STAT-ALL-TABLES-VIEW), [Routine Vacuuming](https://www.postgresql.org/docs/18/routine-vacuuming.html).

### Q12 — Index usage and size

```sql
SELECT s.schemaname, s.relname, s.indexrelname,
       s.idx_scan, s.idx_tup_read, s.idx_tup_fetch,
       pg_relation_size(s.indexrelid) AS index_bytes,
       i.indisunique, i.indisprimary
FROM pg_stat_user_indexes AS s
JOIN pg_index AS i ON i.indexrelid = s.indexrelid
ORDER BY pg_relation_size(s.indexrelid) DESC
LIMIT 50;
```

Zero scans alone does not justify dropping an index: consider reset time, infrequent workloads, constraints and replica usage. Source: [PG16 index statistics](https://www.postgresql.org/docs/16/monitoring-stats.html#MONITORING-PG-STAT-ALL-INDEXES-VIEW).

### Q13 — Transaction ID age

```sql
SELECT datname, age(datfrozenxid) AS xid_age,
       current_setting('autovacuum_freeze_max_age')::bigint AS freeze_max_age
FROM pg_database
WHERE datallowconn
ORDER BY age(datfrozenxid) DESC;
```

Track growth and investigate missed freezing early; `autovacuum_freeze_max_age` is a maintenance trigger, not the hard wraparound limit. Source: [Preventing Transaction ID Wraparound Failures](https://www.postgresql.org/docs/18/routine-vacuuming.html#VACUUM-FOR-WRAPAROUND).

### Q14 — Vacuum progress

```sql
SELECT pid, datname, relid, phase, heap_blks_total,
       heap_blks_scanned, heap_blks_vacuumed,
       round(100.0 * heap_blks_scanned / NULLIF(heap_blks_total, 0), 1)
         AS heap_scan_pct
FROM pg_stat_progress_vacuum;
```

The percentage measures the heap scanning phase, not total job completion. `VACUUM FULL` appears in `pg_stat_progress_cluster`, not this view. Source: [Vacuum progress reporting](https://www.postgresql.org/docs/18/progress-reporting.html#VACUUM-PROGRESS-REPORTING).

### Q15 — WAL generation counters

```sql
SELECT wal_records, wal_fpi, wal_bytes, wal_buffers_full, stats_reset
FROM pg_stat_wal;
```

Difference for WAL bytes/second and buffer-full events. A rise should be correlated with workload and checkpoint activity. Source: [PG18 WAL statistics](https://www.postgresql.org/docs/18/monitoring-stats.html#MONITORING-PG-STAT-WAL-VIEW).

### Q16a / Q16b — Checkpoints

PG14–16, Q16a:

```sql
SELECT checkpoints_timed AS timed, checkpoints_req AS requested,
       checkpoint_write_time AS write_ms, checkpoint_sync_time AS sync_ms,
       buffers_checkpoint AS buffers_written, stats_reset
FROM pg_stat_bgwriter;
```

PG17–18, Q16b:

```sql
SELECT num_timed AS timed, num_requested AS requested,
       write_time AS write_ms, sync_time AS sync_ms,
       buffers_written, stats_reset
FROM pg_stat_checkpointer;
```

Sources: [PG16 background writer](https://www.postgresql.org/docs/16/monitoring-stats.html#MONITORING-PG-STAT-BGWRITER-VIEW), [PG17 checkpointer](https://www.postgresql.org/docs/17/monitoring-stats.html#MONITORING-PG-STAT-CHECKPOINTER-VIEW). Collect deltas. Counting semantics also matter: timed checkpoints can include skipped work; PG18 adds `num_done` for completed checkpoints. [PG18 changes](https://www.postgresql.org/docs/18/release-18.html).

### Q17a / Q17b — I/O bytes by backend and context

PG16–17, Q17a:

```sql
SELECT backend_type, object, context, reads, writes,
       reads::numeric * op_bytes AS read_bytes,
       writes::numeric * op_bytes AS write_bytes,
       read_time AS read_ms, write_time AS write_ms,
       fsyncs, fsync_time AS fsync_ms, stats_reset
FROM pg_stat_io;
```

PG18, Q17b:

```sql
SELECT backend_type, object, context, reads, writes,
       read_bytes, write_bytes,
       read_time AS read_ms, write_time AS write_ms,
       fsyncs, fsync_time AS fsync_ms, stats_reset
FROM pg_stat_io;
```

Keep nulls: some operations are inapplicable. Timings need `track_io_timing`, and PG18 WAL rows need `track_wal_io_timing`. These are PostgreSQL I/O statistics, not disk-device utilization. Sources: [PG16 I/O definition](https://www.postgresql.org/docs/16/monitoring-stats.html#MONITORING-PG-STAT-IO-VIEW), [PG18 I/O definition](https://www.postgresql.org/docs/18/monitoring-stats.html#MONITORING-PG-STAT-IO-VIEW).

### Q18 — Replication sender lag

```sql
SELECT pid, application_name, client_addr, state, sync_state,
       sent_lsn, write_lsn, flush_lsn, replay_lsn,
       write_lag, flush_lag, replay_lag,
       pg_wal_lsn_diff(pg_current_wal_lsn(), replay_lsn) AS replay_gap_bytes
FROM pg_stat_replication;
```

Run on the primary. Lag intervals describe recent replication behavior, not a guaranteed catch-up estimate; null values need context. Source: [PG17 replication statistics](https://www.postgresql.org/docs/17/monitoring-stats.html#MONITORING-PG-STAT-REPLICATION-VIEW).

### Q19 — Replication slot WAL retention

```sql
SELECT slot_name, slot_type, active, restart_lsn, confirmed_flush_lsn,
       pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)
         AS retained_wal_span_bytes
FROM pg_replication_slots
ORDER BY retained_wal_span_bytes DESC NULLS LAST;
```

Run on the primary. This LSN span estimates retention pressure, not exact on-disk space per slot; slots can retain overlapping WAL. Investigate inactive slots and retention limits. Source: [`pg_replication_slots`](https://www.postgresql.org/docs/18/view-pg-replication-slots.html).

## Internal server logs and historical events

### Recommended logging baseline

A DBA can configure the following example in `postgresql.conf`; thresholds are workload-specific:

```conf
logging_collector = on              # restart required
log_destination = 'csvlog'
log_min_duration_statement = '1s'
log_lock_waits = on
log_min_error_statement = error
log_temp_files = '64MB'
```

Lock-wait logging uses `deadlock_timeout`; avoid lowering it indiscriminately. Slow-statement logging records completed statement durations; extended-protocol Parse/Bind/Execute phases can be logged separately. These settings do not retroactively generate history. Sources: [PG18 duration/lock/error logging](https://www.postgresql.org/docs/18/runtime-config-logging.html), [PG14 collector and destinations](https://www.postgresql.org/docs/14/runtime-config-logging.html).

### Q20 — Server log discovery

```sql
SELECT pg_current_logfile('csvlog') AS active_csv_log;
SELECT name, size, modification
FROM pg_ls_logdir()
ORDER BY modification DESC
LIMIT 20;
```

`pg_monitor` can normally discover filenames; a null active path can mean collector or requested format is disabled. Sources: [`pg_current_logfile`](https://www.postgresql.org/docs/18/functions-info.html), [`pg_ls_logdir`](https://www.postgresql.org/docs/18/functions-admin.html).

### Q21 — Bounded server log read

DBA diagnostic example, reading the start of the active CSV file:

```sql
SELECT pg_read_file(pg_current_logfile('csvlog'), 0, 65536, true)
       AS csv_fragment;
```

This returns raw text, not parsed records or a reliable tail. A byte boundary can split a character/CSV record. Production readers need complete-record buffering, offsets and rotation handling. File functions are privileged; `pg_monitor` alone is insufficient. Absolute paths outside allowed locations may need additional server-file privileges. Managed services may prohibit this route entirely. Do not grant broad file access to a routine metrics account; prefer a reviewed restricted interface or imported table. Source: [Server file access functions and privilege warning](https://www.postgresql.org/docs/18/functions-admin.html#FUNCTIONS-ADMIN-GENFILE).

### Import CSV logs inside PostgreSQL

The following is an **optional DBA setup/import operation**, separate from read-only monitoring. The table's field order matches the documented PG14–18 CSV layout. Use a dedicated restricted schema; the example name is `monitoring`. The server reads a completed, rotated file, with no client-side file transfer required.

```sql
CREATE SCHEMA IF NOT EXISTS monitoring;
CREATE TABLE monitoring.server_log (
  log_time timestamptz, user_name text, database_name text,
  process_id integer, connection_from text, session_id text,
  session_line_num bigint, command_tag text, session_start_time timestamptz,
  virtual_transaction_id text, transaction_id bigint, error_severity text,
  sql_state_code text, message text, detail text, hint text,
  internal_query text, internal_query_pos integer, context text,
  query text, query_pos integer, location text, application_name text,
  backend_type text, leader_pid integer, query_id bigint,
  PRIMARY KEY (session_id, session_line_num)
);
-- Replace with an actual absolute SERVER path to a closed CSV log file.
COPY monitoring.server_log
FROM '/absolute/server/path/to/completed-log.csv' WITH (FORMAT csv);
CREATE INDEX server_log_time_idx ON monitoring.server_log (log_time);
```

Retain a manifest of imported files; importing a file twice fails on duplicate keys rather than silently deduplicating. Do not import the actively written file: incomplete records can fail the entire import. Add retention/partitioning for sustained use; avoid turning a production database into an unbounded log warehouse. For multiple clusters, store a cluster identity and include it in uniqueness keys. Sources: [PG14 CSV import layout and rotation guidance](https://www.postgresql.org/docs/14/runtime-config-logging.html#RUNTIME-CONFIG-LOGGING-CSVLOG), [server-side COPY permissions](https://www.postgresql.org/docs/18/sql-copy.html).

### Q22 — Historical errors, including deadlocks

```sql
SELECT log_time, database_name, process_id, application_name,
       error_severity, sql_state_code, message, detail, query
FROM monitoring.server_log
WHERE log_time >= statement_timestamp() - interval '1 hour'
  AND error_severity IN ('ERROR', 'FATAL', 'PANIC')
ORDER BY log_time DESC
LIMIT 200;
```

For resolved deadlocks add `AND sql_state_code = '40P01'`; database deadlock counters only count events, whereas log detail can identify participants. Coverage is limited by logging settings, retained files and import freshness. Source: [PostgreSQL error codes](https://www.postgresql.org/docs/18/errcodes-appendix.html).

### Q23 — Historical slow executions

```sql
WITH durations AS (
  SELECT log_time, database_name, process_id, session_id, session_line_num,
         application_name, query_id, message,
         substring(message FROM '^duration: ([0-9]+[.]?[0-9]*) ms')::numeric
           AS duration_ms
  FROM monitoring.server_log
  WHERE log_time >= statement_timestamp() - interval '1 hour'
)
SELECT * FROM durations
WHERE duration_ms >= 1000
ORDER BY duration_ms DESC
LIMIT 100;
```

This parser assumes PostgreSQL's English duration-message format; adapt it for `lc_messages`, protocol phase labels and your log format. Statement text may be embedded in `message`; the CSV `query` field is not universally populated for duration logs. If statements and durations are separate messages, correlate using session identity and ordering. Lock-wait text also needs language-aware parsing; it is not an ERROR-only event. Source: [PG15 duration logging](https://www.postgresql.org/docs/15/runtime-config-logging.html).

## Deeper diagnosis and rollout

For a selected representative read query, obtain an actual plan manually using `EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT ...`. `ANALYZE` executes the statement and adds measurement overhead; do not run arbitrary captured SQL as part of automated monitoring. [EXPLAIN reference](https://www.postgresql.org/docs/18/sql-explain.html), [plan interpretation](https://www.postgresql.org/docs/18/using-explain.html).

For plans of real slow executions, consider `auto_explain` with a duration threshold and sampling. It writes plans to server logs rather than providing a history view. `log_analyze`/node timing can add significant overhead; assess `log_timing = off` and test first. [auto_explain](https://www.postgresql.org/docs/18/auto-explain.html).

Suggested rollout, to tune locally:

1. Poll Q02–Q04 every 15–30 seconds, and Q05–Q06 when lock waits appear or during an incident.
2. Poll Q08–Q10, Q15–Q19 every 30–60 seconds; compute interval rates and retain reset markers.
3. Run Q11–Q14 every 1–5 minutes, limiting expensive size checks on large catalogues.
4. Use Q20–Q23 for controlled log access/imports; alert on ingestion delay as well as events.
5. Baseline thresholds against workload, then validate permissions and the chosen version variants on the target server before production rollout.

SQL exposes substantial internal state, but cannot replace OS/container metrics for CPU utilization, filesystem free space or storage-device latency. Preserve query text and detailed logs in access-controlled storage; literals and error detail may contain sensitive application data.
