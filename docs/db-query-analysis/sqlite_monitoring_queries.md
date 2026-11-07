<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0. See license.txt in the project root.
-->

# SQLite monitoring SQL and APIs: performance, slow queries, locks and diagnostics

## Scope and interpretation

Scope: SQLite 3.37 through 3.54, with compatibility landmarks at 3.37, 3.46, 3.53 and 3.54. SQLite is an embedded C library, not a database server. Monitoring therefore belongs primarily inside each application process and database connection; a separate SQL collector cannot enumerate other processes' connections, running statements, transactions or errors.

These are operational SQL/PRAGMA and C API patterns assembled from SQLite's documented interfaces. Wrapper libraries expose the same capabilities under language-specific names. Confirm which SQLite library version and compile options the application actually loaded rather than relying on an operating-system package version.

## What can be retrieved entirely through SQL?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Library identity and compile features | `sqlite_version()`, `sqlite_source_id()`, `PRAGMA compile_options` | Describes the current connection's loaded library. |
| Attached files and connection settings | `PRAGMA database_list` and configuration PRAGMAs | Connection-local; other processes can differ. |
| Database/page/free-list state | page-count/page-size/free-list PRAGMAs | Snapshot for the selected schema; WAL bytes are separate. |
| Schema, indexes and planner statistics | `sqlite_schema`, table-valued PRAGMAs, `sqlite_stat1` | Statistics exist only after analysis; estimates are not runtime counters. |
| Integrity and foreign-key checks | `quick_check`, `integrity_check`, `foreign_key_check` | Can be expensive and are checks, not passive metrics. |
| WAL checkpoint state | `PRAGMA wal_checkpoint(NOOP)` where supported | Connection/file state only; compatibility and busy results require care. |
| Running/slow statements | Application instrumentation | No SQL process list or query-history table. |
| Lock blockers and transactions in other processes | Not available through SQL | Instrument busy handling and application connection ownership. |
| Internal server logs | Not applicable | SQLite has no server process; use error-log and trace callbacks. |

“Entirely through SQL” is intentionally limited. Opening an extra monitoring connection can itself affect locks, WAL checkpoints and file lifetime.

## Prerequisites and collection rules

Run passive metadata queries through an application-owned connection or a deliberately read-only monitoring connection. Use URI `mode=ro` or `PRAGMA query_only=ON` where appropriate, but understand that some temporary/internal writes and connection setup behavior depend on the build/VFS. Do not run repair, checkpoint, `VACUUM`, `ANALYZE`, `REINDEX` or write PRAGMAs from a read-only poller.

SQLite PRAGMAs are version-specific; unknown PRAGMAs can be silently ignored. Check `sqlite_version()` and verify returned column shape. Many settings are per connection, so sampling one connection does not prove the configuration of every connection in the application.

Prefer in-process monotonic timing around prepare/step/finalize plus `sqlite3_trace_v2()` profile events and `sqlite3_stmt_status()` counters. Redact expanded bind values. A trace callback runs on the executing thread and must be fast, non-blocking and non-reentrant for the same connection.

## Compatibility matrix

**Y** = documented common interface. **V** = available/shape depends on release or compile option. **A** = application API, not SQL. **W** = performs work or can change state.

| Query or interface | 3.37 | 3.46 | 3.53 | 3.54 |
| --- | --- | --- | --- | --- |
| Q01 Library identity | Y | Y | Y | Y |
| Q02 Attached databases | Y | Y | Y | Y |
| Q03 Connection configuration | Y | Y | Y | Y |
| Q04 Schema objects | Y | Y | Y | Y |
| Q05 Object size via `dbstat` | V | V | V | V |
| Q06 Planner statistics | V | V | V | V |
| Q07 Page and free-list state | Y | Y | Y | Y |
| Q08 Passive WAL status | — | — | Y | Y |
| Q09 Data/schema change indicators | Y | Y | Y | Y |
| Q10 Foreign-key check | W | W | W | W |
| Q11 Quick integrity check | W | W | W | W |
| Q12 Optimize recommendation | W | W | W | W |
| Q13 Transaction state API | A | A | A | A |
| Q14 Trace/profile API | A | A | A | A |
| Q15 Statement counters | A | A | A | A |
| Q16 Connection status | A | A | A | A |
| Q17 Process-wide status | A | A | A | A |
| Q18 Error-log callback | A | A | A | A |

SQLite 3.46 changed `PRAGMA optimize` so its internal analysis work is automatically bounded. SQLite 3.53 fixed a WAL-reset corruption issue present in affected earlier releases; use a current patch release rather than treating a feature matrix as a security/bug-support policy. [Release history](https://sqlite.org/changes.html).

## Query catalogue

### Q01 — Library identity

```sql
SELECT sqlite_version() AS sqlite_version,
       sqlite_source_id() AS sqlite_source_id,
       CURRENT_TIMESTAMP AS sampled_at;

PRAGMA compile_options;
```

Capture both values from the actual application connection. Different processes on one host can load different SQLite libraries. Compile options determine availability of features such as `dbstat`, FTS and statement scan status.

### Q02 — Attached databases

```sql
PRAGMA database_list;
```

Returns sequence, schema name and filename for the current connection. The filename can be empty for temporary or in-memory databases and is sensitive deployment information. Source: [PRAGMA reference](https://www.sqlite.org/pragma.html#pragma_database_list).

### Q03 — Connection configuration

```sql
PRAGMA main.journal_mode;
PRAGMA main.synchronous;
PRAGMA main.locking_mode;
PRAGMA main.cache_size;
PRAGMA main.mmap_size;
PRAGMA main.wal_autocheckpoint;
PRAGMA busy_timeout;
PRAGMA foreign_keys;
PRAGMA read_uncommitted;
PRAGMA query_only;
PRAGMA temp_store;
```

Issue these as separate statements. Values are connection- or schema-scoped and some can change during application lifetime. Reading is passive; assigning a value would be a configuration change.

### Q04 — Schema objects

```sql
SELECT type,
       name,
       tbl_name,
       rootpage,
       sql
FROM main.sqlite_schema
WHERE name NOT LIKE 'sqlite_%'
ORDER BY type, name;

PRAGMA main.table_list;
```

`PRAGMA table_list` was introduced in 3.37 and can add columns in future releases. Schema SQL can expose application details; store it only when needed.

### Q05 — Object size via `dbstat`

Requires the `dbstat` virtual table to be available:

```sql
SELECT name,
       SUM(pgsize) AS allocated_bytes,
       SUM(payload) AS payload_bytes,
       SUM(unused) AS unused_bytes,
       COUNT(*) AS page_count
FROM dbstat
GROUP BY name
ORDER BY allocated_bytes DESC;
```

`dbstat` reports database pages, not WAL/journal files or filesystem allocation. Availability depends on the build. Its view is a snapshot and concurrent writers can change it.

### Q06 — Planner statistics

First check whether statistics exist:

```sql
SELECT name
FROM main.sqlite_schema
WHERE type = 'table' AND name IN ('sqlite_stat1', 'sqlite_stat4');
```

If `sqlite_stat1` exists:

```sql
SELECT tbl, idx, stat
FROM main.sqlite_stat1
ORDER BY tbl, idx;
```

Statistics are optimizer inputs, not current row counts. `sqlite_stat4` is compile-option dependent and contains sampled values that can be sensitive.

### Q07 — Page and free-list state

```sql
PRAGMA main.page_size;
PRAGMA main.page_count;
PRAGMA main.freelist_count;
PRAGMA main.max_page_count;
PRAGMA main.auto_vacuum;
PRAGMA main.encoding;
```

Approximate main-file logical bytes as `page_size * page_count`; free-list bytes as `page_size * freelist_count`. This excludes WAL/journal/shared-memory files and filesystem overhead. Free pages are reusable and do not by themselves justify `VACUUM`.

### Q08 — Passive WAL status

On SQLite 3.51 and later, which introduced the `NOOP` mode:

```sql
PRAGMA main.wal_checkpoint(NOOP);
```

The result is `busy`, total WAL frames and checkpointed frames. Values of `-1` indicate no WAL. Do not substitute `FULL`, `RESTART` or `TRUNCATE` in a monitor: those modes wait and/or change checkpoint state. If `NOOP` is unavailable in a supported legacy build, obtain WAL metrics through `sqlite3_wal_hook()` and filesystem telemetry instead. [WAL checkpoint PRAGMA](https://www.sqlite.org/pragma.html#pragma_wal_checkpoint).

### Q09 — Data and schema change indicators

```sql
PRAGMA main.data_version;
PRAGMA main.schema_version;
PRAGMA main.user_version;
PRAGMA main.application_id;
```

`data_version` is useful only by comparing repeated reads on the same connection; it changes when another connection commits. It is not a global monotonically increasing transaction ID. Application and user version are application-managed metadata.

### Q10 — Foreign-key check

```sql
PRAGMA main.foreign_key_check;
```

Each row is a violation; an empty result means none were found in the checked scope. This scans data and can be expensive/locking on large databases. Run on a schedule or offline copy, not at a high polling rate.

### Q11 — Quick integrity check

```sql
PRAGMA main.quick_check;
```

A healthy result is a single `ok` row. The check performs substantial reads and is not a continuous metric. `integrity_check` is more comprehensive and more expensive. Neither proves storage hardware durability or validates foreign keys. Source: [integrity-check PRAGMAs](https://www.sqlite.org/pragma.html#pragma_quick_check).

### Q12 — Optimize recommendation

```sql
PRAGMA optimize;
```

This is maintenance, not a passive query. Since 3.46, SQLite automatically limits the scope of any analysis it chooses to run. Applications with long-lived connections should consider `PRAGMA optimize=0x10002` on open and `PRAGMA optimize` periodically; short-lived connections can run it before close. Apply through the owning application, not an external collector. [ANALYZE recommended usage](https://www.sqlite.org/lang_analyze.html).

## Application-level runtime instrumentation

### Q13 — Transaction state

```c
int transaction_state = sqlite3_txn_state(database_connection, "main");
```

The result identifies no transaction, a read transaction or a write transaction for one connection/schema. It cannot inspect another process's connections. Pass `NULL` only when the intended aggregate behavior across attached schemas is understood. [Transaction state](https://www.sqlite.org/c3ref/txn_state.html).

### Q14 — Statement tracing and duration

```c
sqlite3_trace_v2(
    database_connection,
    SQLITE_TRACE_STMT | SQLITE_TRACE_PROFILE | SQLITE_TRACE_CLOSE,
    trace_callback,
    callback_context);
```

Use `SQLITE_TRACE_PROFILE` completion events for duration and `SQLITE_TRACE_STMT` for identity. Avoid expanded SQL when bind values are sensitive. Each connection has at most one trace callback; installing a collector must not silently replace an application's existing callback. Source: [`sqlite3_trace_v2`](https://sqlite.org/c3ref/trace_v2.html).

### Q15 — Prepared-statement counters

```c
int full_scan_steps = sqlite3_stmt_status(
    prepared_statement, SQLITE_STMTSTATUS_FULLSCAN_STEP, 0);
int sort_operations = sqlite3_stmt_status(
    prepared_statement, SQLITE_STMTSTATUS_SORT, 0);
int virtual_machine_steps = sqlite3_stmt_status(
    prepared_statement, SQLITE_STMTSTATUS_VM_STEP, 0);
int automatic_indexes = sqlite3_stmt_status(
    prepared_statement, SQLITE_STMTSTATUS_AUTOINDEX, 0);
```

Sample after execution and before finalizing the statement. Reset only when the application's interval accounting is designed for it. High full-scan steps are candidates for plan review, not proof an index is required. Source: [`sqlite3_stmt_status`](https://www.sqlite.org/c3ref/stmt_status.html).

### Q16 — Connection status

```c
int current_value = 0;
int highwater_value = 0;
int result_code = sqlite3_db_status(
    database_connection,
    SQLITE_DBSTATUS_CACHE_USED,
    &current_value,
    &highwater_value,
    0);
```

Repeat for relevant `SQLITE_DBSTATUS_*` operations such as cache use/hit/miss, lookaside use, schema memory, statement memory and deferred foreign keys. SQLite 3.51 added `sqlite3_db_status64()` for values that can exceed 32 bits; use it when the loaded library provides it. Always check the result code. Source: [database connection status](https://www.sqlite.org/c3ref/db_status.html).

### Q17 — Process-wide SQLite status

```c
sqlite3_int64 current_value = 0;
sqlite3_int64 highwater_value = 0;
int result_code = sqlite3_status64(
    SQLITE_STATUS_MEMORY_USED,
    &current_value,
    &highwater_value,
    0);
```

This covers SQLite-library state inside the process, not total process memory. Operations include memory, page-cache, scratch and allocator counters depending on the build. Resetting high-water values changes observability state. Source: [`sqlite3_status64`](https://www.sqlite.org/c3ref/status.html).

## Internal errors and historical events

### Recommended logging baseline

SQLite has no server log. Capture errors at every API boundary using the primary and extended result codes, `sqlite3_errmsg()`, operation identity, database/schema identity and application request correlation. Do not log bound values by default.

### Q18 — Global SQLite error-log callback

Before SQLite initialization, configure the process-wide log callback:

```c
int config_result = sqlite3_config(
    SQLITE_CONFIG_LOG,
    sqlite_log_callback,
    callback_context);
```

The callback receives selected internal warnings/errors, not every returned application error. Configuration timing matters: most `sqlite3_config()` options must be set before library initialization. Keep the callback bounded and thread-safe. [Error logging interface](https://www.sqlite.org/errlog.html).

For a durable slow-query history, the application must create it from Q14/Q15 measurements or export telemetry. Keep bounded text/hash, duration, result/extended result code, row count, full-scan/sort counters, connection role and timestamps. There is no history to query retroactively if the application did not record it.

## Deeper diagnosis and rollout

For a chosen statement, run:

```sql
EXPLAIN QUERY PLAN
SELECT /* selected read-only statement */ 1;
```

Replace the example with the exact safely bound statement in a controlled environment. `EXPLAIN QUERY PLAN` output is intended for interactive debugging and its format can change; do not build a version-independent production parser around the description text. [EXPLAIN QUERY PLAN](https://www.sqlite.org/eqp.html).

Suggested rollout:

1. Instrument every application connection with Q01 identity and Q14 duration/error events.
2. Add Q15 counters for known expensive statement families and Q16/Q17 memory/cache telemetry at a modest interval.
3. Capture Q02–Q09 when a connection opens and periodically only where their cost is justified.
4. Schedule Q10/Q11 on a maintenance connection or validated snapshot, not a latency-sensitive production path.
5. Run Q12 through application lifecycle hooks and record whether it performed analysis work.
6. Instrument busy/locked result codes, busy-handler wait duration, WAL hooks and transaction ownership; SQL cannot identify another process's blocker.
7. Validate the loaded SQLite version, compile options, VFS behavior, wrapper semantics and overhead on every deployment target.

SQLite monitoring is application observability. SQL/PRAGMA snapshots do not replace filesystem free-space and latency checks, WAL/journal file monitoring, process resource metrics, backup validation or error handling at each API call.
