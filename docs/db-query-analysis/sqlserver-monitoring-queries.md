# SQL Server monitoring SQL: performance, slow queries, locks and internal logs

## Scope and interpretation

Scope: SQL Server 2016, 2017, 2019, 2022 and 2025, using T-SQL against the database engine. Legacy inclusion is for installed-estate compatibility and does not imply support status. The matrix targets SQL Server instances.

Azure SQL Database, Managed Instance, Synapse and Fabric have different permissions, scope and diagnostic storage and are covered here.

These operational patterns follow the companion PostgreSQL and Oracle documents' structure. IDs are local to this document. Examples were checked against Microsoft documentation, not executed on live servers. Thresholds and cadences are recommendations to tune locally.

## What can be retrieved entirely through SQL?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Requests running slowly now | sys.dm_exec_requests | Current state only; excludes idle blockers unless joined to sessions. |
| Expensive completed statements | sys.dm_exec_query_stats | Plan-cache lifetime; not durable history. |
| Blocking and locks | requests, sessions, dm_tran_locks | Sampling misses resolved blocking. |
| Historical query performance | Query Store | Must be enabled, writable and capturing the workload. |
| Recorded server/Agent errors | sys.sp_readerrorlog | Only retained log files and messages actually logged. |
| Deadlock graphs | system_health Extended Events | Rollover/target retention, not indefinite history. |
| Selected individual slow executions/errors | Custom Extended Events | Requires prior configuration and retained targets. |

“Internal” means SQL-accessible diagnostics without SSH, file sharing or external forwarding. ERRORLOG and event_file data are server files read by the engine; Query Store is database-resident. The transaction log is a recovery mechanism, not an application-error journal. Missing histories cannot be reconstructed from live DMVs.

## Prerequisites and collection rules

Use a dedicated login with only required permissions. Most server performance DMVs need VIEW SERVER STATE in 2016–2019 and VIEW SERVER PERFORMANCE STATE from 2022. Some database DMVs/catalogues instead require database state/performance permissions, object visibility, or explicit SELECT; consult the linked page for every chosen interface. Query Store reads require VIEW DATABASE STATE on older releases and VIEW DATABASE PERFORMANCE STATE from 2022. Numeric metrics and query text deserve different access policies.

For sys.sp_readerrorlog, Microsoft currently documents VIEW SERVER STATE or securityadmin for 2019 and earlier; from 2022 it also allows the narrower VIEW ANY ERROR LOG permission. Do not give a collector securityadmin. Reading server XE files requires VIEW SERVER STATE on older releases, VIEW SERVER PERFORMANCE STATE from 2022. Creating or changing XE sessions is a separate administrative capability. Sources: [DMV permission model](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/system-dynamic-management-objects?view=sql-server-ver17), [error-log permissions](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-readerrorlog-transact-sql?view=sql-server-ver17), [XE file permissions](https://learn.microsoft.com/en-us/sql/relational-databases/system-functions/sys-fn-xe-file-target-read-file-transact-sql?view=sql-server-ver17).

Instance queries can run in master. Q09/Q11/Q12/Q13/Q23 run in each application database; Q17 explicitly changes to tempdb; Q19 reads msdb. Snippets are independent batches. Record server/instance identity, version, database, UTC capture time and sqlserver_start_time.

Use consecutive snapshots for cumulative counters. Discard deltas after restart, counter reset/decrease, plan eviction/recompile or identity changes. Do not run DBCC SQLPERF CLEAR, flush plan caches or restart services as monitoring steps. DMVs are changing observations: joins can miss rows or see inconsistent state.

SQL text may contain credentials, personal data and application literals. Limit length/rows and restrict retention. Even a SELECT can be costly if it enumerates large plan caches or parses many event files. Do not collect every XML execution plan in a frequent scrape.

## Compatibility matrix

Y = documented common interface; Q = Query Store enabled/capturing; A = configured availability groups; H = accessible retained XE target; B = msdb history and access; — = unavailable. All cells depend on relevant permissions and configuration; they do not claim live execution testing or cloud compatibility.

| Query name | 2016 | 2017 | 2019 | 2022 | 2025 |
| --- | --- | --- | --- | --- | --- |
| Q01 Environment and configuration | Y | Y | Y | Y | Y |
| Q02 Active slow requests | Y | Y | Y | Y | Y |
| Q03 Long and idle transactions | Y | Y | Y | Y | Y |
| Q04 Session and wait summary | Y | Y | Y | Y | Y |
| Q05 Blocking relationships | Y | Y | Y | Y | Y |
| Q06 Waiting lock detail | Y | Y | Y | Y | Y |
| Q07 Expensive cached statements | Y | Y | Y | Y | Y |
| Q08 Statement counter snapshot | Y | Y | Y | Y | Y |
| Q09 Query Store collection health | Q | Q | Q | Q | Q |
| Q10 Workload and memory counters | Y | Y | Y | Y | Y |
| Q11 Optimizer statistics candidates | Y | Y | Y | Y | Y |
| Q12 Index usage and size | Y | Y | Y | Y | Y |
| Q13 Transaction log pressure | Y | Y | Y | Y | Y |
| Q14 Long-operation progress | Y | Y | Y | Y | Y |
| Q15 Wait counter snapshot | Y | Y | Y | Y | Y |
| Q16 File I/O counters | Y | Y | Y | Y | Y |
| Q17 Tempdb allocation | Y | Y | Y | Y | Y |
| Q18 Availability group health | A | A | A | A | A |
| Q19 Backup history | B | B | B | B | B |
| Q20 Diagnostic file discovery | Y | Y | Y | Y | Y |
| Q21 Recorded server errors | Y | Y | Y | Y | Y |
| Q22 Deadlock history | H | H | H | H | H |
| Q23 Historical query performance and failures | Q | Q | Q | Q | Q |
| Q24 Custom captured slow batches and errors | H | H | H | H | H |

The common-column examples avoid newer spill counters, newer memory-grant fields and Query Store wait-stat views. Query Store exists from 2016; per-query Query Store wait statistics require 2017+, but are not used here. Query Store defaults vary by version and database creation/upgrade history; Q09 checks actual state rather than assuming it is enabled. SQL Server 2022 changes the permission model even when query syntax is unchanged. Sources: [Query Store](https://learn.microsoft.com/en-us/sql/relational-databases/performance/monitoring-performance-by-using-the-query-store?view=sql-server-ver17), [DMV permission changes](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/system-dynamic-management-objects?view=sql-server-ver17).

## Query catalogue

### Q01 — Environment and configuration

Instance context; retain the start time with every counter sample.

~~~sql
SELECT SERVERPROPERTY('ServerName') AS server_name,
       SERVERPROPERTY('ProductVersion') AS product_version,
       SERVERPROPERTY('ProductLevel') AS product_level,
       SERVERPROPERTY('Edition') AS edition,
       SYSUTCDATETIME() AS captured_utc, sqlserver_start_time
FROM sys.dm_os_sys_info;
SELECT name, value_in_use FROM sys.configurations
WHERE name IN ('max server memory (MB)','max degree of parallelism',
 'cost threshold for parallelism','blocked process threshold (s)');
~~~

Configuration reads are informational; do not tune automatically from a single observation.

Sources: [System information](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-os-sys-info-transact-sql?view=sql-server-ver17).

### Q02 — Active slow requests

Instance scope; example active-request threshold five seconds.

~~~sql
SELECT TOP (50) r.session_id, r.request_id, DB_NAME(r.database_id) AS database_name,
 r.status,r.command,r.total_elapsed_time AS elapsed_ms,r.cpu_time AS cpu_ms,
 r.logical_reads,r.reads,r.writes,r.wait_type,r.wait_time AS current_wait_ms,
 r.blocking_session_id,s.login_name,s.host_name,s.program_name,
 SUBSTRING(t.text,(r.statement_start_offset/2)+1,
   ((CASE WHEN r.statement_end_offset=-1 THEN DATALENGTH(t.text)
          ELSE r.statement_end_offset END-r.statement_start_offset)/2)+1)
   AS statement_text
FROM sys.dm_exec_requests AS r
JOIN sys.dm_exec_sessions AS s ON s.session_id=r.session_id
OUTER APPLY sys.dm_exec_sql_text(r.sql_handle) AS t
WHERE s.is_user_process=1 AND r.session_id<>@@SPID
 AND r.total_elapsed_time>=5000
ORDER BY r.total_elapsed_time DESC;
~~~

Duration/cpu are milliseconds; logical_reads are page reads. A request can run multiple tasks, so not every parallel worker wait is represented by its request wait_type.

Sources: [Active requests](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-requests-transact-sql?view=sql-server-ver17).

### Q03 — Long and idle transactions

Include sessions without a currently executing request.

~~~sql
SELECT TOP (100) st.session_id,DB_NAME(dt.database_id) AS database_name,
 at.transaction_begin_time,
 DATEDIFF(SECOND,at.transaction_begin_time,GETDATE()) AS open_seconds,
 s.status,s.open_transaction_count,s.last_request_end_time,
 dt.database_transaction_log_bytes_used,s.login_name,s.host_name,s.program_name
FROM sys.dm_tran_session_transactions AS st
JOIN sys.dm_tran_active_transactions AS at ON at.transaction_id=st.transaction_id
JOIN sys.dm_tran_database_transactions AS dt ON dt.transaction_id=st.transaction_id
JOIN sys.dm_exec_sessions AS s ON s.session_id=st.session_id
WHERE s.is_user_process=1
ORDER BY at.transaction_begin_time;
~~~

Rows can repeat for transactions touching multiple databases. A sleeping session can retain locks; inspect blocking before terminating anything.

Sources: [Database transactions](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-tran-database-transactions-transact-sql?view=sql-server-ver17), [Sessions](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-sessions-transact-sql?view=sql-server-ver17).

### Q04 — Session and wait summary

Current sessions grouped by application, status and current request wait.

~~~sql
SELECT s.program_name,s.status,r.wait_type,COUNT_BIG(*) AS session_request_rows
FROM sys.dm_exec_sessions AS s
LEFT JOIN sys.dm_exec_requests AS r ON r.session_id=s.session_id
WHERE s.is_user_process=1 AND s.session_id<>@@SPID
GROUP BY s.program_name,s.status,r.wait_type
ORDER BY session_request_rows DESC;
~~~

MARS can create more than one request per session, so this counts joined session/request rows, not necessarily distinct connections.

Sources: [Sessions](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-sessions-transact-sql?view=sql-server-ver17), [Active requests](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-requests-transact-sql?view=sql-server-ver17).

### Q05 — Blocking relationships

Current blocked requests and their directly identified blocking sessions.

~~~sql
SELECT TOP (100) w.session_id AS waiting_session,w.request_id,
 w.blocking_session_id,w.wait_type,w.wait_time AS wait_ms,w.wait_resource,
 b.status AS blocker_session_status,b.open_transaction_count,
 b.login_name AS blocker_login,b.host_name AS blocker_host,
 wt.text AS waiting_batch,bt.text AS blocker_recent_batch
FROM sys.dm_exec_requests AS w
LEFT JOIN sys.dm_exec_sessions AS b ON b.session_id=w.blocking_session_id
LEFT JOIN sys.dm_exec_connections AS bc ON bc.session_id=b.session_id
OUTER APPLY sys.dm_exec_sql_text(w.sql_handle) AS wt
OUTER APPLY sys.dm_exec_sql_text(bc.most_recent_sql_handle) AS bt
WHERE w.blocking_session_id<>0
ORDER BY w.wait_time DESC;
~~~

Negative blocker IDs have special meanings; they are not ordinary SPIDs. The blocker’s most recent batch can be different from the statement that acquired its retained locks.

Sources: [Active requests](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-requests-transact-sql?view=sql-server-ver17), [Sessions](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-sessions-transact-sql?view=sql-server-ver17).

### Q06 — Waiting lock detail

Inspect current lock requests that are not fully granted.

~~~sql
SELECT TOP (200) request_session_id,resource_type,
 DB_NAME(resource_database_id) AS database_name,
 resource_associated_entity_id,resource_description,
 request_mode,request_status,request_owner_type
FROM sys.dm_tran_locks
WHERE request_status<>'GRANT'
ORDER BY request_session_id,resource_type;
~~~

Combine with Q05. Resource IDs need type-aware decoding; joining every lock to a local database object ID produces incorrect results for keys/pages or other databases.

Sources: [Lock requests](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-tran-locks-transact-sql?view=sql-server-ver17).

### Q07 — Expensive cached statements

Rank completed statements whose plans remain cached.

~~~sql
SELECT TOP (30) qs.query_hash,qs.plan_handle,qs.creation_time,
 qs.last_execution_time,qs.execution_count,
 qs.total_elapsed_time/1000.0 AS total_elapsed_ms,
 qs.total_elapsed_time/NULLIF(qs.execution_count,0)/1000.0 AS mean_elapsed_ms,
 qs.total_worker_time/1000.0 AS total_cpu_ms,qs.total_logical_reads,
 SUBSTRING(t.text,(qs.statement_start_offset/2)+1,
  ((CASE WHEN qs.statement_end_offset=-1 THEN DATALENGTH(t.text)
         ELSE qs.statement_end_offset END-qs.statement_start_offset)/2)+1)
 AS statement_text
FROM sys.dm_exec_query_stats AS qs
OUTER APPLY sys.dm_exec_sql_text(qs.sql_handle) AS t
WHERE qs.execution_count>0
ORDER BY qs.total_elapsed_time DESC;
~~~

These timing counters are microseconds, despite Q02 using milliseconds. One statement may have several plan entries; this is a plan-entry ranking, not a complete workload ranking.

Sources: [Cached query statistics](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-query-stats-transact-sql?view=sql-server-ver17).

### Q08 — Statement counter snapshot

Snapshot counters for interval analysis, optionally restricting to a known plan handle.

~~~sql
SELECT SYSUTCDATETIME() AS captured_utc,
 sql_handle,plan_handle,statement_start_offset,statement_end_offset,
 creation_time,plan_generation_num,query_hash,query_plan_hash,
 execution_count,total_worker_time,total_elapsed_time,
 total_logical_reads,total_logical_writes
FROM sys.dm_exec_query_stats;
~~~

Stage selected rows or add a plan-handle filter on large estates. Compare the full identity and generation; never treat an evicted plan as an execution-counter reset to zero.

Sources: [Cached query statistics](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-query-stats-transact-sql?view=sql-server-ver17).

### Q09 — Query Store collection health

Application database context.

~~~sql
SELECT DB_NAME() AS database_name,actual_state_desc,desired_state_desc,
 readonly_reason,current_storage_size_mb,max_storage_size_mb,
 query_capture_mode_desc,interval_length_minutes,
 stale_query_threshold_days
FROM sys.database_query_store_options;
~~~

A read-only/full Query Store stops providing expected fresh coverage. Review capture mode, cleanup and interval settings before using historical absence as evidence.

Sources: [Query Store overview](https://learn.microsoft.com/en-us/sql/relational-databases/performance/monitoring-performance-by-using-the-query-store?view=sql-server-ver17).

### Q10 — Workload and memory counters

Selected instance memory/workload counters.

~~~sql
SELECT object_name,counter_name,instance_name,cntr_value,cntr_type
FROM sys.dm_os_performance_counters
WHERE counter_name IN ('Batch Requests/sec','SQL Compilations/sec',
 'SQL Re-Compilations/sec','User Connections','Memory Grants Pending',
 'Total Server Memory (KB)','Target Server Memory (KB)');
SELECT TOP (50) session_id,request_id,request_time,grant_time,
 requested_memory_kb,granted_memory_kb,used_memory_kb,wait_time_ms
FROM sys.dm_exec_query_memory_grants
ORDER BY requested_memory_kb DESC;
~~~

Counter names containing /sec are often raw cumulative counters in this DMV; calculate rates according to cntr_type. Memory Grants Pending is a gauge, not a counter delta.

Sources: [Performance counters](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-os-performance-counters-transact-sql?view=sql-server-ver17), [Memory grants](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-query-memory-grants-transact-sql?view=sql-server-ver17).

### Q11 — Optimizer statistics candidates

Application database context; identify statistics worth reviewing.

~~~sql
SELECT TOP (100) OBJECT_SCHEMA_NAME(s.object_id) AS schema_name,
 OBJECT_NAME(s.object_id) AS table_name,s.name AS statistics_name,
 p.last_updated,p.rows,p.rows_sampled,p.modification_counter
FROM sys.stats AS s
OUTER APPLY sys.dm_db_stats_properties(s.object_id,s.stats_id) AS p
WHERE OBJECTPROPERTY(s.object_id,'IsUserTable')=1
ORDER BY p.modification_counter DESC;
~~~

This is a review queue, not an automatic UPDATE STATISTICS list. NULL properties can reflect missing visibility or absent statistics blobs.

Sources: [Statistics properties](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-stats-properties-transact-sql?view=sql-server-ver17).

### Q12 — Index usage and size

Application database context; disk-based index usage and allocation.

~~~sql
WITH sz AS (
 SELECT object_id,index_id,SUM(reserved_page_count)*8.0/1024 AS reserved_mb
 FROM sys.dm_db_partition_stats GROUP BY object_id,index_id
)
SELECT TOP (100) OBJECT_SCHEMA_NAME(i.object_id) AS schema_name,
 OBJECT_NAME(i.object_id) AS table_name,i.name,i.index_id,sz.reserved_mb,
 u.user_seeks,u.user_scans,u.user_lookups,u.user_updates,u.last_user_seek
FROM sys.indexes AS i
JOIN sys.tables AS t ON t.object_id=i.object_id
LEFT JOIN sz ON sz.object_id=i.object_id AND sz.index_id=i.index_id
LEFT JOIN sys.dm_db_index_usage_stats AS u
 ON u.database_id=DB_ID() AND u.object_id=i.object_id AND u.index_id=i.index_id
WHERE t.is_ms_shipped=0
ORDER BY sz.reserved_mb DESC;
~~~

Usage history resets and differs for memory-optimized/spatial indexes. Missing rows are not proof of permanently unused indexes; check constraints and a representative workload window.

Sources: [Index usage](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-index-usage-stats-transact-sql?view=sql-server-ver17), [Partition allocation](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-partition-stats-transact-sql?view=sql-server-ver17).

### Q13 — Transaction log pressure

Run in each application database.

~~~sql
SELECT DB_NAME() AS database_name,total_log_size_in_bytes,
 used_log_space_in_bytes,used_log_space_in_percent
FROM sys.dm_db_log_space_usage;
SELECT name,recovery_model_desc,log_reuse_wait_desc
FROM sys.databases WHERE database_id=DB_ID();
~~~

High occupancy needs interpretation alongside log-reuse waits, long transactions and backup/replica health. Do not shrink logs as an automatic response.

Sources: [Log space usage](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-log-space-usage-transact-sql?view=sql-server-ver17).

### Q14 — Long-operation progress

Inspect operations reporting progress, including backup/restore.

~~~sql
SELECT session_id,DB_NAME(database_id) AS database_name,command,
 percent_complete,total_elapsed_time AS elapsed_ms,
 estimated_completion_time AS remaining_estimate_ms,wait_type
FROM sys.dm_exec_requests
WHERE percent_complete>0
 OR command IN ('BACKUP DATABASE','BACKUP LOG','RESTORE DATABASE','RESTORE LOG')
ORDER BY total_elapsed_time DESC;
~~~

Most ordinary SELECTs do not publish progress. Remaining time is an estimate and can change sharply.

Sources: [Active requests](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-requests-transact-sql?view=sql-server-ver17).

### Q15 — Wait counter snapshot

Instance cumulative wait statistics; retain the raw identities.

~~~sql
SELECT SYSUTCDATETIME() AS captured_utc,wait_type,
 waiting_tasks_count,wait_time_ms,signal_wait_time_ms
FROM sys.dm_os_wait_stats
WHERE waiting_tasks_count>0;
~~~

Rank interval deltas after excluding idle/background waits appropriate to your release. Parallel worker waits accumulate across tasks and are not query wall-clock duration.

Sources: [Wait statistics](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-os-wait-stats-transact-sql?view=sql-server-ver17).

### Q16 — File I/O counters

Instance-wide file I/O totals; calculate latency from consecutive snapshots.

~~~sql
SELECT SYSUTCDATETIME() AS captured_utc,v.database_id,
 DB_NAME(v.database_id) AS database_name,v.file_id,m.type_desc,m.physical_name,
 v.num_of_reads,v.num_of_bytes_read,v.io_stall_read_ms,
 v.num_of_writes,v.num_of_bytes_written,v.io_stall_write_ms,
 v.size_on_disk_bytes
FROM sys.dm_io_virtual_file_stats(NULL,NULL) AS v
LEFT JOIN sys.master_files AS m
 ON m.database_id=v.database_id AND m.file_id=v.file_id;
~~~

Interval read latency = delta(io_stall_read_ms)/delta(num_of_reads), guarding zero denominator. Do not confuse lifetime averages with the incident interval.

Sources: [File I/O statistics](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-io-virtual-file-stats-transact-sql?view=sql-server-ver17).

### Q17 — Tempdb allocation

Tempdb context; allocation gauges rather than host disk free space.

~~~sql
USE tempdb;
SELECT file_id,unallocated_extent_page_count*8.0/1024 AS unallocated_mb,
 user_object_reserved_page_count*8.0/1024 AS user_objects_mb,
 internal_object_reserved_page_count*8.0/1024 AS internal_objects_mb,
 version_store_reserved_page_count*8.0/1024 AS version_store_mb
FROM sys.dm_db_file_space_usage;
~~~

Version-store pressure, large sorts and user temp tables require different investigation. Add task/session allocation DMVs for attribution; this query reports file totals.

Sources: [File space usage](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-file-space-usage-transact-sql?view=sql-server-ver17).

### Q18 — Availability group health

Only instances hosting Always On availability replicas.

~~~sql
SELECT database_id,group_database_id,replica_id,is_local,is_primary_replica,
 synchronization_state_desc,synchronization_health_desc,
 is_suspended,suspend_reason_desc,log_send_queue_size,log_send_rate,
 redo_queue_size,redo_rate,last_commit_time
FROM sys.dm_hadr_database_replica_states;
~~~

Queue sizes are KB and rates KB/s. Values reflect the local replica’s knowledge and can be stale/NULL; queue/rate estimates are not guaranteed failover or application freshness times.

Sources: [Availability replica states](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-hadr-database-replica-states-transact-sql?view=sql-server-ver17).

### Q19 — Backup history

Read msdb; returns completed backup records in the last seven days.

~~~sql
SELECT database_name,type,is_copy_only,
 MAX(backup_finish_date) AS latest_finish,
 MAX(CASE WHEN has_backup_checksums=1 THEN backup_finish_date END)
 AS latest_with_checksums
FROM msdb.dbo.backupset
WHERE backup_finish_date>=DATEADD(DAY,-7,GETDATE())
GROUP BY database_name,type,is_copy_only
ORDER BY database_name,type;
~~~

Purged history or backups on another replica can produce no row. Backup history is not proof the media exists or a restore will succeed; it also does not identify every failed job.

Sources: [Backup history](https://learn.microsoft.com/en-us/sql/relational-databases/system-tables/backupset-transact-sql?view=sql-server-ver17).

## Internal server logs and historical events

### Recommended logging baseline

Keep error logs and system_health enabled with enough rollover capacity for the investigation window. ERRORLOG does not capture every ordinary statement error. Query Store provides interval aggregates, not a full per-execution transcript, and capture policies can omit queries.

For durable query summaries, an operator can enable/tune Query Store in each selected application database. This is a configuration change, not a polling query:

~~~sql
-- CONFIGURATION CHANGE: run in the selected database after reviewing capacity.
ALTER DATABASE CURRENT SET QUERY_STORE = ON;
ALTER DATABASE CURRENT SET QUERY_STORE
 (OPERATION_MODE = READ_WRITE, MAX_STORAGE_SIZE_MB = 1024,
  INTERVAL_LENGTH_MINUTES = 15, QUERY_CAPTURE_MODE = AUTO);
~~~

AUTO capture can exclude low-frequency queries; choose settings based on the evidence required. Confirm Q09 after enabling. Query Store configuration persists, but data cleanup and storage limits still affect retention. [Query Store documentation](https://learn.microsoft.com/en-us/sql/relational-databases/performance/monitoring-performance-by-using-the-query-store?view=sql-server-ver17).

For individual slow calls/errors, create a bounded custom XE session only when needed. The following optional example captures completed batches/RPCs lasting at least one second and reported errors of severity 16 or greater. Replace the file path with an absolute path writable by the SQL Server service account (Windows or Linux). Keep event payloads access-controlled.

~~~sql
-- CONFIGURATION CHANGE: server-scoped, not for Azure SQL Database.
CREATE EVENT SESSION monitor_perf_errors ON SERVER
ADD EVENT sqlserver.sql_batch_completed(
 ACTION(sqlserver.client_app_name,sqlserver.database_id,sqlserver.session_id)
 WHERE ([duration]>=(1000000))),
ADD EVENT sqlserver.rpc_completed(
 ACTION(sqlserver.client_app_name,sqlserver.database_id,sqlserver.session_id)
 WHERE ([duration]>=(1000000))),
ADD EVENT sqlserver.error_reported(
 ACTION(sqlserver.client_app_name,sqlserver.database_id,sqlserver.session_id)
 WHERE ([severity]>=(16)))
ADD TARGET package0.event_file(
 SET filename=N'/var/opt/mssql/log/monitor_perf_errors.xel',
     max_file_size=(50),max_rollover_files=(4))
WITH (MAX_DISPATCH_LATENCY=5 SECONDS,STARTUP_STATE=OFF);
ALTER EVENT SESSION monitor_perf_errors ON SERVER STATE=START;
-- At the end of the diagnostic window:
-- ALTER EVENT SESSION monitor_perf_errors ON SERVER STATE=STOP;
~~~

Completed batch/RPC duration is microseconds. This does not capture every statement within a batch, errors below the chosen threshold, calls that never complete, or all client cancellations/timeouts. Error events may represent handled application errors. For recurring monitoring, add database/application filters and assess overhead. blocked_process_report is a separate event requiring a deliberate blocked-process threshold; system_health is not a complete blocking-duration recorder. Source: [Extended Events configuration](https://learn.microsoft.com/en-us/sql/relational-databases/extended-events/quick-start-extended-events-in-sql-server?view=sql-server-ver17).


### Q20 — Diagnostic file discovery

Discover the current error-log and active system_health event-file paths.

~~~sql
SELECT CONVERT(nvarchar(4000),SERVERPROPERTY('ErrorLogFileName'))
 AS error_log_file;
SELECT s.name,t.target_name,CONVERT(xml,t.target_data) AS target_metadata
FROM sys.dm_xe_sessions AS s
JOIN sys.dm_xe_session_targets AS t ON t.event_session_address=s.address
WHERE s.name='system_health' AND t.target_name='event_file';
~~~

Reading target metadata does not publish the file or require a file share. No result can mean the session/target is absent or not visible.

Sources: [system_health](https://learn.microsoft.com/en-us/sql/relational-databases/extended-events/use-the-system-health-session?view=sql-server-ver17).

### Q21 — Recorded server errors

Read keyword-filtered records from the current SQL Server error log.

~~~sql
EXEC master.sys.sp_readerrorlog 0,1,N'Error';
EXEC master.sys.sp_readerrorlog 0,1,N'Login failed';
-- For a retained previous file, change the first parameter from 0 to 1.
~~~

Keyword filters are selective, not severity parsing. Some useful warnings omit “Error”; the procedure has no TOP/time-window parameter in its documented four-argument interface. Use controlled log size/rotation and avoid repeatedly importing huge files.

Sources: [sp_readerrorlog](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-readerrorlog-transact-sql?view=sql-server-ver17).

### Q22 — Deadlock history

Read retained system_health event files; the engine resolves the default log path.

~~~sql
SELECT TOP (100) f.file_name,f.file_offset,
 x.e.value('(/event/@timestamp)[1]','datetime2(7)') AS event_utc,
 x.e.query('/event/data[@name="xml_report"]/value/deadlock') AS deadlock_graph
FROM sys.fn_xe_file_target_read_file(N'system_health*.xel',NULL,NULL,NULL) AS f
CROSS APPLY (SELECT TRY_CONVERT(xml,f.event_data) AS e) AS x
WHERE f.object_name=N'xml_deadlock_report'
ORDER BY event_utc DESC;
~~~

If the session uses a custom directory, use Q20 to construct the correct server-local wildcard path. TOP limits returned rows but may not bound file scanning. Rollover can remove older graphs; deadlocks differ from ongoing blocking.

Sources: [system_health](https://learn.microsoft.com/en-us/sql/relational-databases/extended-events/use-the-system-health-session?view=sql-server-ver17), [Read Extended Event files](https://learn.microsoft.com/en-us/sql/relational-databases/system-functions/sys-fn-xe-file-target-read-file-transact-sql?view=sql-server-ver17).

### Q23 — Historical query performance and failures

Application database context; rank executions in Query Store intervals overlapping the last hour.

~~~sql
DECLARE @since datetimeoffset=DATEADD(HOUR,-1,SYSDATETIMEOFFSET());
SELECT TOP (30) q.query_id,q.query_hash,rs.execution_type_desc,
 SUM(rs.count_executions) AS execution_count,
 SUM(CONVERT(float,rs.count_executions)*rs.avg_duration)/1000.0 AS total_ms,
 SUM(CONVERT(float,rs.count_executions)*rs.avg_duration)/
   NULLIF(SUM(rs.count_executions),0)/1000.0 AS mean_ms,
 MAX(rs.max_duration)/1000.0 AS max_ms,
 MAX(CONVERT(nvarchar(4000),qt.query_sql_text)) AS query_text
FROM sys.query_store_runtime_stats AS rs
JOIN sys.query_store_runtime_stats_interval AS i
 ON i.runtime_stats_interval_id=rs.runtime_stats_interval_id
JOIN sys.query_store_plan AS p ON p.plan_id=rs.plan_id
JOIN sys.query_store_query AS q ON q.query_id=p.query_id
JOIN sys.query_store_query_text AS qt ON qt.query_text_id=q.query_text_id
WHERE i.end_time>=@since
GROUP BY q.query_id,q.query_hash,rs.execution_type_desc
ORDER BY total_ms DESC;
~~~

Weighted means avoid averaging averages. Aggregating all runtime rows handles multiple records for an active interval. Intervals overlapping the boundary can include earlier calls. Regular/Aborted/Exception groups distinguish outcomes but do not provide individual error numbers or messages.

Sources: [Query Store runtime statistics](https://learn.microsoft.com/en-us/sql/relational-databases/system-catalog-views/sys-query-store-runtime-stats-transact-sql?view=sql-server-ver17).

### Q24 — Custom captured slow batches and errors

Read the optional custom session created above; adjust the path to the actual target.

~~~sql
SELECT TOP (100) f.file_name,f.file_offset,f.object_name,
 x.e.value('(/event/@timestamp)[1]','datetime2(7)') AS event_utc,
 x.e.value('(/event/data[@name="duration"]/value)[1]','bigint')
   /1000.0 AS duration_ms,
 x.e.value('(/event/data[@name="error_number"]/value)[1]','int') AS error_number,
 x.e.value('(/event/data[@name="severity"]/value)[1]','int') AS severity,
 x.e.value('(/event/data[@name="message"]/value)[1]','nvarchar(4000)') AS message,
 x.e.query('/event') AS event_payload
FROM sys.fn_xe_file_target_read_file(
 N'/var/opt/mssql/log/monitor_perf_errors*.xel',NULL,NULL,NULL) AS f
CROSS APPLY (SELECT TRY_CONVERT(xml,f.event_data) AS e) AS x
ORDER BY event_utc DESC;
~~~

Fields absent from an event type return NULL. For continuous collection, checkpoint file_name/file_offset and use the function’s initial-file/offset arguments; handle rollover gaps. Server files remain subject to retention limits.

Sources: [Read Extended Event files](https://learn.microsoft.com/en-us/sql/relational-databases/system-functions/sys-fn-xe-file-target-read-file-transact-sql?view=sql-server-ver17).

## Deeper diagnosis and rollout

Start with Q01/Q02/Q05/Q13/Q15/Q16/Q21. For a small installation, try 15–60-second counter snapshots, temporary 5–15-second blocker sampling and lower-frequency statistics/index inspection. Retain the query identity and plan generation before calculating cache deltas. Do not poll all cached plans or all historical event files every few seconds.

Validate on non-production with a slow SELECT, a sleeping open transaction, a blocked request and a deliberate deadlock. Confirm least-privilege access under each major version, especially the 2022 permission boundary. Verify Query Store read-only behavior, weighted interval aggregation, XE rollover and restart handling. Query Store may require relevant cumulative updates on older releases.

To keep retained evidence inside SQL Server, insert bounded snapshots and selected XE/error rows into a dedicated administrative database with retention jobs and narrow access. Treat this writer separately from read-only DMV permissions. Test restoration of that evidence store if it matters to incident response.

## References

Primary Microsoft references are linked beside each query. Source index:

- [Active requests](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-requests-transact-sql?view=sql-server-ver17)
- [Sessions](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-sessions-transact-sql?view=sql-server-ver17)
- [Database transactions](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-tran-database-transactions-transact-sql?view=sql-server-ver17)
- [Lock requests](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-tran-locks-transact-sql?view=sql-server-ver17)
- [Wait statistics](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-os-wait-stats-transact-sql?view=sql-server-ver17)
- [Cached query statistics](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-query-stats-transact-sql?view=sql-server-ver17)
- [Query Store overview](https://learn.microsoft.com/en-us/sql/relational-databases/performance/monitoring-performance-by-using-the-query-store?view=sql-server-ver17)
- [Query Store runtime statistics](https://learn.microsoft.com/en-us/sql/relational-databases/system-catalog-views/sys-query-store-runtime-stats-transact-sql?view=sql-server-ver17)
- [Performance counters](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-os-performance-counters-transact-sql?view=sql-server-ver17)
- [Statistics properties](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-stats-properties-transact-sql?view=sql-server-ver17)
- [Index usage](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-index-usage-stats-transact-sql?view=sql-server-ver17)
- [Log space usage](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-log-space-usage-transact-sql?view=sql-server-ver17)
- [File I/O statistics](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-io-virtual-file-stats-transact-sql?view=sql-server-ver17)
- [File space usage](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-db-file-space-usage-transact-sql?view=sql-server-ver17)
- [Memory grants](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-exec-query-memory-grants-transact-sql?view=sql-server-ver17)
- [Availability replica states](https://learn.microsoft.com/en-us/sql/relational-databases/system-dynamic-management-objects/sys-dm-hadr-database-replica-states-transact-sql?view=sql-server-ver17)
- [Backup history](https://learn.microsoft.com/en-us/sql/relational-databases/system-tables/backupset-transact-sql?view=sql-server-ver17)
- [sp_readerrorlog](https://learn.microsoft.com/en-us/sql/relational-databases/system-stored-procedures/sp-readerrorlog-transact-sql?view=sql-server-ver17)
- [system_health](https://learn.microsoft.com/en-us/sql/relational-databases/extended-events/use-the-system-health-session?view=sql-server-ver17)
- [Read Extended Event files](https://learn.microsoft.com/en-us/sql/relational-databases/system-functions/sys-fn-xe-file-target-read-file-transact-sql?view=sql-server-ver17)
- [Extended Events quickstart](https://learn.microsoft.com/en-us/sql/relational-databases/extended-events/quick-start-extended-events-in-sql-server?view=sql-server-ver17)
