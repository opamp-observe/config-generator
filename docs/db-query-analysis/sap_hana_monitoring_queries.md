<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0. See license.txt in the project root.
-->

# SAP HANA monitoring SQL: performance, expensive statements, locks and diagnosis files

## Scope and interpretation

Scope: SAP HANA Platform 2.0 SPS 05 through SPS 08 and SAP HANA Cloud. The core monitoring-view patterns are shared, but cloud permissions and columns can differ from on-premises revisions. Confirm every projection against the SQL and System Views Reference for the exact revision.

These are operational query patterns assembled from SAP's documented monitoring views. Thresholds and polling intervals are recommendations to tune locally. Compatibility is documentation-based, not an execution claim for every revision or tenant topology.

## What can be retrieved entirely through SQL?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Statements running slowly now | `SYS.M_ACTIVE_STATEMENTS` | Current state; short statements between polls are missed. |
| Current connections and transactions | `M_CONNECTIONS`, `M_TRANSACTIONS` | Visibility depends on monitoring privileges and database context. |
| Blocking relationships | `M_BLOCKED_TRANSACTIONS` | Current waits only; retain samples for resolved incidents. |
| Expensive completed statements | `M_EXPENSIVE_STATEMENTS` | Expensive-statements trace is disabled by default and bounded by configuration. |
| Aggregated statement patterns | `M_SQL_PLAN_CACHE` | Plan-cache lifetime; eviction/recompile breaks continuity. |
| Memory, CPU, disk and service health | `M_SERVICE_MEMORY`, host/service monitoring views | SQL does not replace OS, storage or cloud metrics. |
| Alerts and diagnosis information | `_SYS_STATISTICS` alert views, trace-file views where permitted | Availability, retention and cloud access vary. |

“Entirely through SQL” means reachable through the database connection and granted monitoring interfaces. It does not mean that host trace files are copied into ordinary application tables.

## Prerequisites and collection rules

Use a dedicated technical user with the least monitoring privileges needed. SAP HANA commonly uses `CATALOG READ`, `MONITORING` and view-specific access patterns; trace administration is separate and must not be granted merely to read metrics. In tenant systems, connect to every intended tenant and the system database separately where required. Preserve database, host, port and service identity in every stored sample.

Monitoring views are live and need not form a transactionally consistent snapshot across queries. Stage related rows under a collector sample ID before complex joins. Difference cumulative counters only across continuous service uptime and discard negative deltas or gaps. Timestamps and durations differ by view; duration fields named `*_MICROSEC` are microseconds.

Statement strings, parameter values, trace files and alerts can contain customer data. Prefer hashes and bounded text where possible. The expensive-statements trace has overhead, is inactive by default, and its in-memory record count is bounded. Enabling it is an administrative change, not part of a read-only poller. [Expensive Statements Trace](https://help.sap.com/docs/SAP_HANA_PLATFORM/f157e7b47b2a417a99eadd4b6c433b77/5faf04f17830464eacdb7938b383d2ab.html).

## Compatibility matrix

**Y** = common platform interface. **C** = available in HANA Cloud with role/column validation. **T** = trace must be enabled. **D** = diagnosis-file access varies.

| Query name | SPS 05 | SPS 06 | SPS 07/08 | HANA Cloud |
| --- | --- | --- | --- | --- |
| Q01 Environment and services | Y | Y | Y | C |
| Q02 Active slow statements | Y | Y | Y | C |
| Q03 Long transactions | Y | Y | Y | C |
| Q04 Connection summary | Y | Y | Y | C |
| Q05 Blocking relationships | Y | Y | Y | C |
| Q06 Expensive statements | T | T | T | T/C |
| Q07 SQL plan-cache patterns | Y | Y | Y | C |
| Q08 Service memory | Y | Y | Y | C |
| Q09 Admission-control events | Y | Y | Y | C |
| Q10 Column-store table memory | Y | Y | Y | C |
| Q11 Disk capacity | Y | Y | Y | C |
| Q12 Delta-merge activity | Y | Y | Y | C |
| Q13 Backup history | Y | Y | Y | C |
| Q14 Log-segment pressure | Y | Y | Y | C |
| Q15 Service replication | Y | Y | Y | C |
| Q16 Current alerts | Y | Y | Y | C |
| Q17 Diagnosis files | D | D | D | D/C |

SAP HANA Cloud is continuously updated. Treat the Cloud column as an interface family, not a fixed-version guarantee. SAP's current performance guidance identifies `M_ACTIVE_STATEMENTS`, `M_PREPARED_STATEMENTS` and `M_EXPENSIVE_STATEMENTS` as the principal statement-analysis views. [Analyzing System Performance](https://help.sap.com/docs/hana-cloud-database/sap-hana-cloud-sap-hana-database-administration-guide/analyzing-system-performance).

## Query catalogue

### Q01 — Environment and services

```sql
SELECT DATABASE_NAME, SYSTEM_ID, HOST, START_TIME
FROM SYS.M_DATABASE;

SELECT HOST, PORT, SERVICE_NAME, PROCESS_ID, ACTIVE_STATUS,
       SQL_PORT, COORDINATOR_TYPE
FROM SYS.M_SERVICES
ORDER BY HOST, PORT;
```

Capture at connection startup and after topology changes. In multiple-container systems, collect system and tenant databases deliberately.

### Q02 — Active slow statements

```sql
SELECT HOST,
       PORT,
       CONNECTION_ID,
       STATEMENT_ID,
       STATEMENT_STATUS,
       START_TIME,
       DURATION_MICROSEC,
       DB_USER,
       APP_USER,
       APPLICATION_NAME,
       WORKLOAD_CLASS_NAME,
       STATEMENT_HASH,
       STATEMENT_STRING
FROM SYS.M_ACTIVE_STATEMENTS
WHERE DURATION_MICROSEC >= 5000000
ORDER BY DURATION_MICROSEC DESC
LIMIT 100;
```

Duration includes the statement's current lifetime. Running statements have incomplete final resource counters. Exclude the collector by application/user or connection identity.

### Q03 — Long transactions

```sql
SELECT HOST,
       PORT,
       CONNECTION_ID,
       TRANSACTION_ID,
       TRANSACTION_STATUS,
       START_TIME,
       UPDATE_TRANSACTION_ID,
       MIN_MVCC_SNAPSHOT_TIMESTAMP
FROM SYS.M_TRANSACTIONS
WHERE START_TIME < ADD_SECONDS(CURRENT_TIMESTAMP, -60)
ORDER BY START_TIME;
```

Long age alone is not a defect. Old snapshots can retain versions and should be correlated with the owning connection and workload.

### Q04 — Connection summary

```sql
SELECT HOST,
       PORT,
       CONNECTION_STATUS,
       USER_NAME,
       CLIENT_APPLICATION,
       COUNT(*) AS CONNECTION_COUNT
FROM SYS.M_CONNECTIONS
GROUP BY HOST, PORT, CONNECTION_STATUS, USER_NAME, CLIENT_APPLICATION
ORDER BY CONNECTION_COUNT DESC;
```

Connection state is a gauge. Pooled connections and internal services require separate interpretation.

### Q05 — Blocking relationships

```sql
SELECT HOST,
       PORT,
       BLOCKED_CONNECTION_ID,
       BLOCKED_TRANSACTION_ID,
       LOCK_OWNER_CONNECTION_ID,
       LOCK_OWNER_TRANSACTION_ID,
       LOCK_TYPE,
       LOCK_MODE,
       WAITING_SCHEMA_NAME,
       WAITING_OBJECT_NAME,
       WAITING_OBJECT_TYPE,
       WAITING_RECORD_ID
FROM SYS.M_BLOCKED_TRANSACTIONS
ORDER BY BLOCKED_CONNECTION_ID;
```

Store repeated samples to establish persistence. Do not terminate a blocking connection solely from this snapshot; first identify business context and transaction ownership.

### Q06 — Expensive statements

```sql
SELECT START_TIME,
       DURATION_MICROSEC,
       CPU_TIME,
       MEMORY_SIZE,
       RECORDS,
       ERROR_CODE,
       DB_USER,
       APP_USER,
       APPLICATION_NAME,
       STATEMENT_HASH,
       STATEMENT_STRING
FROM SYS.M_EXPENSIVE_STATEMENTS
WHERE START_TIME >= ADD_SECONDS(CURRENT_TIMESTAMP, -3600)
ORDER BY DURATION_MICROSEC DESC
LIMIT 200;
```

The view is empty unless tracing has collected records. In-memory tracing is a ring buffer; file-backed behavior and retention depend on configuration. A threshold of zero can create material overhead and volume.

### Q07 — SQL plan-cache patterns

```sql
SELECT STATEMENT_HASH,
       PLAN_ID,
       SCHEMA_NAME,
       EXECUTION_COUNT,
       TOTAL_EXECUTION_TIME,
       AVG_EXECUTION_TIME,
       TOTAL_RESULT_RECORD_COUNT,
       TOTAL_LOCK_WAIT_DURATION,
       LAST_EXECUTION_TIMESTAMP,
       STATEMENT_STRING
FROM SYS.M_SQL_PLAN_CACHE
WHERE EXECUTION_COUNT > 0
ORDER BY TOTAL_EXECUTION_TIME DESC
LIMIT 100;
```

Plan-cache records are not a durable execution ledger. Eviction, invalidation and service restart reset continuity; preserve plan ID and sample identity when calculating deltas.

### Q08 — Service memory

```sql
SELECT HOST,
       PORT,
       SERVICE_NAME,
       PHYSICAL_MEMORY_SIZE,
       EFFECTIVE_ALLOCATION_LIMIT,
       TOTAL_MEMORY_USED_SIZE,
       CODE_SIZE,
       STACK_SIZE,
       HEAP_MEMORY_ALLOCATED_SIZE,
       HEAP_MEMORY_USED_SIZE
FROM SYS.M_SERVICE_MEMORY
ORDER BY TOTAL_MEMORY_USED_SIZE DESC;
```

Memory categories overlap with allocator/accounting behavior and should not be blindly summed across levels. Correlate with host allocation limits and out-of-memory events.

### Q09 — Admission-control events

```sql
SELECT *
FROM SYS.M_ADMISSION_CONTROL_EVENTS
WHERE EVENT_TIME >= ADD_SECONDS(CURRENT_TIMESTAMP, -3600)
ORDER BY EVENT_TIME DESC
LIMIT 200;
```

This detects recent queue/reject activity due to workload admission control. Use `DESCRIBE SYS.M_ADMISSION_CONTROL_EVENTS` and replace `*` with the stable columns on the target revision before production ingestion. SAP recommends this view when resource pressure prevents admission. [Troubleshooting connection and admission failures](https://help.sap.com/docs/SAP_HANA_PLATFORM/bed8c14f9f024763b0777aa72b5436f6/ac83cbadbd474bcb8f07475d16e49454.html?locale=en-US).

### Q10 — Column-store table memory

```sql
SELECT SCHEMA_NAME,
       TABLE_NAME,
       RECORD_COUNT,
       MEMORY_SIZE_IN_TOTAL,
       MEMORY_SIZE_IN_MAIN,
       MEMORY_SIZE_IN_DELTA,
       LAST_MERGE_TIME
FROM SYS.M_CS_TABLES
ORDER BY MEMORY_SIZE_IN_TOTAL DESC
LIMIT 100;
```

This is column-store memory, not total durable table size. Unloaded tables and partitioned/distributed tables require topology-aware aggregation.

### Q11 — Disk capacity

```sql
SELECT HOST,
       PATH,
       USAGE_TYPE,
       TOTAL_SIZE,
       USED_SIZE,
       TOTAL_SIZE - USED_SIZE AS FREE_SIZE
FROM SYS.M_DISKS
ORDER BY HOST, USAGE_TYPE, PATH;
```

Database-reported capacity does not replace filesystem, volume-manager or cloud storage alerts. Keep data, log, trace and backup usage types separate.

### Q12 — Delta-merge activity

```sql
SELECT HOST,
       PORT,
       SCHEMA_NAME,
       TABLE_NAME,
       START_TIME,
       EXECUTION_TIME,
       MOTIVATION,
       SUCCESS,
       LAST_ERROR,
       ERROR_DESCRIPTION
FROM SYS.M_DELTA_MERGE_STATISTICS
WHERE START_TIME >= ADD_SECONDS(CURRENT_TIMESTAMP, -3600)
ORDER BY START_TIME DESC
LIMIT 200;
```

Repeated failures or sustained delta growth merit investigation. Exact diagnostic columns can vary by revision; validate the projection before rollout.

### Q13 — Backup history

```sql
SELECT SYS_START_TIME,
       SYS_END_TIME,
       ENTRY_TYPE_NAME,
       BACKUP_ID,
       STATE_NAME,
       MESSAGE,
       COMMENT
FROM SYS.M_BACKUP_CATALOG
WHERE SYS_START_TIME >= ADD_DAYS(CURRENT_TIMESTAMP, -7)
ORDER BY SYS_START_TIME DESC
LIMIT 200;
```

A successful catalogue entry does not by itself prove restore readiness or external-backup availability. Test recovery separately.

### Q14 — Log-segment pressure

```sql
SELECT HOST,
       PORT,
       VOLUME_ID,
       FILE_NAME,
       STATE,
       SIZE,
       START_POSITION,
       END_POSITION
FROM SYS.M_LOG_SEGMENTS
ORDER BY HOST, PORT, VOLUME_ID, START_POSITION;
```

Retained segments can indicate backup or savepoint constraints. Correlate state with backup catalogue and log-volume capacity rather than deleting files manually.

### Q15 — Service replication

```sql
SELECT HOST,
       PORT,
       VOLUME_ID,
       SITE_ID,
       SECONDARY_HOST,
       SECONDARY_PORT,
       REPLICATION_STATUS,
       REPLICATION_MODE,
       LAST_LOG_POSITION
FROM SYS.M_SERVICE_REPLICATION
ORDER BY HOST, PORT;
```

Only meaningful where system replication is configured. Validate exact columns for the revision and interpret together with replication mode and site role.

## Internal server logs and historical events

### Recommended logging baseline

Use alerts for continuous health monitoring. Enable expensive-statement tracing only with an explicit duration, threshold and retention plan. Diagnosis files remain the authoritative detail for many internal failures; do not grant broad trace access to a general metrics collector.

### Q16 — Current alerts

```sql
SELECT ALERT_ID,
       ALERT_NAME,
       RATING,
       ALERT_TIMESTAMP,
       ALERT_DETAILS
FROM _SYS_STATISTICS.STATISTICS_CURRENT_ALERTS
WHERE RATING >= 3
ORDER BY ALERT_TIMESTAMP DESC
LIMIT 200;
```

Alert ratings and checks are configured by the statistics service. An empty result can mean healthy state, disabled checks or insufficient privilege; monitor collection health separately.

### Q17 — Diagnosis-file discovery

```sql
SELECT HOST,
       FILE_NAME,
       FILE_SIZE,
       FILE_MTIME
FROM SYS.M_TRACEFILES
WHERE FILE_MTIME >= ADD_SECONDS(CURRENT_TIMESTAMP, -3600)
ORDER BY FILE_MTIME DESC
LIMIT 100;

SELECT HOST, FILE_NAME, OFFSET, CONTENT
FROM SYS.M_TRACEFILE_CONTENTS
WHERE HOST = :trace_host
  AND FILE_NAME = :trace_filename
  AND OFFSET > -100000
ORDER BY OFFSET
LIMIT 500;
```

`M_TRACEFILE_CONTENTS` requires equality predicates for host and file name; the negative offset reads a bounded tail without materializing every file. The bind placeholders are supplied by the client. Cloud services may restrict direct trace-file views. File discovery is not a complete error audit, and trace payloads require stricter access than numeric metrics. Source: [`M_TRACEFILE_CONTENTS`](https://help.sap.com/docs/SAP_HANA_PLATFORM/4fe29514fd584807ac9f2a04f6754767/20c8d7fe75191014b8cebeafdbafde33.html).

## Deeper diagnosis and rollout

For a chosen statement, use the plan cache and SAP HANA's plan visualization/explain tooling in a controlled session. Re-executing a production statement merely to obtain runtime detail can change data or create load; prefer retained plan/trace evidence where possible.

Suggested rollout:

1. Establish Q01 and least-privilege access separately for each system/tenant database.
2. Poll Q02–Q05 every 15–30 seconds and stage related rows under one sample ID.
3. Use Q06 only after the expensive-statements trace is deliberately configured; collect Q07 every 1–5 minutes.
4. Poll Q08–Q12 every 30–60 seconds with host/service identity preserved.
5. Check Q13–Q15 on operationally appropriate intervals and alert on stale successful backups or unhealthy replication.
6. Collect Q16 continuously; use Q17 only for incident-driven, access-controlled diagnosis.
7. Validate columns, units, tenant visibility and overhead against the exact HANA revision before production deployment.

SQL monitoring does not replace SAP HANA cockpit, OS/cloud telemetry, storage checks, network measurements or tested backup recovery. Protect statement text, alerts and trace files as application data.
