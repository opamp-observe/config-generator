# MySQL monitoring SQL: performance, slow queries, locks and internal logs

## Scope and interpretation

Scope: Oracle MySQL 5.7, 8.0 and 8.4 release families, principally InnoDB, using SQL. 5.7 is included for installed-estate compatibility, not as a recommendation or support-status claim. 

Later innovation/rebranded release families are outside this matrix. MariaDB, Aurora, Percona and other compatible products require product-specific validation.

Query IDs are local to this document. Examples were checked against vendor documentation, not executed on live database servers. Thresholds and collection intervals are starting points to benchmark locally.

## What can be retrieved entirely through SQL?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Currently slow statements | Performance Schema statements + threads | Needs statement instrumentation and timers. |
| Expensive normalized patterns | events_statements_summary_by_digest | Finite in-memory capacity, resets and overflow. |
| Lock blocking | data_lock_waits on 8.x; INNODB_LOCK_WAITS on 5.7 | Current state only; metadata locks are separate. |
| Completed individual slow statements | mysql.slow_log with TABLE output | Slow logging must have been enabled beforehand. |
| Recent statement errors | Statement history + MYSQL_ERRNO | Volatile bounded history, not every client error. |
| Server errors/warnings | performance_schema.error_log, 8.0.22+ | In-memory ring; appropriate log sink required. |
| Latest deadlock | SHOW ENGINE INNODB STATUS | Latest InnoDB deadlock only; not a deadlock archive. |

“Internal” means retrievable over an authenticated DB connection without publishing files or using SSH. mysql.slow_log is table-resident when TABLE output is selected. performance_schema.error_log is a bounded diagnostic buffer, not a regular durable log table. MySQL recovery redo/binlogs are not substitutes for an application-error journal.

## Prerequisites and collection rules

Use a dedicated monitoring account. Grant SELECT on only required Performance Schema tables, information-schema visibility, and SELECT on mysql.slow_log if deploying Q22. PROCESS is needed for complete cross-session process/transaction visibility and SHOW ENGINE INNODB STATUS; avoid SUPER for a read-only collector. Reading threads exposes information about other sessions, so Performance Schema table access is itself sensitive. Configuring instrumentation, logging or replication is an operator action, not a read-only permission. Consult each interface's access rules; managed services may restrict them.

Examples do not need the sys schema. Performance Schema must be enabled at server startup, and the relevant instruments, consumers and thread INSTRUMENTED/HISTORY settings must allow collection. Metadata/stage/history instrumentation can be disabled by default. Q09 inspects this state; an empty table does not prove absence of problems. [Performance Schema privileges](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-table-characteristics.html), [setup consumers](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-setup-consumers-table.html), [InnoDB diagnostics](https://dev.mysql.com/doc/refman/8.4/en/innodb-information-schema-transactions.html).

Run against each physical instance: primary and replica counters have different meaning. Include server_uuid, server_id, version, uptime, role/channel and UTC sample time in retained samples. Replace appdb where used. Snippets are independent; SET time_zone in Q01 applies only to that client session.

Most Performance Schema timers are picoseconds: divide by 1e12 for seconds or 1e9 for milliseconds. They are not Unix timestamps. Use consecutive counter snapshots, discard intervals crossing restart/reset/decrease and preserve unsigned integer precision. Digest eviction/overflow and history rollover can lose evidence. Do not TRUNCATE summary tables or FLUSH STATUS as part of scraping.

Limit text length and restrict access to SQL/log payloads, which can include literals and sensitive values. LIMIT bounds returned rows, not necessarily work scanned by a sort. Frequent queries against unindexed CSV log tables can be expensive.

## Compatibility matrix

Y = documented common interface; P = Performance Schema instrumentation/consumer required; I = InnoDB; R = configured replication channel; T = prior slow logging to TABLE; E = working error-log sink/buffer. A release marker is a minimum patch level. — = use the alternative or unavailable. Cells are documentation-based, not runtime certification.

| Query name | 5.7 | 8.0 | 8.4 |
| --- | --- | --- | --- |
| Q01 Environment and configuration | Y | Y | Y |
| Q02 Active slow statements | P | P | P |
| Q03 Long and idle transactions | I | I | I |
| Q04 Session and wait summary | P | P | P |
| Q05a Blocking relationships, data_lock_waits | — | I (8.0.1+) | I |
| Q05b Blocking relationships, legacy | I | — | — |
| Q06 Metadata lock detail | P | P | P |
| Q07 Expensive statement patterns | P | P | P |
| Q08 Statement counter snapshot | P | P | P |
| Q09 Instrumentation collection health | P | P | P |
| Q10 Workload and connection counters | P | P | P |
| Q11 Table storage and maintenance candidates | Y | Y | Y |
| Q12 Index usage | P | P | P |
| Q13 InnoDB cache and transaction pressure | I | I | I |
| Q14 Long-operation stage progress | P | P | P |
| Q15 Redo and commit pressure | I | I | I |
| Q16 File I/O counters | P | P | P |
| Q17 Statement spill and scan candidates | P | P | P |
| Q18a Replica lag and state, REPLICA syntax | — | R (8.0.22+) | R |
| Q18b Replica lag and state, legacy syntax | R | R (before 8.0.22) | — |
| Q19 Replication worker errors | R | R | R |
| Q20 Logging configuration | Y | Y | Y |
| Q21 Recent internal server errors | — | E (8.0.22+) | E |
| Q22 Historical slow executions | T | T | T |
| Q23 Recently completed statement errors | P | P | P |
| Q24 Error counter summary | — | P | P |
| Q25 Latest InnoDB deadlock | I | I | I |

Important boundaries: data_locks/data_lock_waits replace the removed legacy InnoDB lock tables in 8.0; error_log begins at 8.0.22. SHOW REPLICA STATUS begins at 8.0.22; use SHOW SLAVE STATUS on 5.7/older 8.0. The queries avoid newer 8.0-only digest quantiles and sample-text columns in their common paths. Error summary tables are an 8.x path, not a 5.7 fallback.

Sources: [Performance Schema table/version reference](https://dev.mysql.com/doc/mysqld-version-reference/en/performance-schema-tables.html), [8.0 lock tables](https://dev.mysql.com/doc/refman/8.0/en/performance-schema-lock-tables.html), [5.7 lock waits](https://docs.oracle.com/cd/E17952_01/mysql-5.7-en/information-schema-innodb-lock-waits-table.html), [REPLICA syntax](https://dev.mysql.com/doc/refman/8.0/en/show-replica-status.html).

## Query catalogue

### Q01 — Environment and configuration

Instance identity and the selected collector session timezone.

~~~sql
SET SESSION time_zone='+00:00';
SELECT UTC_TIMESTAMP(6) AS captured_utc,VERSION() AS version,
 @@version_comment AS version_comment,@@server_uuid AS server_uuid,
 @@server_id AS server_id,@@hostname AS hostname,@@port AS port,
 @@performance_schema AS performance_schema_enabled;
SHOW GLOBAL STATUS LIKE 'Uptime';
SHOW GLOBAL VARIABLES WHERE Variable_name IN
 ('read_only','super_read_only','max_connections','innodb_buffer_pool_size');
~~~

Using a session timezone avoids changing application sessions. mysql.slow_log TIMESTAMP values follow the reader session timezone; Performance Schema elapsed timers do not.

Sources: [Server status variables](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html).

### Q02 — Active slow statements

Foreground statements currently running for at least five seconds.

~~~sql
SELECT t.THREAD_ID,t.PROCESSLIST_ID,t.PROCESSLIST_USER,t.PROCESSLIST_HOST,
 t.PROCESSLIST_DB,t.PROCESSLIST_STATE,e.EVENT_ID,
 e.TIMER_WAIT/1000000000000 AS elapsed_seconds,
 e.LOCK_TIME/1000000000000 AS lock_seconds,
 e.ROWS_EXAMINED,e.ROWS_SENT,LEFT(e.SQL_TEXT,4000) AS sql_text
FROM performance_schema.threads AS t
JOIN performance_schema.events_statements_current AS e
 ON e.THREAD_ID=t.THREAD_ID
WHERE t.TYPE='FOREGROUND' AND t.PROCESSLIST_ID<>CONNECTION_ID()
 AND e.END_EVENT_ID IS NULL AND e.TIMER_WAIT>=5000000000000
ORDER BY e.TIMER_WAIT DESC LIMIT 50;
~~~

A NULL timer can mean timing is disabled. PROCESSLIST_TIME can be useful for session-state age, but is not always the active statement duration.

Sources: [Current statement events](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-events-statements-current-table.html).

### Q03 — Long and idle transactions

Find open InnoDB transactions, including idle sessions.

~~~sql
SELECT x.trx_id,x.trx_state,x.trx_started,
 TIMESTAMPDIFF(SECOND,x.trx_started,NOW()) AS age_seconds,
 x.trx_mysql_thread_id AS connection_id,x.trx_rows_locked,x.trx_rows_modified,
 x.trx_wait_started,t.PROCESSLIST_COMMAND,t.PROCESSLIST_STATE,
 LEFT(x.trx_query,4000) AS current_trx_query
FROM information_schema.innodb_trx AS x
LEFT JOIN performance_schema.threads AS t
 ON t.PROCESSLIST_ID=x.trx_mysql_thread_id
ORDER BY x.trx_started LIMIT 100;
~~~

An idle open transaction can have NULL trx_query. Transaction age alone does not establish that the transaction is blocking another session.

Sources: [InnoDB transaction diagnostics](https://dev.mysql.com/doc/refman/8.4/en/innodb-information-schema-transactions.html).

### Q04 — Session and wait summary

Count current foreground session states.

~~~sql
SELECT PROCESSLIST_USER,PROCESSLIST_COMMAND,PROCESSLIST_STATE,
 COUNT(*) AS sessions,MAX(PROCESSLIST_TIME) AS longest_state_seconds
FROM performance_schema.threads
WHERE TYPE='FOREGROUND' AND PROCESSLIST_ID<>CONNECTION_ID()
GROUP BY PROCESSLIST_USER,PROCESSLIST_COMMAND,PROCESSLIST_STATE
ORDER BY sessions DESC LIMIT 100;
~~~

State labels are not stable analytical dimensions across every version. Sleep is idle session state; use Q03 to distinguish idle transactions.

Sources: [Threads](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-threads-table.html).

### Q05a / Q05b — Blocking relationships

Q05a is the 8.x path. It identifies engine-provided waiter/blocker pairs and their lock details.

~~~sql
SELECT w.ENGINE,w.REQUESTING_ENGINE_TRANSACTION_ID AS waiting_trx,
 wt.PROCESSLIST_ID AS waiting_connection,
 w.BLOCKING_ENGINE_TRANSACTION_ID AS blocking_trx,
 bt.PROCESSLIST_ID AS blocking_connection,
 rl.OBJECT_SCHEMA,rl.OBJECT_NAME,rl.INDEX_NAME,
 rl.LOCK_TYPE,rl.LOCK_MODE AS requested_mode,bl.LOCK_MODE AS blocking_mode
FROM performance_schema.data_lock_waits AS w
LEFT JOIN performance_schema.data_locks AS rl
 ON rl.ENGINE=w.ENGINE AND rl.ENGINE_LOCK_ID=w.REQUESTING_ENGINE_LOCK_ID
LEFT JOIN performance_schema.data_locks AS bl
 ON bl.ENGINE=w.ENGINE AND bl.ENGINE_LOCK_ID=w.BLOCKING_ENGINE_LOCK_ID
LEFT JOIN performance_schema.threads AS wt
 ON wt.THREAD_ID=w.REQUESTING_THREAD_ID
LEFT JOIN performance_schema.threads AS bt
 ON bt.THREAD_ID=w.BLOCKING_THREAD_ID
LIMIT 100;
~~~

Q05b is the 5.7 path; those information-schema lock tables were removed in 8.0.

~~~sql
SELECT w.requesting_trx_id,r.trx_mysql_thread_id AS waiting_connection,
 r.trx_wait_started,LEFT(r.trx_query,4000) AS waiting_sql,
 w.blocking_trx_id,b.trx_mysql_thread_id AS blocking_connection,
 b.trx_started AS blocker_started,LEFT(b.trx_query,4000) AS blocker_current_sql
FROM information_schema.innodb_lock_waits AS w
JOIN information_schema.innodb_trx AS r ON r.trx_id=w.requesting_trx_id
JOIN information_schema.innodb_trx AS b ON b.trx_id=w.blocking_trx_id
LIMIT 100;
~~~

Current blocking relationships can disappear while these live sources are joined. A blocker's current SQL can be NULL or different from the lock-acquiring statement. Sources: [data_lock_waits](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-data-lock-waits-table.html), [5.7 INNODB_LOCK_WAITS](https://docs.oracle.com/cd/E17952_01/mysql-5.7-en/information-schema-innodb-lock-waits-table.html).


### Q06 — Metadata lock detail

Pending metadata-lock requests, often associated with DDL waiting behind transactions.

~~~sql
SELECT m.OBJECT_TYPE,m.OBJECT_SCHEMA,m.OBJECT_NAME,m.LOCK_TYPE,
 m.LOCK_DURATION,m.LOCK_STATUS,m.OWNER_THREAD_ID,
 t.PROCESSLIST_ID,t.PROCESSLIST_USER,t.PROCESSLIST_STATE,
 LEFT(t.PROCESSLIST_INFO,4000) AS current_sql
FROM performance_schema.metadata_locks AS m
LEFT JOIN performance_schema.threads AS t ON t.THREAD_ID=m.OWNER_THREAD_ID
WHERE m.LOCK_STATUS='PENDING'
LIMIT 100;
~~~

Q05 does not cover metadata locks. Matching object names to granted locks identifies candidates, not a reliable universal blocker graph because compatibility and queue order matter.

Sources: [Metadata locks](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-metadata-locks-table.html).

### Q07 — Expensive statement patterns

Rank normalized statement patterns by total timed cost.

~~~sql
SELECT SCHEMA_NAME,DIGEST,LEFT(DIGEST_TEXT,4000) AS digest_text,COUNT_STAR,
 SUM_TIMER_WAIT/1000000000000 AS total_seconds,
 AVG_TIMER_WAIT/1000000000 AS mean_ms,MAX_TIMER_WAIT/1000000000 AS max_ms,
 SUM_ROWS_EXAMINED,SUM_ROWS_SENT,SUM_ERRORS,SUM_WARNINGS
FROM performance_schema.events_statements_summary_by_digest
WHERE DIGEST IS NOT NULL AND COUNT_STAR>0
ORDER BY SUM_TIMER_WAIT DESC LIMIT 30;
~~~

Results are lifetime/summary-retention totals. A NULL DIGEST overflow row can contain substantial workload; inspect it using Q09 rather than ignoring it operationally.

Sources: [Statement summaries](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-statement-summary-tables.html).

### Q08 — Statement counter snapshot

Counter snapshot for interval rankings.

~~~sql
SELECT UTC_TIMESTAMP(6) AS captured_utc,SCHEMA_NAME,DIGEST,FIRST_SEEN,LAST_SEEN,
 COUNT_STAR,SUM_TIMER_WAIT,SUM_LOCK_TIME,SUM_ROWS_EXAMINED,SUM_ROWS_SENT,
 SUM_ERRORS,SUM_WARNINGS,SUM_CREATED_TMP_TABLES,SUM_CREATED_TMP_DISK_TABLES
FROM performance_schema.events_statements_summary_by_digest;
~~~

Key by schema/digest and track FIRST_SEEN. Detect resets/identity changes before subtracting. Decimal/unsigned sums should not be forced into narrow integer types.

Sources: [Statement summaries](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-statement-summary-tables.html).

### Q09 — Instrumentation collection health

Check collection configuration and digest coverage.

~~~sql
SELECT NAME,ENABLED FROM performance_schema.setup_consumers;
SELECT NAME,ENABLED,TIMED FROM performance_schema.setup_instruments
WHERE NAME IN ('statement/sql/select','wait/lock/metadata/sql/mdl')
 OR NAME LIKE 'stage/innodb/%';
SELECT SCHEMA_NAME,COUNT_STAR,FIRST_SEEN,LAST_SEEN
FROM performance_schema.events_statements_summary_by_digest
WHERE DIGEST IS NULL;
SHOW GLOBAL STATUS LIKE 'Performance_schema%lost';
~~~

Also inspect the target threads’ INSTRUMENTED/HISTORY columns. Disabled consumers, untimed instruments, lost events and overflow all limit conclusions.

Sources: [Consumers](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-setup-consumers-table.html), [Instrumentation setup](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-setup-instruments-table.html).

### Q10 — Workload and connection counters

Selected workload, connection and temporary-table counters.

~~~sql
SELECT VARIABLE_NAME,VARIABLE_VALUE
FROM performance_schema.global_status
WHERE VARIABLE_NAME IN ('Uptime','Questions','Queries','Com_select',
 'Com_insert','Com_update','Com_delete','Threads_connected','Threads_running',
 'Connections','Aborted_connects','Aborted_clients','Max_used_connections',
 'Created_tmp_tables','Created_tmp_disk_tables','Slow_queries','Bytes_received',
 'Bytes_sent');
~~~

Threads_running/connected are gauges. Queries includes activity such as statements executed inside stored programs; Questions has different semantics. Slow_queries does not guarantee a matching mysql.slow_log row.

Sources: [Server status variables](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html).

### Q11 — Table storage and maintenance candidates

Selected application schema table estimates.

~~~sql
SELECT TABLE_SCHEMA,TABLE_NAME,ENGINE,TABLE_ROWS,
 DATA_LENGTH,INDEX_LENGTH,DATA_FREE,UPDATE_TIME
FROM information_schema.tables
WHERE TABLE_SCHEMA='appdb' AND TABLE_TYPE='BASE TABLE'
ORDER BY DATA_LENGTH+INDEX_LENGTH DESC LIMIT 100;
~~~

InnoDB TABLE_ROWS is approximate and DATA_FREE can reflect shared tablespace space. These values do not justify automatic OPTIMIZE TABLE or identify all stale optimizer statistics.

Sources: [TABLES metadata](https://dev.mysql.com/doc/refman/8.4/en/information-schema-tables-table.html).

### Q12 — Index usage

Index I/O counters for one application schema.

~~~sql
SELECT OBJECT_SCHEMA,OBJECT_NAME,INDEX_NAME,COUNT_FETCH,
 SUM_TIMER_FETCH/1000000000000 AS fetch_seconds,
 COUNT_INSERT,COUNT_UPDATE,COUNT_DELETE
FROM performance_schema.table_io_waits_summary_by_index_usage
WHERE OBJECT_SCHEMA='appdb'
ORDER BY COUNT_FETCH DESC LIMIT 100;
~~~

INDEX_NAME NULL is not a regular named index. These are handler-level operations, not query counts. Validate uniqueness/constraints and a representative window before changing indexes.

Sources: [Table and index I/O summaries](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-table-wait-summary-tables.html).

### Q13 — InnoDB cache and transaction pressure

Read local InnoDB buffer and transaction pressure counters.

~~~sql
SELECT VARIABLE_NAME,VARIABLE_VALUE FROM performance_schema.global_status
WHERE VARIABLE_NAME IN ('Innodb_buffer_pool_pages_total',
 'Innodb_buffer_pool_pages_free','Innodb_buffer_pool_pages_dirty',
 'Innodb_buffer_pool_read_requests','Innodb_buffer_pool_reads',
 'Innodb_buffer_pool_wait_free','Innodb_row_lock_current_waits',
 'Innodb_row_lock_waits','Innodb_row_lock_time','Innodb_deadlocks');
~~~

Counter availability can differ; absent rows mean unavailable, not zero. Compute interval cache-miss ratios and row-lock time per wait from deltas, guarding zero denominators.

Sources: [Server status variables](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html).

### Q14 — Long-operation stage progress

Current stages that publish work estimates.

~~~sql
SELECT s.THREAD_ID,t.PROCESSLIST_ID,s.EVENT_NAME,
 s.TIMER_WAIT/1000000000000 AS elapsed_seconds,
 s.WORK_COMPLETED,s.WORK_ESTIMATED,
 100.0*s.WORK_COMPLETED/NULLIF(s.WORK_ESTIMATED,0) AS stage_percent
FROM performance_schema.events_stages_current AS s
LEFT JOIN performance_schema.threads AS t ON t.THREAD_ID=s.THREAD_ID
WHERE s.END_EVENT_ID IS NULL
ORDER BY s.TIMER_WAIT DESC LIMIT 50;
~~~

Requires stage instruments/consumers. A stage percent is not whole-DDL completion percent; not all operations expose estimates.

Sources: [Stage progress](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-events-stages-current-table.html).

### Q15 — Redo and commit pressure

Redo generation and waits; these are recovery metrics, not diagnostic messages.

~~~sql
SELECT VARIABLE_NAME,VARIABLE_VALUE FROM performance_schema.global_status
WHERE VARIABLE_NAME IN ('Innodb_os_log_written','Innodb_log_waits',
 'Innodb_log_write_requests','Innodb_log_writes');
~~~

Redo bytes/sec = delta(Innodb_os_log_written)/elapsed seconds. New redo-capacity/checkpoint variables differ across patch levels and are deliberately omitted from this common query.

Sources: [Server status variables](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html), [InnoDB parameters](https://dev.mysql.com/doc/refman/8.4/en/innodb-parameters.html).

### Q16 — File I/O counters

File I/O summary counters by instrument.

~~~sql
SELECT EVENT_NAME,COUNT_READ,SUM_NUMBER_OF_BYTES_READ,
 SUM_TIMER_READ/1000000000000 AS read_seconds,
 COUNT_WRITE,SUM_NUMBER_OF_BYTES_WRITE,
 SUM_TIMER_WRITE/1000000000000 AS write_seconds,
 COUNT_MISC,SUM_TIMER_MISC/1000000000000 AS misc_seconds
FROM performance_schema.file_summary_by_event_name
WHERE COUNT_STAR>0 ORDER BY SUM_TIMER_WAIT DESC LIMIT 50;
~~~

Use interval deltas for mean I/O latency. Misc operations include more than data reads/writes; timing depends on enabled instrumentation.

Sources: [File I/O summaries](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-file-summary-tables.html).

### Q17 — Statement spill and scan candidates

Find statement patterns creating temporary tables or performing scans.

~~~sql
SELECT SCHEMA_NAME,DIGEST,LEFT(DIGEST_TEXT,2000) AS digest_text,COUNT_STAR,
 SUM_CREATED_TMP_TABLES,SUM_CREATED_TMP_DISK_TABLES,
 SUM_NO_INDEX_USED,SUM_NO_GOOD_INDEX_USED,SUM_ROWS_EXAMINED,
 SUM_TIMER_WAIT/1000000000000 AS total_seconds
FROM performance_schema.events_statements_summary_by_digest
WHERE DIGEST IS NOT NULL
ORDER BY SUM_CREATED_TMP_DISK_TABLES DESC,SUM_ROWS_EXAMINED DESC LIMIT 30;
~~~

Temporary-table counters are not a byte count or complete measure of every spill implementation. A no-index scan can be appropriate for a small table.

Sources: [Statement summaries](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-statement-summary-tables.html).

### Q18a / Q18b — Replica lag and state

Q18a: MySQL 8.0.22+ and 8.4:

~~~sql
SHOW REPLICA STATUS;
~~~

Q18b: MySQL 5.7 and earlier 8.0:

~~~sql
SHOW SLAVE STATUS;
~~~

Run on each replica and inspect all channel rows. Column names changed from Slave/Master to Replica/Source with the terminology transition. Inspect I/O and SQL thread state, last receiver/applier errors, retrieved/executed GTID state and Seconds_Behind_Source (Seconds_Behind_Master in legacy output). REPLICATION CLIENT is the relevant SHOW-status privilege.

Lag can be NULL/unknown or misleadingly zero when the receiver itself is behind. It is not a guarantee of application freshness. Q19 gives SQL-queryable per-worker/receiver errors. Source: [SHOW REPLICA STATUS](https://dev.mysql.com/doc/refman/8.4/en/show-replica-status.html), [5.7 SHOW SLAVE STATUS](https://docs.oracle.com/cd/E17952_01/mysql-5.7-en/show-slave-status.html).


### Q19 — Replication worker errors

SQL-queryable receiver and applier error state across replication channels.

~~~sql
SELECT CHANNEL_NAME,SERVICE_STATE,LAST_ERROR_NUMBER,LAST_ERROR_MESSAGE,
 LAST_ERROR_TIMESTAMP
FROM performance_schema.replication_connection_status;
SELECT CHANNEL_NAME,WORKER_ID,THREAD_ID,SERVICE_STATE,
 LAST_ERROR_NUMBER,LAST_ERROR_MESSAGE,LAST_ERROR_TIMESTAMP
FROM performance_schema.replication_applier_status_by_worker;
SELECT CHANNEL_NAME,THREAD_ID,SERVICE_STATE,LAST_ERROR_NUMBER,
 LAST_ERROR_MESSAGE,LAST_ERROR_TIMESTAMP
FROM performance_schema.replication_applier_status_by_coordinator;
~~~

A previous error can remain after successful recovery. Inspect SERVICE_STATE, error timestamps and Q18 together. Single-threaded and parallel-applier configurations populate these tables differently.

Sources: [Applier worker status](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-replication-applier-status-by-worker-table.html), [Replication connection status](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-replication-connection-status-table.html), [Coordinator status](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-replication-applier-status-by-coordinator-table.html).

## Internal server logs and historical events

### Recommended logging baseline

Keep error logging enabled at an intentional verbosity. On 8.0.22+, confirm that the configured sink populates performance_schema.error_log. Traditional log_sink_internal and JSON log_sink_json support it; an unsupported sink can leave the table empty. The table is a fixed-size in-memory ring and is not a complete archive.

For a controlled slow-query recording window, an operator can select table output. Capture current settings with Q20 first and restore them after the window. This configuration example is not part of read-only polling:

~~~sql
-- CONFIGURATION CHANGE; requires appropriate system-variable privileges.
-- If existing file logging is required, retain it with FILE,TABLE.
SET GLOBAL log_output='FILE,TABLE';
SET GLOBAL long_query_time=0.5;
SET GLOBAL slow_query_log=ON;
~~~

log_output also affects the general query log if that log is enabled. long_query_time has a session value: changing the global default affects new application sessions; existing sessions can retain their old threshold. Review min_examined_row_limit and applicable options. Table slow-log writes and reads add overhead; define a supported rotation/purge procedure. Do not add arbitrary application indexes or DDL to mysql.slow_log.

Slow log execution order follows completion and does not reproduce transaction order. It is a performance log, not complete failed-query auditing. Keep general_query_log disabled unless a specific investigation justifies its cost and payload exposure. Sources: [Slow query log](https://dev.mysql.com/doc/refman/8.4/en/slow-query-log.html), [log destinations and table restrictions](https://dev.mysql.com/doc/refman/8.4/en/log-destinations.html).


### Q20 — Logging configuration

Discover relevant settings without assuming every variable exists on 5.7.

~~~sql
SHOW GLOBAL VARIABLES WHERE Variable_name IN ('log_error','log_error_services',
 'log_error_verbosity','log_output','slow_query_log','slow_query_log_file',
 'long_query_time','min_examined_row_limit','general_log',
 'innodb_print_all_deadlocks');
~~~

Only existing variables return rows. A file path does not imply a SQL logfile-reading interface exists on that version.

Sources: [Log destinations](https://dev.mysql.com/doc/refman/8.4/en/log-destinations.html), [Error log table](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-error-log-table.html).

### Q21 — Recent internal server errors

8.0.22+ only: recent server error/warning buffer entries.

~~~sql
SELECT LOGGED,THREAD_ID,PRIO,ERROR_CODE,SUBSYSTEM,DATA
FROM performance_schema.error_log
WHERE LOGGED>=NOW()-INTERVAL 1 HOUR AND PRIO IN ('Error','Warning')
ORDER BY LOGGED DESC LIMIT 100;
SHOW GLOBAL STATUS LIKE 'Error_log%';
~~~

ERROR_CODE identifies server log events, not a transcript of every client statement error. THREAD_ID here is a connection ID for foreground threads, unlike the internal THREAD_ID in most other Performance Schema tables. Check expired-event counters for buffer loss.

Sources: [Error log table](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-error-log-table.html).

### Q22 — Historical slow executions

Requires prior slow logging with TABLE in log_output. Set collector timezone to UTC as in Q01.

~~~sql
SELECT start_time,user_host,query_time,lock_time,rows_sent,rows_examined,
 db,thread_id,LEFT(sql_text,4000) AS sql_text
FROM mysql.slow_log
WHERE start_time>=NOW()-INTERVAL 1 HOUR AND query_time>='00:00:00.500000'
ORDER BY start_time DESC LIMIT 100;
~~~

This queries retained log records, not all slow statements ever executed. CSV table scans/sorting can be costly; cap retention and choose frequency accordingly. Entries are written after execution; lock_time is not a complete InnoDB row-wait duration.

Sources: [Slow query log](https://dev.mysql.com/doc/refman/8.4/en/slow-query-log.html), [Log destinations](https://dev.mysql.com/doc/refman/8.4/en/log-destinations.html).

### Q23 — Recently completed statement errors

Recent completed errors in the enabled global statement-history buffer.

~~~sql
SELECT h.THREAD_ID,h.EVENT_ID,h.CURRENT_SCHEMA,
 h.TIMER_WAIT/1000000000 AS elapsed_ms,h.MYSQL_ERRNO,
 h.RETURNED_SQLSTATE,h.MESSAGE_TEXT,LEFT(h.SQL_TEXT,4000) AS sql_text,
 t.PROCESSLIST_ID,t.PROCESSLIST_USER
FROM performance_schema.events_statements_history_long AS h
LEFT JOIN performance_schema.threads AS t ON t.THREAD_ID=h.THREAD_ID
WHERE h.MYSQL_ERRNO<>0
ORDER BY h.TIMER_END DESC LIMIT 100;
~~~

No wall-clock timestamp is provided here: TIMER_END is a relative timer. A disconnected thread can have no matching threads row. Save the capture UTC timestamp with returned event IDs; the buffer is volatile and can be disabled.

Sources: [Statement history](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-events-statements-history-long-table.html), [Current statement events](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-events-statements-current-table.html).

### Q24 — Error counter summary

8.x only: cumulative error counts, including handled/raised distinctions.

~~~sql
SELECT ERROR_NUMBER,ERROR_NAME,SQL_STATE,SUM_ERROR_RAISED,SUM_ERROR_HANDLED,
 FIRST_SEEN,LAST_SEEN
FROM performance_schema.events_errors_summary_global_by_error
WHERE SUM_ERROR_RAISED>0
ORDER BY SUM_ERROR_RAISED DESC LIMIT 50;
~~~

Not an event log and not all errors are instrumented. Error counters can include internal/handled errors, so they are not directly equal to failed customer requests. Use deltas for incident periods.

Sources: [Error summary tables](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-error-summary-tables.html).

### Q25 — Latest InnoDB deadlock

Requires PROCESS; returns the InnoDB monitor output as text.

~~~sql
SHOW ENGINE INNODB STATUS;
~~~

Inspect LATEST DETECTED DEADLOCK, transactions, history-list length and pending I/O. Only the latest InnoDB deadlock is available here; newer incidents overwrite it. innodb_print_all_deadlocks can record all detected InnoDB deadlocks in the server error log, but does not create a SQL-readable archive on 5.7. External deadlocks in other engines are outside this command.

Sources: [InnoDB monitor](https://dev.mysql.com/doc/refman/8.4/en/innodb-standard-monitor.html).

## Deeper diagnosis and rollout

Start Q01/Q02/Q03/Q05/Q09/Q10/Q19/Q21, applying the version alternatives. A starting cadence is 15–60 seconds for counters, temporary 5–15-second lock sampling during an incident and lower-frequency table/index scans. Retain numeric snapshots inside a dedicated administrative schema if historical analysis must remain inside MySQL; give the writer a separate role and purge data deliberately.

Use EXPLAIN for a specific suspected query after identifying its shape. EXPLAIN ANALYZE executes the workload and is available only on applicable 8.0 patch levels and later; it is not a common 5.7 polling query. Restrict it to an intentional investigation. [EXPLAIN ANALYZE](https://dev.mysql.com/doc/refman/8.4/en/explain.html).

Validate on non-production with a slow read, an idle open transaction, InnoDB blocking, metadata-lock blocking, an ordinary statement error and a controlled deadlock. Confirm instrument/consumer settings, history rollover, digest overflow, logging timezone, long_query_time behavior for existing sessions, patch-specific privileges and restart/reset handling. On 5.7, explicitly verify that no collector attempts Q21/Q24 or the 8.x lock query.

## References

Primary MySQL documentation is linked beside each query. Source index:

- [Current statement events](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-events-statements-current-table.html)
- [Statement history](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-events-statements-history-long-table.html)
- [Statement summaries](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-statement-summary-tables.html)
- [Data lock waits](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-data-lock-waits-table.html)
- [Metadata locks](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-metadata-locks-table.html)
- [InnoDB transaction diagnostics](https://dev.mysql.com/doc/refman/8.4/en/innodb-information-schema-transactions.html)
- [Consumers](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-setup-consumers-table.html)
- [Server status variables](https://dev.mysql.com/doc/refman/8.4/en/server-status-variables.html)
- [Table and index I/O summaries](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-table-wait-summary-tables.html)
- [Stage progress](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-events-stages-current-table.html)
- [File I/O summaries](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-file-summary-tables.html)
- [SHOW REPLICA STATUS](https://dev.mysql.com/doc/refman/8.4/en/show-replica-status.html)
- [Applier worker status](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-replication-applier-status-by-worker-table.html)
- [Replication connection status](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-replication-connection-status-table.html)
- [Error log table](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-error-log-table.html)
- [Error summary tables](https://dev.mysql.com/doc/refman/8.4/en/performance-schema-error-summary-tables.html)
- [Slow query log](https://dev.mysql.com/doc/refman/8.4/en/slow-query-log.html)
- [Log destinations](https://dev.mysql.com/doc/refman/8.4/en/log-destinations.html)
- [InnoDB monitor](https://dev.mysql.com/doc/refman/8.4/en/innodb-standard-monitor.html)
