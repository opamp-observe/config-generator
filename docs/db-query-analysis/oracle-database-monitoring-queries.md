# Oracle Database monitoring SQL: performance, slow queries, locks and internal logs

Research date: 18 October 2026. Scope: Oracle Database 12.2, 19c, 21c and Oracle AI Database 26ai. Legacy releases are included for installed-estate compatibility; inclusion does not imply current support. Oracle states that 26ai replaces 23ai, and the former 23ai documentation redirects to 26ai. Unpatched 23ai installations are not independently certified by this matrix. [Oracle release announcement](https://www.oracle.com/news/announcement/ai-world-database-26ai-powers-the-ai-for-data-revolution-2025-10-14/).

These are operational query patterns assembled from Oracle's documented interfaces. Thresholds and polling intervals are recommendations to tune locally. Compatibility is based on documentation, not execution tests against each release. The structure follows the companion PostgreSQL monitoring document; query identifiers are local to this Oracle document.

## What can be retrieved entirely through SQL?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Queries running slowly now | `GV$SESSION`, `GV$SQL` | Current observation; activity between polls is missed. |
| Expensive statement patterns | `GV$SQL` counter snapshots | Library-cache lifetime; not a complete permanent history. |
| Blocking sessions and lock requests | `GV$SESSION`, `GV$LOCK` | Current state; retain samples to investigate resolved problems. |
| Internal warnings, incidents and recorded errors | `V$DIAG_ALERT_EXT` | Alert log only; not every SQL error or execution is logged here. |
| Trace files without SSH or external forwarding | `V$DIAG_TRACE_FILE`, `V$DIAG_TRACE_FILE_CONTENTS` | Requires diagnostic-view privileges, existing files and available ADR data. |
| Individual recently monitored slow executions | `GV$SQL_MONITOR` | **Optional Tuning Pack feature**; selection and retention are limited. |
| Historical sampled activity / SQL summaries | ASH / AWR | **Optional Diagnostics Pack features**; neither is a complete execution log. |

“Logging that isn't exposed outside the DB” is treated as diagnostic information accessible through a database connection without forwarding files to another service. Oracle's SQL diagnostic views expose ADR-backed files; this does not mean the original files are stored in application tables. Missing or purged history cannot be reconstructed from live counters.

## Prerequisites and collection rules

### Access and scope

Use a dedicated account with `CREATE SESSION` and explicit read privileges on the selected views. A DBA grants privileges against the underlying SYS objects, for example:

```sql
GRANT CREATE SESSION TO monitoring_user;
GRANT SELECT ON SYS.GV_$SESSION TO monitoring_user;
GRANT SELECT ON SYS.GV_$SQL TO monitoring_user;
GRANT SELECT ON SYS.V_$DIAG_ALERT_EXT TO monitoring_user;
```

These are examples, not a complete grant script. Grant the additional underlying `GV_$`/`V_$` objects and dictionary views used by the queries you deploy. Diagnostic text merits narrower access than numeric metrics. Query through the documented public `GV$`/`V$` names; avoid granting `SYSDBA` to collectors. [Dynamic performance view architecture](https://docs.oracle.com/en/database/oracle/oracle-database/19/cncpt/data-dictionary-and-dynamic-performance-views.html?embed=1).

`GV$` adds `INST_ID` and collects qualified instances, making the main queries suitable for RAC and single-instance databases. Run application-level collection through each PDB service. Run database/instance and Data Guard checks through an appropriately privileged administrative connection. A root connection does not automatically see every PDB: common-user grants and `CONTAINER_DATA` control visibility. Include deployment identity, `DBID`, `DB_UNIQUE_NAME`, instance, startup time and `CON_ID` in stored samples. [Global and container data views](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/about-dynamic-performance-views.html), [container privileges](https://docs.oracle.com/en/database/oracle/oracle-database/19/dbseg/managing-commonly-and-locally-granted-privileges.html).

Oracle documents that dynamic views do not guarantee read consistency and recommends copying their data to ordinary tables before complex joins, sorting or aggregation. The joined/ranked examples below are compact diagnostic patterns; for a recurring production collector, stage the required columns from each source with a sample ID and run the joins/ranking against those snapshots, or perform them in the collector. An ordinary transaction does not freeze the underlying live views.

Cumulative counters need consecutive samples: `rate = delta(counter) / elapsed_seconds`. Discard deltas across instance restarts, cursor reloads, changed identities, counter decreases or collection gaps. Do not flush shared pools or reset counters as part of polling. Keep workloads and instance/container totals separate to avoid double-counting root and PDB data.

Bind variables such as `:sql_id` and `:trace_filename` are inputs to supply through your SQL client or collector. Numeric time thresholds below are examples. Dates in dynamic views are not uniformly timezone-bearing; keep database/PDB clocks consistent, particularly when collecting across RAC. Oracle 26ai can manage `SYSDATE`/`SYSTIMESTAMP` per PDB. [26ai behavior changes](https://docs.oracle.com/en/database/oracle/oracle-database/26/upgrd/oracle-database-changes-deprecations-desupports.html).

### Management-pack boundary

| Interface | Treatment in this document |
| --- | --- |
| Ordinary session, SQL-cache, lock, undo, I/O and ADR views, Q01–Q22 | Baseline collection; does not invoke ASH/AWR/SQL Monitor. Database/edition/service entitlements still apply. |
| Real-Time SQL Monitoring, Q23 | Tuning Pack feature; Tuning Pack also requires Diagnostics Pack under the conventional licensing model. |
| ASH and AWR SQL history, Q24–Q25 | Diagnostics Pack features. |

The existence of a view, a successful `SELECT`, or `CONTROL_MANAGEMENT_PACK_ACCESS = DIAGNOSTIC+TUNING` does not establish entitlement. Check your edition and purchased/cloud-service inclusions before enabling Q23–Q25. Oracle also documents exceptions for some `DBA_HIST_*` views, so a blanket claim that every such view requires a pack would be inaccurate. Sources: [19c licensing](https://docs.oracle.com/en/database/oracle/oracle-database/19/dblic/Licensing-Information.html), [26ai licensing](https://docs.oracle.com/en/database/oracle/oracle-database/26/dblic/Licensing-Information.html), [pack-access parameter](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/CONTROL_MANAGEMENT_PACK_ACCESS.html).

## Compatibility matrix

**Y** = uses the documented common interfaces for the indicated release family; privileges and relevant configuration remain prerequisites. **A** = ADR diagnostic access and retained files required. **S** = standby/Data Guard context required. **T** = optional Tuning Pack path. **D** = optional Diagnostics Pack path. **—** = use the alternative query. No cell implies support status, cloud-provider permission, or a live execution test.

| Query name | 12.2 | 19c | 21c | 26ai |
| --- | --- | --- | --- | --- |
| Q01a Environment, common columns | Y | Y | Y | Y |
| Q01b Full release information | — | Y | Y | Y |
| Q02 Active slow executions | Y | Y | Y | Y |
| Q03 Long and idle transactions | Y | Y | Y | Y |
| Q04 Session and wait summary | Y | Y | Y | Y |
| Q05 Blocking relationships | Y | Y | Y | Y |
| Q06 Waiting lock detail | Y | Y | Y | Y |
| Q07 Expensive cached statements | Y | Y | Y | Y |
| Q08 Statement counter snapshot | Y | Y | Y | Y |
| Q09 Cursor collection health | Y | Y | Y | Y |
| Q10 Workload and resource counters | Y | Y | Y | Y |
| Q11 Optimizer statistics candidates | Y | Y | Y | Y |
| Q12 Hot tables and indexes | Y | Y | Y | Y |
| Q13 Undo pressure and snapshot errors | Y | Y | Y | Y |
| Q14 Long-operation progress | Y | Y | Y | Y |
| Q15 Redo and commit waits | Y | Y | Y | Y |
| Q16 File I/O counters | Y | Y | Y | Y |
| Q17 Current temporary-space consumers | Y | Y | Y | Y |
| Q18 Standby transport/apply lag | S | S | S | S |
| Q19 Archive destination status | Y | Y | Y | Y |
| Q20 ADR and trace discovery | A | A | A | A |
| Q21 Selected trace contents | A | A | A | A |
| Q22a Recorded alert errors/warnings | A | A | A | A |
| Q22b Enhanced alert context | — | — | — | A |
| Q23 Individual monitored executions | T | T | T | T |
| Q24 Recent ASH activity | D | D | D | D |
| Q25 Historical AWR SQL summaries | D | D | D | D |

Version-specific points:

- `BANNER_FULL` and `VERSION_FULL` were introduced in 18c, so Q01b is excluded for 12.2. [Version view](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-VERSION.html), [instance view](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-INSTANCE.html).
- Q20/Q21's trace views start at **12.2.0.1**; these examples cannot be transplanted unchanged to 12.1/11g. [12.2 trace metadata](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/refrn/V-DIAG_TRACE_FILE.html), [12.2 trace contents](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/refrn/V-DIAG_TRACE_FILE_CONTENTS.html).
- Q22b uses additional fields documented in 26ai, absent from the compared 19c/21c alert schemas. Use Q22a for their common subset. [19c alert view](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-DIAG_ALERT_EXT.html), [21c alert view](https://docs.oracle.com/en/database/oracle/oracle-database/21/refrn/V-DIAG_ALERT_EXT.html), [26ai alert view](https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/V-DIAG_ALERT_EXT.html).
- Do not infer the product name from the first numeric version component alone: 26ai's documented `VERSION_FULL` examples begin `23.26...`. [Release-number changes](https://docs.oracle.com/en/database/oracle/oracle-database/26/upgrd/oracle-database-changes-deprecations-desupports.html).

Core column continuity: [12.2 session](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/refrn/V-SESSION.html), [19c session](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SESSION.html), [21c session](https://docs.oracle.com/en/database/oracle/oracle-database/21/refrn/V-SESSION.html), [26ai session](https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/V-SESSION.html); SQL-cache definitions for [12.2](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/refrn/V-SQL.html), [19c](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SQL.html), [21c](https://docs.oracle.com/en/database/oracle/oracle-database/21/refrn/V-SQL.html), [26ai](https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/V-SQL.html). Other interfaces are linked beside their queries.

## Query catalogue

### Q01a / Q01b — Environment and configuration

Q01a, common baseline; run at startup/reconnection and after configuration changes:

```sql
SELECT banner FROM v$version;
SELECT inst_id, instance_name, host_name, version, startup_time, status
FROM gv$instance;
SELECT dbid, name, db_unique_name, database_role, open_mode, cdb
FROM v$database;
SELECT sys_context('USERENV', 'CON_NAME') AS container_name,
       sys_context('USERENV', 'CON_ID') AS container_id
FROM dual;
SELECT name, value FROM v$parameter
WHERE name IN ('statistics_level', 'timed_statistics',
               'control_management_pack_access', 'diagnostic_dest',
               'undo_management', 'undo_retention');
```

Q01b, 19c/21c/26ai additional release detail:

```sql
SELECT banner_full FROM v$version;
SELECT inst_id, instance_name, version_full FROM gv$instance;
```

Sources: [`V$VERSION`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-VERSION.html), [`V$INSTANCE`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-INSTANCE.html), [`V$DATABASE`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-DATABASE.html). Record the database role so standby-only checks are routed correctly.

### Q02 — Active slow executions

```sql
SELECT s.inst_id, s.con_id, s.sid, s.serial#, s.username,
       s.module, s.action, s.sql_id, s.sql_child_number,
       s.sql_exec_id, s.sql_exec_start,
       ROUND((SYSDATE - s.sql_exec_start) * 86400, 1) AS elapsed_seconds,
       s.state, s.wait_class, s.event, q.sql_text
FROM gv$session s
LEFT JOIN gv$sql q
  ON q.inst_id = s.inst_id AND q.con_id = s.con_id
 AND q.sql_id = s.sql_id AND q.child_number = s.sql_child_number
WHERE s.type = 'USER' AND s.status = 'ACTIVE'
  AND s.sql_exec_start < SYSDATE - 5/86400
  AND NOT (s.inst_id = TO_NUMBER(sys_context('USERENV', 'INSTANCE'))
           AND s.sid = TO_NUMBER(sys_context('USERENV', 'SID')))
ORDER BY s.sql_exec_start;
```

This measures wall-clock age from execution start, including waits. `LAST_CALL_ET` is active/inactive call age, not a general substitute for SQL execution duration. When `STATE` is not `WAITING`, `EVENT` can describe the previous wait. SQL text can disappear from cache before the join. Source: [`V$SESSION`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SESSION.html).

### Q03 — Long and idle transactions

```sql
SELECT s.inst_id, s.con_id, s.sid, s.serial#, s.username, s.status,
       s.sql_id, s.prev_sql_id, t.start_date,
       ROUND((SYSDATE - t.start_date) * 86400) AS transaction_age_seconds,
       s.last_call_et AS current_state_age_seconds,
       t.used_ublk, t.used_urec
FROM gv$transaction t
JOIN gv$session s
  ON s.inst_id = t.inst_id AND s.taddr = t.addr
WHERE t.start_date < SYSDATE - 60/86400 OR s.status = 'INACTIVE'
ORDER BY t.start_date;
```

Find inactive sessions that still own transactions and undo. Long age alone does not prove a problem. `PREV_SQL_ID` is a clue to the last statement, not a complete transaction history. Sources: [`V$TRANSACTION`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-TRANSACTION.html), [12.2 typed start date](https://docs.oracle.com/en/database/oracle/oracle-database/12.2/refrn/V-TRANSACTION.html).

### Q04 — Session and wait summary

```sql
SELECT inst_id, con_id, status,
       CASE WHEN state = 'WAITING' THEN wait_class ELSE 'NOT WAITING' END
         AS current_wait_class,
       CASE WHEN state = 'WAITING' THEN event END AS current_wait_event,
       COUNT(*) AS sessions
FROM gv$session
WHERE type = 'USER'
GROUP BY inst_id, con_id, status,
         CASE WHEN state = 'WAITING' THEN wait_class ELSE 'NOT WAITING' END,
         CASE WHEN state = 'WAITING' THEN event END;
```

Separate idle connection waits from non-idle active waits. “Not waiting” does not establish CPU saturation. Sample repeatedly to distinguish a sustained issue from a transient event. Source: [21c session state and wait fields](https://docs.oracle.com/en/database/oracle/oracle-database/21/refrn/V-SESSION.html).

### Q05 — Blocking relationships

```sql
SELECT w.inst_id AS waiting_inst, w.con_id, w.sid AS waiting_sid,
       w.serial# AS waiting_serial, w.username AS waiting_user,
       w.event, w.sql_id AS waiting_sql_id,
       w.blocking_instance, w.blocking_session,
       b.serial# AS blocker_serial, b.username AS blocker_user,
       b.status AS blocker_status, b.sql_id AS blocker_sql_id,
       b.prev_sql_id AS blocker_prev_sql_id,
       w.final_blocking_session_status,
       w.final_blocking_instance, w.final_blocking_session
FROM gv$session w
LEFT JOIN gv$session b
  ON b.inst_id = w.blocking_instance AND b.sid = w.blocking_session
WHERE w.blocking_session_status = 'VALID';
```

Joining on instance **and** SID is essential in RAC. Only interpret final-blocker columns when `FINAL_BLOCKING_SESSION_STATUS = 'VALID'`; use that status when automating chain resolution. Samples can race with session termination/SID reuse. Do not terminate blockers automatically from this evidence alone. Source: [26ai session/blocker fields](https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/V-SESSION.html).

### Q06 — Waiting lock detail

```sql
SELECT l.inst_id, l.con_id, l.sid, s.serial#, s.username,
       l.type, l.id1, l.id2, l.lmode, l.request,
       l.ctime AS current_mode_age_seconds, l.block,
       s.state, s.event, s.sql_id
FROM gv$lock l
LEFT JOIN gv$session s ON s.inst_id = l.inst_id AND s.sid = l.sid
WHERE l.request > 0;
```

`TX` is a transaction enqueue; `TM` is a DML enqueue. `CTIME` is time since the current mode was granted, not a universal lock-wait timer. `BLOCK = 2` has RAC-specific meaning. Use Q05 for actual blocker attribution rather than a simplistic resource-ID self-join. Source: [`V$LOCK`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-LOCK.html).

### Q07 — Expensive cached statements

```sql
SELECT inst_id, con_id, sql_id, child_number, plan_hash_value,
       parsing_schema_name, executions,
       ROUND(elapsed_time / NULLIF(executions, 0) / 1000, 2) AS mean_db_ms,
       ROUND(elapsed_time / 1000, 2) AS total_db_ms,
       ROUND(cpu_time / 1000, 2) AS total_cpu_ms,
       buffer_gets, disk_reads, sql_text
FROM gv$sql
WHERE executions >= 5
  AND elapsed_time / NULLIF(executions, 0) >= 1000000
ORDER BY mean_db_ms DESC
FETCH FIRST 50 ROWS ONLY;
```

Rank by total elapsed time instead to find the largest aggregate cost. Oracle's `ELAPSED_TIME` includes parse/execute/fetch database time and can accumulate parallel worker time; mean database time is not necessarily mean user wall time. Cache statistics may include in-progress work and partially fetched executions. Unlike PostgreSQL's typical literal normalization, distinct literal SQL can produce separate Oracle SQL IDs. Source: [`V$SQL`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SQL.html).

### Q08 — Statement counter snapshot

```sql
SELECT SYSTIMESTAMP AS sampled_at, inst_id, con_id, sql_id,
       child_number, child_address, plan_hash_value,
       first_load_time, last_load_time, loads, invalidations,
       executions, end_of_fetch_count, elapsed_time, cpu_time,
       buffer_gets, disk_reads, rows_processed,
       application_wait_time, concurrency_wait_time,
       cluster_wait_time, user_io_wait_time
FROM gv$sql;
```

Key samples by database, startup, instance, container, SQL ID and child incarnation. Retain addresses/load markers as continuity checks; no single marker guarantees perfect continuity through eviction/reload. `delta(elapsed_time) / delta(executions)` is an interval cost estimate, not a precise mean of completed executions where work crosses sample boundaries. Filter to relevant schemas or recently active cursors when full-cache scans are expensive. Source: [21c SQL statistics](https://docs.oracle.com/en/database/oracle/oracle-database/21/refrn/V-SQL.html).

### Q09 — Cursor collection health

```sql
SELECT inst_id, con_id, sql_id, version_count, loaded_versions,
       loads, invalidations, parse_calls, executions, sharable_mem
FROM gv$sqlarea
WHERE version_count >= 20 OR invalidations >= 100
ORDER BY version_count DESC
FETCH FIRST 50 ROWS ONLY;
```

Investigate excessive child versions and reloads; these thresholds are triage examples. Counters disappearing from Q08 usually mean cache churn, not zero activity. This check cannot prove that all executions have been retained. Source: [`V$SQLAREA`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SQLAREA.html).

### Q10 — Workload and resource counters

```sql
SELECT inst_id, con_id, name, value
FROM gv$sysstat
WHERE name IN ('user commits', 'user rollbacks', 'execute count',
               'parse count (total)', 'parse count (hard)',
               'session logical reads', 'physical reads', 'physical writes',
               'physical read total bytes', 'physical write total bytes',
               'sorts (disk)', 'workarea executions - onepass',
               'workarea executions - multipass');
SELECT inst_id, con_id, stat_name, value
FROM gv$sys_time_model
WHERE stat_name IN ('DB time', 'DB CPU', 'sql execute elapsed time',
                    'parse time elapsed', 'hard parse elapsed time');
SELECT inst_id, con_id, resource_name, current_utilization,
       max_utilization, initial_allocation, limit_value
FROM gv$resource_limit
WHERE resource_name IN ('sessions', 'processes', 'transactions');
```

Difference cumulative values; time-model values are microseconds. Current utilization is a gauge and maximum utilization is a high-water mark. Limits can be strings such as `UNLIMITED`; do not blindly cast them to numbers. Sources: [`V$SYSSTAT`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SYSSTAT.html), [`V$SYS_TIME_MODEL`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SYS_TIME_MODEL.html), [`V$RESOURCE_LIMIT`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-RESOURCE_LIMIT.html).

### Q11 — Optimizer statistics candidates

```sql
SELECT owner, table_name, partition_name, subpartition_name,
       object_type, num_rows, last_analyzed, stale_stats, stattype_locked
FROM dba_tab_statistics
WHERE owner = :application_owner
  AND (stale_stats = 'YES' OR last_analyzed IS NULL)
ORDER BY last_analyzed NULLS FIRST
FETCH FIRST 100 ROWS ONLY;
```

Stale/missing statistics are investigation candidates, not an instruction to gather everything. Respect intentional locks and partition/global statistics strategy. `NUM_ROWS` is an estimate at statistics collection time. Source: [table statistics fields](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/ALL_TAB_STATISTICS.html).

### Q12 — Hot tables and indexes

```sql
SELECT inst_id, con_id, owner, object_name, subobject_name,
       object_type, statistic_name, value
FROM gv$segment_statistics
WHERE owner = :application_owner
  AND statistic_name IN ('logical reads', 'physical reads',
                        'physical writes', 'buffer busy waits',
                        'row lock waits', 'ITL waits');
```

Compare deltas by object and statistic to identify hot segments. This is not an unused-index report; low reads do not prove an index is safe to remove. Source: [`V$SEGMENT_STATISTICS`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SEGMENT_STATISTICS.html).

### Q13 — Undo pressure and snapshot errors

```sql
SELECT inst_id, con_id, begin_time, end_time, undoblks, txncount,
       maxquerylen, maxqueryid, tuned_undoretention,
       ssolderrcnt, nospaceerrcnt, unxpstealcnt
FROM gv$undostat
WHERE begin_time >= SYSDATE - 1/24
ORDER BY inst_id, begin_time DESC;
```

These are ten-minute buckets, with a partial current bucket; do not repeatedly sum that bucket on every poll. `SSOLDERRCNT` counts ORA-01555 events, and `NOSPACEERRCNT` counts undo-space failures. This is more useful than importing PostgreSQL's transaction-ID-age/wraparound model into Oracle. Source: [`V$UNDOSTAT`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-UNDOSTAT.html).

### Q14 — Long-operation progress

```sql
SELECT inst_id, con_id, sid, serial#, sql_id, opname, target,
       sofar, totalwork, units,
       ROUND(100 * sofar / NULLIF(totalwork, 0), 1) AS operation_pct,
       elapsed_seconds, time_remaining, last_update_time
FROM gv$session_longops
WHERE totalwork > 0 AND sofar < totalwork
  AND last_update_time > SYSDATE - 10/1440;
```

Covers instrumented operations, not every slow statement. A query can expose multiple operations, so their percentages are not a whole-query completion estimate. Stale entries can remain. Source: [`V$SESSION_LONGOPS`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SESSION_LONGOPS.html).

### Q15 — Redo and commit waits

```sql
SELECT inst_id, con_id, name, value
FROM gv$sysstat
WHERE name IN ('redo size', 'redo entries', 'redo writes',
               'redo log space requests', 'redo buffer allocation retries');
SELECT inst_id, con_id, event, total_waits, time_waited_micro
FROM gv$system_event
WHERE event IN ('log file sync', 'log file parallel write',
                'log buffer space', 'log file switch completion',
                'log file switch (checkpoint incomplete)',
                'log file switch (archiving needed)');
```

Calculate redo bytes/second from `redo size`. Interval mean wait is `delta(time_waited_micro) / delta(total_waits) / 1000` in milliseconds. Correlate with commit rate and log-switch pressure. Sources: [`V$SYSSTAT`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SYSSTAT.html), [`V$SYSTEM_EVENT`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SYSTEM_EVENT.html).

### Q16 — File I/O counters

```sql
SELECT inst_id, con_id, filetype_id, file_no, filetype_name,
       small_read_megabytes, large_read_megabytes,
       small_write_megabytes, large_write_megabytes,
       small_read_reqs, large_read_reqs,
       small_write_reqs, large_write_reqs,
       small_read_servicetime, large_read_servicetime,
       small_write_servicetime, large_write_servicetime
FROM gv$iostat_file;
```

Use request and service-time deltas for interval latency; service times here are milliseconds. Small/large operations and file types should remain distinct. Other file types may be consolidated rather than represented per individual file. Source: [`V$IOSTAT_FILE`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-IOSTAT_FILE.html).

### Q17 — Current temporary-space consumers

Run through the relevant PDB service so local tablespace metadata matches usage:

```sql
SELECT u.inst_id, u.con_id, s.sid, s.serial#, u.username,
       u.sql_id, u.tablespace, u.segtype,
       u.blocks, u.blocks * t.block_size AS allocated_bytes
FROM gv$tempseg_usage u
JOIN dba_tablespaces t ON t.tablespace_name = u.tablespace
LEFT JOIN gv$session s
  ON s.inst_id = u.inst_id AND s.saddr = u.session_addr
 AND s.serial# = u.session_num;
```

This is current allocated temporary segment space, not cumulative bytes spilled. Do not join root-level usage to dictionary data by tablespace name alone across multiple PDBs; use container-aware metadata if centralizing. Source: [`V$TEMPSEG_USAGE`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-TEMPSEG_USAGE.html).

### Q18 — Standby transport/apply lag

```sql
SELECT name, value, unit, time_computed, datum_time
FROM v$dataguard_stats
WHERE name IN ('transport lag', 'apply lag', 'apply finish time');
```

Run on the standby, normally via an administrative connection to the applying instance; the primary returns no rows. An unchanged `DATUM_TIME` can indicate no new source data, even if the displayed lag looks small. This query does not itself require opening a standby for application queries. Source: [`V$DATAGUARD_STATS`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-DATAGUARD_STATS.html).

### Q19 — Archive destination status

```sql
SELECT inst_id, dest_id, dest_name, status, type, destination,
       error, archived_thread#, archived_seq#,
       applied_thread#, applied_seq#, gap_status
FROM gv$archive_dest_status
WHERE status <> 'INACTIVE';
```

Review local archive errors as well as remote transport destinations. Sequence gaps alone are not time-lag estimates, especially across RAC redo threads. Source: [`V$ARCHIVE_DEST_STATUS`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-ARCHIVE_DEST_STATUS.html).

## Internal server logs and historical events

### Recommended logging baseline

Retain ADR alert and diagnostic files for your incident investigation window. Use Q20 to discover ADR locations, Q22 to retrieve recorded errors, and selective SQL tracing when individual call detail is necessary. Oracle does not offer a directly equivalent, universal `log_min_duration_statement` alert-log switch for every application SQL execution.

For selective tracing, a DBA can enable waits and disable bind capture for a specific target session:

```sql
BEGIN
  DBMS_MONITOR.SESSION_TRACE_ENABLE(
    session_id => :target_sid, serial_num => :target_serial,
    waits => TRUE, binds => FALSE);
END;
/
-- Reproduce or observe the bounded workload, then disable on the same instance.
BEGIN
  DBMS_MONITOR.SESSION_TRACE_DISABLE(
    session_id => :target_sid, serial_num => :target_serial);
END;
/
```

This is an administrative change, separate from read-only monitoring. Target the correct RAC instance; SID/serial alone is not a cluster-wide address. Service/module/action tracing is another option for pooled connections. Trace volume and overhead require a bounded capture window. `binds => FALSE` avoids bind-value tracing but SQL literals can still be present. Sources: [`DBMS_MONITOR`](https://docs.oracle.com/en/database/oracle/oracle-database/19/arpls/DBMS_MONITOR.html), [application tracing](https://docs.oracle.com/en/database/oracle/oracle-database/19/tgsql/performing-application-tracing.html).

### Q20 — ADR and trace discovery

```sql
SELECT name, value FROM v$diag_info;
SELECT adr_home, trace_filename, change_time, modify_time, con_id
FROM v$diag_trace_file
WHERE modify_time >= SYSTIMESTAMP - INTERVAL '1' HOUR
ORDER BY modify_time DESC
FETCH FIRST 50 ROWS ONLY;
```

Run on the instance/container holding the diagnostic data. `Default Trace File` describes the current process, not an arbitrary application session. ADR cleanup or provider restrictions can limit visibility. Sources: [`V$DIAG_INFO`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-DIAG_INFO.html), [`V$DIAG_TRACE_FILE`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-DIAG_TRACE_FILE.html).

### Q21 — Selected trace contents

```sql
SELECT adr_home, trace_filename, timestamp AS trace_timestamp,
       record_type, section_id, section_name,
       session_id, serial#, payload, con_id
FROM v$diag_trace_file_contents
WHERE adr_home = :adr_home
  AND trace_filename = :trace_filename
  AND (timestamp >= SYSTIMESTAMP - INTERVAL '1' HOUR OR timestamp IS NULL)
FETCH FIRST 500 ROWS ONLY;
```

This retrieves a bounded **fragment**, without guaranteeing physical file order. Null timestamps and freeform records matter; a strict timestamp-only filter can omit useful context. Do not sort by `LINE_NUMBER` as though it were a file-record offset: Oracle defines it as a code-source line number. For complete SQL Trace interpretation use the complete trace and a trace-aware parser/TKPROF; individual payload rows are not a ready-made slow-query table. Sources: [19c contents fields](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-DIAG_TRACE_FILE_CONTENTS.html), [26ai contents fields](https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/V-DIAG_TRACE_FILE_CONTENTS.html).

### Q22a / Q22b — Recorded alert errors and warnings

Q22a, common alert-log fields:

```sql
SELECT originating_timestamp, con_id, message_type, message_level,
       problem_key, message_text, detailed_location,
       filename, record_id
FROM v$diag_alert_ext
WHERE originating_timestamp >= SYSTIMESTAMP - INTERVAL '1' HOUR
  AND (message_type IN (2, 3, 4) OR message_text LIKE '%ORA-00060%')
ORDER BY originating_timestamp DESC, record_id DESC
FETCH FIRST 200 ROWS ONLY;
```

Incident errors, errors and warnings have message types 2, 3 and 4. ORA-00060 identifies a recorded deadlock; diagnostic detail may be in a referenced trace file. Many application errors never enter the alert log, so this is not a complete database error audit. Source: [19c alert view](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-DIAG_ALERT_EXT.html).

Q22b, additional context in the 26ai documented schema:

```sql
SELECT originating_timestamp, con_id, message_text,
       cause_text, action_text, sql_id, session_id, target_user,
       filename, record_id
FROM v$diag_alert_ext
WHERE originating_timestamp >= SYSTIMESTAMP - INTERVAL '1' HOUR
  AND message_type IN (2, 3, 4)
ORDER BY originating_timestamp DESC, record_id DESC
FETCH FIRST 200 ROWS ONLY;
```

Source: [26ai alert context](https://docs.oracle.com/en/database/oracle/oracle-database/26/refrn/V-DIAG_ALERT_EXT.html). The extra fields may be null for a particular message.

For recurring retrieval, keep a small overlapping time window and deduplicate using deployment/ADR identity, container, filename and record ID. Timestamp alone is not a reliable cursor. Fetch all pages before advancing a watermark; the example row limit is for diagnostics, not an ingestion completeness guarantee. If retained data must stay inside Oracle, a DBA-managed ordinary table can preserve selected results before ADR purge; implement retention and deduplication rather than repeatedly appending the whole window.

### Q23 — Individual monitored executions (optional Tuning Pack)

**Only deploy after confirming entitlement.**

```sql
SELECT inst_id, con_id, sql_id, sql_exec_id, sql_exec_start,
       sid, session_serial#, status,
       ROUND(elapsed_time / 1000, 2) AS elapsed_ms,
       ROUND(cpu_time / 1000, 2) AS cpu_ms,
       buffer_gets, physical_read_bytes, physical_write_bytes, sql_text
FROM gv$sql_monitor
WHERE sql_exec_start >= SYSDATE - 1/24
  AND elapsed_time >= 1000000
  AND px_qcsid IS NULL
ORDER BY elapsed_time DESC
FETCH FIRST 100 ROWS ONLY;
```

Retains active and recently completed monitored executions; filter `STATUS <> 'EXECUTING'` if you only want finished rows, while interpreting other statuses explicitly. `PX_QCSID IS NULL` removes parallel-worker rows so the coordinator/serial rows form the primary execution list. Treat SQL ID, execution ID, start time and instance as execution identity.

Automatic monitoring commonly selects parallel statements or statements consuming at least five seconds of CPU/I/O; a one-second filter here does **not** make all one-second wall-clock executions visible. This is an in-memory monitoring window, not durable slow-query logging. Sources: [`V$SQL_MONITOR`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-SQL_MONITOR.html), [monitoring selection and retention](https://docs.oracle.com/en/database/oracle/oracle-database/19/tgsql/monitoring-database-operations.html).

### Q24 — Recent ASH activity (optional Diagnostics Pack)

```sql
SELECT inst_id, con_id, sql_id, session_state, wait_class, event,
       COUNT(*) AS activity_samples
FROM gv$active_session_history
WHERE sample_time >= LOCALTIMESTAMP - INTERVAL '10' MINUTE
  AND session_type = 'FOREGROUND'
GROUP BY inst_id, con_id, sql_id, session_state, wait_class, event
ORDER BY activity_samples DESC
FETCH FIRST 50 ROWS ONLY;
```

ASH samples active sessions; sample counts are neither execution counts nor exact query runtimes. Null SQL IDs and parallel-worker samples need interpretation. The memory window varies with workload and buffer size. Source: [`V$ACTIVE_SESSION_HISTORY`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/V-ACTIVE_SESSION_HISTORY.html).

### Q25 — Historical AWR SQL summaries (optional Diagnostics Pack)

```sql
SELECT st.dbid, st.instance_number, st.con_id, st.sql_id, st.plan_hash_value,
       SUM(st.executions_delta) AS executions,
       ROUND(SUM(st.elapsed_time_delta) / 1000, 2) AS total_db_ms,
       ROUND(SUM(st.elapsed_time_delta) /
             NULLIF(SUM(st.executions_delta), 0) / 1000, 2) AS mean_db_ms
FROM dba_hist_sqlstat st
JOIN dba_hist_snapshot sn
  ON sn.dbid = st.dbid AND sn.instance_number = st.instance_number
 AND sn.snap_id = st.snap_id
WHERE st.dbid = :dbid
  AND sn.end_interval_time >= LOCALTIMESTAMP - INTERVAL '1' DAY
GROUP BY st.dbid, st.instance_number, st.con_id, st.sql_id, st.plan_hash_value
HAVING SUM(st.executions_delta) > 0
ORDER BY total_db_ms DESC
FETCH FIRST 50 ROWS ONLY;
```

Use this database-level form from the administrative root/non-CDB context with the intended AWR repository visible. PDB-local AWR repositories require explicit repository/container scoping rather than combining them with root history. The selected snapshots can straddle the requested boundary. AWR captures selected SQL, and interval work can cross execution boundaries; these totals are not a complete individual execution history. Sources: [`DBA_HIST_SQLSTAT`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/DBA_HIST_SQLSTAT.html), [`DBA_HIST_SNAPSHOT`](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/DBA_HIST_SNAPSHOT.html).

## Deeper diagnosis and rollout

For a chosen cursor, inspect its actual cached execution plan on the instance holding it:

```sql
SELECT *
FROM TABLE(DBMS_XPLAN.DISPLAY_CURSOR(:sql_id, :child_number,
                                   'ALLSTATS LAST'));
```

`ALLSTATS LAST` needs row-source statistics captured for that execution, for example through controlled use of `gather_plan_statistics` or session instrumentation; absent data is not evidence of zero work. This does not execute the SQL again. `DISPLAY_AWR` is a different history path with Diagnostics Pack implications. Source: [`DBMS_XPLAN`](https://docs.oracle.com/en/database/oracle/oracle-database/19/arpls/DBMS_XPLAN.html).

Suggested rollout:

1. Establish Q01 metadata and view privileges; leave Q23–Q25 out of the collector unless entitled.
2. Poll Q02–Q04 every 15–30 seconds. Retrieve Q05/Q06 during lock waits or incident investigation.
3. Capture Q08/Q10/Q12/Q15/Q16 every 30–60 seconds. Derive rates from validated deltas and stage data before complex analysis.
4. Check Q11/Q13/Q14/Q17–Q19 every 1–5 minutes; run Q18 on standby instances and include datum freshness.
5. Poll bounded alert windows through Q22 and verify pagination/deduplication. Query selected trace files through Q20/Q21 when needed, rather than scanning every file continuously.
6. Validate overhead, RAC instance joins, PDB visibility and version-specific columns against the exact release update before production deployment.

SQL exposes extensive internal state but does not replace host/container measurements for CPU saturation, filesystem free space, storage-device latency or listener/service behavior outside the database. Protect SQL text, trace payloads and diagnostic messages as application data.
