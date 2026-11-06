<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Database query analysis

This collection provides reviewed operational query patterns for inspecting
database performance, slow activity, blocking, resource pressure, replication,
and database-accessible diagnostic history. The examples are starting points
for bounded monitoring and incident analysis, not production-ready grants or
universal polling schedules.

Each database guide includes its supported version scope, least-privilege and
collection guidance, a compatibility matrix, a numbered query catalogue, and
the limitations of retrieving logs or historical events through a database
connection. Validate every selected query against the exact product version,
edition, topology, enabled features, and hosting restrictions before rollout.

## Database guides

| Database | Covered releases | Summary |
| --- | --- | --- |
| [MongoDB](mongodb-monitoring-queries.md) | MongoDB Server 6.0, 7.0, and 8.0 | `mongosh` patterns for active and profiled operations, transactions, lock contention, WiredTiger and storage pressure, indexes, replication and oplog health, optional query statistics, and the bounded in-memory server log. Compatible services such as DocumentDB and Cosmos DB require separate validation. |
| [MySQL](mysql-monitoring-queries.md) | Oracle MySQL 5.7, 8.0, and 8.4 | SQL patterns built around Performance Schema and InnoDB for current activity, statement digests, blocking, metadata locks, storage and I/O pressure, replication, slow-log tables, recent errors, and latest-deadlock evidence. MariaDB, Aurora, and Percona require product-specific validation. |
| [Oracle Database](oracle-database-monitoring-queries.md) | Oracle Database 12.2, 19c, 21c, and Oracle AI Database 26ai | SQL patterns using dynamic performance and ADR views for sessions, cached SQL, locks, resource and undo pressure, RAC-aware scope, Data Guard, alert and trace data, plus clearly separated optional Diagnostics Pack and Tuning Pack queries. |
| [PostgreSQL](postgresql-monitoring-queries.md) | Community PostgreSQL 14 through 18 | SQL patterns for activity, `pg_stat_statements`, blockers and locks, workload and maintenance pressure, WAL, checkpoints, I/O, replication, and controlled access to or import of retained server logs. PostgreSQL 19 is excluded while pre-release. |
| [SQL Server](sqlserver-monitoring-queries.md) | SQL Server 2016, 2017, 2019, 2022, and 2025 | T-SQL patterns for requests, cached statements, blocking, Query Store, memory and I/O pressure, availability groups, backup history, error logs, and Extended Events, with separate scope and permission caveats for Azure SQL and related Microsoft services. |

## Shared usage principles

- Use a dedicated monitoring identity and grant only the permissions needed by
  the selected queries.
- Treat query text, diagnostic messages, plans, and profiler records as
  potentially sensitive data.
- Bound result sizes, text lengths, time windows, and polling frequency; a
  read-only query can still impose material work.
- Compute rates from consecutive counter samples and discard intervals that
  cross restarts, resets, role changes, or counter decreases.
- Do not assume live views provide durable history. Slow-query, error, and
  deadlock evidence generally depends on prior logging, profiling, Query Store,
  Extended Events, ADR retention, or another explicitly enabled facility.
- Keep configuration changes and retained-evidence writers separate from the
  read-only monitoring role.

Query identifiers are local to each guide. Thresholds and collection cadences
are recommendations to tune locally, and documentation-based compatibility is
not a substitute for execution testing on representative non-production
systems.
