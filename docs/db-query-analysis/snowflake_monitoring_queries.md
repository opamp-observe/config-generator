<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0. See license.txt in the project root.
-->

# Snowflake monitoring SQL: performance, slow queries, locks, warehouses and history

## Scope and interpretation

Scope: the continuously delivered Snowflake service. Snowflake does not expose customer-selectable database engine versions, so compatibility is organized by interface, privilege and edition rather than release number. Verify new columns and regional availability against the current documentation before deploying a fixed projection.

These are operational query patterns assembled from Snowflake's documented Information Schema and `SNOWFLAKE.ACCOUNT_USAGE` interfaces. Thresholds, polling intervals and cost interpretations are recommendations to tune locally. Account Usage views have documented latency and retention differences; they are not a live control plane.

## What can be retrieved entirely through SQL?

| Requirement | Recommended interface | Limitation |
| --- | --- | --- |
| Recent and running queries | Information Schema `QUERY_HISTORY` table functions | Short retention/result limits and role visibility apply. |
| Durable account query history | `ACCOUNT_USAGE.QUERY_HISTORY` | Latency; not suitable for immediate incident detection. |
| Blocking and lock waits | `ACCOUNT_USAGE.LOCK_WAIT_HISTORY` | Historical view with latency; no general row-lock catalogue. |
| Warehouse load, queueing and credits | `WAREHOUSE_LOAD_HISTORY`, `WAREHOUSE_METERING_HISTORY` | Different time grains and latency; credits are not direct currency cost. |
| Warehouse suspend/resume/resize events | `WAREHOUSE_EVENTS_HISTORY` | Event history, not performance samples. |
| Storage and table footprint | `STORAGE_USAGE`, `TABLE_STORAGE_METRICS` | Account snapshots and retained/fail-safe bytes need separate interpretation. |
| Query failures | Query History error fields | Records SQL execution failures, not every internal service diagnostic. |
| Internal server logs | Not exposed as host/server files | Use Snowflake history views, event tables and support diagnostics instead. |

“Entirely through SQL” means visible to the active role through Snowflake metadata. It does not imply zero latency, unlimited retention or access across all databases and roles.

## Prerequisites and collection rules

Use a dedicated monitoring role. Grant imported privileges on the shared `SNOWFLAKE` database and only the account privileges needed by the chosen views. `GOVERNANCE_VIEWER`, `USAGE_VIEWER`, `SECURITY_VIEWER` and object `MONITOR` privileges cover different domains; do not default the collector to `ACCOUNTADMIN`. Information Schema query-history functions return records allowed by the active role and function variant. [Account Usage access](https://docs.snowflake.com/en/sql-reference/account-usage).

Set the collector session timezone to UTC before comparing timestamps:

```sql
ALTER SESSION SET TIMEZONE = 'UTC';
```

Use overlapping time windows and deduplicate by `QUERY_ID` or the documented event identity. Never advance a watermark until all pages/results for the window are stored. Account Usage latency varies by view, so monitor each view's newest timestamp separately. Query text, errors, object names and tags can contain customer data.

Milliseconds in Query History fields are component times, and some components overlap or do not sum exactly to total elapsed time. Queued overload, provisioning, repair and transaction-blocked time are operationally distinct. Credit allocation fields are estimates and can differ from billed credits.

## Compatibility matrix

**I** = Information Schema, low-latency but bounded. **A** = Account Usage, delayed account-level history. **E** = edition/feature dependent. **—** = not provided by that interface.

| Query name | Information Schema | Account Usage | Notes |
| --- | --- | --- | --- |
| Q01 Environment and session | I | — | Current session/account. |
| Q02 Recent slow or running queries | I | A | Use Information Schema for immediacy. |
| Q03 Queue and execution breakdown | I | A | Same core query timing fields. |
| Q04 Recent query failures | I | A | Visibility/latency differs. |
| Q05 Lock waits | — | A | Historical lock-wait view. |
| Q06 Expensive query patterns | — | A | Query-hash aggregation. |
| Q07 Query-history freshness | — | A | Collector health signal. |
| Q08 Warehouse load | I | A | Different retention/latency. |
| Q09 Warehouse credits and idle estimate | — | A | Cost attribution is approximate. |
| Q10 Warehouse lifecycle events | — | A | Event history. |
| Q11 Account storage trend | — | A | Daily snapshots. |
| Q12 Table storage | — | A | Includes retained/fail-safe bytes. |
| Q13 Automatic clustering | — | A/E | Feature use required. |
| Q14 Materialized-view refresh | — | A/E | Materialized views required. |
| Q15 Copy/load failures | I | A | Retention differs. |
| Q16 Task failures | I | A/E | Tasks required. |
| Q17 Serverless task credits | — | A/E | Serverless tasks required. |
| Q18 Login failures | — | A | Security-sensitive history. |

## Query catalogue

### Q01 — Environment and session

```sql
SELECT CURRENT_VERSION() AS service_version,
       CURRENT_ORGANIZATION_NAME() AS organization_name,
       CURRENT_ACCOUNT_NAME() AS account_name,
       CURRENT_REGION() AS region_name,
       CURRENT_USER() AS user_name,
       CURRENT_ROLE() AS role_name,
       CURRENT_WAREHOUSE() AS warehouse_name,
       CURRENT_DATABASE() AS database_name,
       CURRENT_SCHEMA() AS schema_name,
       CURRENT_TIMESTAMP() AS sampled_at;

SHOW PARAMETERS LIKE 'TIMEZONE' IN SESSION;
```

Capture this at connection time. `CURRENT_VERSION()` identifies the service build but is not a customer-managed compatibility target.

### Q02 — Recent slow or running queries

```sql
SELECT query_id,
       user_name,
       role_name,
       warehouse_name,
       warehouse_size,
       execution_status,
       start_time,
       end_time,
       total_elapsed_time,
       execution_time,
       queued_overload_time,
       queued_provisioning_time,
       transaction_blocked_time,
       bytes_scanned,
       rows_produced,
       query_text
FROM TABLE(INFORMATION_SCHEMA.QUERY_HISTORY(
  END_TIME_RANGE_START => DATEADD('hour', -1, CURRENT_TIMESTAMP()),
  RESULT_LIMIT => 10000
))
WHERE execution_status = 'RUNNING'
   OR total_elapsed_time >= 5000
ORDER BY start_time DESC;
```

The result limit can truncate a busy account. Use narrower windows or warehouse/user-specific variants when needed. Running queries may not yet have final counters. Source: [query history table functions](https://docs.snowflake.com/en/sql-reference/functions/query_history).

### Q03 — Queue and execution breakdown

```sql
SELECT query_id,
       warehouse_name,
       total_elapsed_time,
       compilation_time,
       execution_time,
       queued_provisioning_time,
       queued_repair_time,
       queued_overload_time,
       transaction_blocked_time,
       list_external_files_time,
       bytes_spilled_to_local_storage,
       bytes_spilled_to_remote_storage
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
  AND (queued_overload_time > 0
       OR queued_provisioning_time > 0
       OR queued_repair_time > 0
       OR transaction_blocked_time > 0)
ORDER BY total_elapsed_time DESC
LIMIT 200;
```

Queue components diagnose different causes. Remote spill is not automatically a warehouse-size recommendation; inspect pruning, join shape and workload concurrency first. Source: [`QUERY_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/query_history).

### Q04 — Recent query failures

```sql
SELECT query_id,
       start_time,
       user_name,
       role_name,
       warehouse_name,
       query_type,
       execution_status,
       error_code,
       error_message,
       query_text
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
  AND execution_status = 'FAIL'
ORDER BY start_time DESC
LIMIT 200;
```

This is SQL execution history, not a complete internal service log. Protect error and query text.

### Q05 — Lock waits

```sql
SELECT requested_at,
       acquired_at,
       transaction_id,
       query_id,
       blocking_transaction_id,
       blocking_query_id,
       resource
FROM SNOWFLAKE.ACCOUNT_USAGE.LOCK_WAIT_HISTORY
WHERE requested_at >= DATEADD('hour', -1, CURRENT_TIMESTAMP())
ORDER BY requested_at DESC
LIMIT 200;
```

A row records a lock wait observed by the history view. Join query IDs to Query History for statement context, allowing for each view's latency. Do not cancel a blocker solely from an old history row. Source: [`LOCK_WAIT_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/lock_wait_history).

### Q06 — Expensive query patterns

```sql
SELECT query_hash,
       query_type,
       warehouse_name,
       count(*) AS executions,
       avg(total_elapsed_time) AS mean_elapsed_ms,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY total_elapsed_time)
         AS p95_elapsed_ms,
       sum(bytes_scanned) AS total_bytes_scanned,
       sum(bytes_spilled_to_remote_storage) AS total_remote_spill_bytes,
       max(query_text) AS example_query
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
WHERE start_time >= DATEADD('day', -1, CURRENT_TIMESTAMP())
  AND execution_status = 'SUCCESS'
GROUP BY query_hash, query_type, warehouse_name
ORDER BY total_bytes_scanned DESC
LIMIT 100;
```

Query hashes can change when text structure changes and should not replace application query tags. Group warehouses separately because size and concurrency affect runtime.

### Q07 — Query-history freshness

```sql
SELECT max(start_time) AS newest_query_start,
       DATEDIFF('minute', max(start_time), CURRENT_TIMESTAMP())
         AS newest_record_age_minutes,
       count_if(start_time >= DATEADD('hour', -24, CURRENT_TIMESTAMP()))
         AS records_last_24_hours
FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY;
```

An idle account naturally has an old newest record. Correlate freshness with expected workload before alerting.

### Q08 — Warehouse load

```sql
SELECT start_time,
       end_time,
       warehouse_name,
       avg_running,
       avg_queued_load,
       avg_queued_provisioning,
       avg_blocked
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_LOAD_HISTORY
WHERE start_time >= DATEADD('hour', -6, CURRENT_TIMESTAMP())
ORDER BY start_time DESC, warehouse_name;
```

Values are interval averages. Short spikes can be hidden by aggregation; corroborate sustained queueing with individual Query History records. Source: [`WAREHOUSE_LOAD_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/warehouse_load_history).

### Q09 — Warehouse credits and idle estimate

```sql
SELECT warehouse_name,
       DATE_TRUNC('hour', start_time) AS usage_hour,
       sum(credits_used_compute) AS compute_credits,
       sum(credits_used_cloud_services) AS cloud_services_credits,
       sum(credits_attributed_compute_queries) AS attributed_query_credits,
       sum(credits_used_compute)
         - sum(credits_attributed_compute_queries) AS estimated_idle_credits
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_METERING_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY warehouse_name, usage_hour
ORDER BY usage_hour DESC, warehouse_name;
```

Attributed query credits exclude some usage and can be null for unsupported warehouse types. Credits in this view are not necessarily billed credits after adjustments. Source: [`WAREHOUSE_METERING_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/warehouse_metering_history).

### Q10 — Warehouse lifecycle events

```sql
SELECT timestamp,
       warehouse_name,
       cluster_number,
       event_name,
       event_reason,
       event_state,
       user_name,
       role_name,
       query_id
FROM SNOWFLAKE.ACCOUNT_USAGE.WAREHOUSE_EVENTS_HISTORY
WHERE timestamp >= DATEADD('day', -1, CURRENT_TIMESTAMP())
ORDER BY timestamp DESC
LIMIT 500;
```

Use this to correlate suspend, resume, resize and cluster events with queueing. Available event names evolve; do not hard-fail on a new value. Source: [`WAREHOUSE_EVENTS_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/warehouse_events_history).

### Q11 — Account storage trend

```sql
SELECT usage_date,
       storage_bytes,
       stage_bytes,
       failsafe_bytes,
       hybrid_table_storage_bytes
FROM SNOWFLAKE.ACCOUNT_USAGE.STORAGE_USAGE
WHERE usage_date >= DATEADD('day', -30, CURRENT_DATE())
ORDER BY usage_date DESC;
```

Fields can be null when a feature is unused. Daily account storage does not attribute all bytes to a current table. Source: [`STORAGE_USAGE`](https://docs.snowflake.com/en/sql-reference/account-usage/storage_usage).

### Q12 — Table storage

```sql
SELECT table_catalog,
       table_schema,
       table_name,
       active_bytes,
       time_travel_bytes,
       failsafe_bytes,
       retained_for_clone_bytes
FROM SNOWFLAKE.ACCOUNT_USAGE.TABLE_STORAGE_METRICS
WHERE table_dropped IS NULL
ORDER BY active_bytes + time_travel_bytes + failsafe_bytes DESC
LIMIT 200;
```

Clone, Time Travel and Fail-safe bytes have different ownership and billing interpretations. Source: [`TABLE_STORAGE_METRICS`](https://docs.snowflake.com/en/sql-reference/account-usage/table_storage_metrics).

### Q13 — Automatic clustering history

```sql
SELECT start_time,
       end_time,
       database_name,
       schema_name,
       table_name,
       credits_used,
       num_bytes_reclustered,
       num_rows_reclustered
FROM SNOWFLAKE.ACCOUNT_USAGE.AUTOMATIC_CLUSTERING_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
ORDER BY start_time DESC
LIMIT 200;
```

Only applies where automatic clustering is used. A clustering key should be justified by workload benefit, not by credits alone. Source: [`AUTOMATIC_CLUSTERING_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/automatic_clustering_history).

### Q14 — Materialized-view refresh history

```sql
SELECT start_time,
       end_time,
       database_name,
       schema_name,
       table_name,
       credits_used
FROM SNOWFLAKE.ACCOUNT_USAGE.MATERIALIZED_VIEW_REFRESH_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
ORDER BY start_time DESC
LIMIT 200;
```

Use only for materialized views and validate columns in the current service documentation. Source: [`MATERIALIZED_VIEW_REFRESH_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/materialized_view_refresh_history).

### Q15 — Copy/load failures

```sql
SELECT last_load_time,
       table_catalog_name,
       table_schema_name,
       table_name,
       file_name,
       status,
       row_count,
       row_parsed,
       first_error_message,
       first_error_line_number,
       first_error_character_position
FROM SNOWFLAKE.ACCOUNT_USAGE.COPY_HISTORY
WHERE last_load_time >= DATEADD('hour', -24, CURRENT_TIMESTAMP())
  AND status != 'Loaded'
ORDER BY last_load_time DESC
LIMIT 200;
```

Status values and partial-load semantics must be interpreted with the COPY options. File names and errors can be sensitive. Source: [`COPY_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/copy_history).

### Q16 — Task failures

```sql
SELECT query_id,
       name,
       database_name,
       schema_name,
       scheduled_time,
       completed_time,
       state,
       error_code,
       error_message,
       return_value
FROM SNOWFLAKE.ACCOUNT_USAGE.TASK_HISTORY
WHERE scheduled_time >= DATEADD('day', -1, CURRENT_TIMESTAMP())
  AND state IN ('FAILED', 'CANCELLED')
ORDER BY scheduled_time DESC
LIMIT 200;
```

Task graph retries and predecessor state need separate correlation. Source: [`TASK_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/task_history).

### Q17 — Serverless task credits

```sql
SELECT start_time,
       end_time,
       task_id,
       task_name,
       schema_id,
       database_id,
       credits_used
FROM SNOWFLAKE.ACCOUNT_USAGE.SERVERLESS_TASK_HISTORY
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
ORDER BY start_time DESC;
```

This covers serverless task compute, not warehouse-backed task cost. Source: [`SERVERLESS_TASK_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/serverless_task_history).

### Q18 — Login failures

```sql
SELECT event_timestamp,
       user_name,
       client_ip,
       reported_client_type,
       is_success,
       error_code,
       error_message,
       first_authentication_factor,
       second_authentication_factor
FROM SNOWFLAKE.ACCOUNT_USAGE.LOGIN_HISTORY
WHERE event_timestamp >= DATEADD('hour', -24, CURRENT_TIMESTAMP())
  AND is_success = 'NO'
ORDER BY event_timestamp DESC
LIMIT 200;
```

Restrict this security-sensitive view. Repeated failures can be configuration mistakes or attacks; do not infer intent from the row alone. Source: [`LOGIN_HISTORY`](https://docs.snowflake.com/en/sql-reference/account-usage/login_history).

## Internal server logs and historical events

### Recommended logging baseline

Snowflake manages the database service and does not expose host log files through SQL. Treat Query History, warehouse histories, load/task histories, alerts, event tables and the service status/support channels as separate evidence sources. For application code running in Snowflake, configure event-table telemetry deliberately; an event table contains emitted handler/application telemetry, not a universal Snowflake server log. [Event tables](https://docs.snowflake.com/en/developer-guide/logging-tracing/event-table-setting-up).

For recurring collection, prefer Account Usage for durable analysis and Information Schema for recent incident response. Preserve the source view and observed ingestion delay. Never equate an empty delayed view with absence of activity.

## Deeper diagnosis and rollout

Use Query Profile for a selected query ID to inspect operator-level work, pruning, spill and skew. Query Profile is richer than the summary fields above, but profile availability and programmatic interfaces should be validated for the deployment. [Query Profile](https://docs.snowflake.com/en/user-guide/ui-query-profile).

Suggested rollout:

1. Establish Q01, UTC and least-privilege role visibility.
2. Poll Q02 from Information Schema every 15–30 seconds for incident detection.
3. Ingest Q03–Q07 from Account Usage with overlap and per-view freshness tracking.
4. Collect Q08–Q10 hourly or more frequently where latency supports it; correlate load, credits and lifecycle events.
5. Capture Q11–Q17 daily or hourly according to operational need and feature use.
6. Route Q18 to a security-controlled destination.
7. Validate result-limit handling, view latency, retention, edition restrictions and new columns in every account/region used.

SQL metadata does not replace Snowflake service-status signals, client/network telemetry or application end-to-end latency. Protect query text, object names, errors, login history and tags as customer data.
