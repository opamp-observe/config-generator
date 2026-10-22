<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0. See license.txt in the project root.
-->

# Database monitoring query analysis

This folder contains version-aware query guides for investigating database health and performance from inside each database product. The guides are intended for monitoring design, incident diagnosis and collector implementation. They are not universal, ready-to-run monitoring scripts: supported views, privileges, editions, topology and retention settings must be validated against the exact deployment being monitored.

## Document structure

Each guide follows the same general structure, adapted where a product exposes different monitoring interfaces:

1. **Scope and interpretation** defines the product releases, editions and deployment models covered by the guide.
2. **Available telemetry** summarizes what can be observed through SQL, CQL, shell commands, system tables, dynamic views or product-specific history services.
3. **Prerequisites and collection rules** describes permissions, optional features, retention limits, sampling guidance and operational cautions.
4. **Compatibility matrix** identifies which query families and monitoring features are available for each covered release or service model.
5. **Query catalogue** provides diagnostic queries grouped by operational concern, such as workload, latency, waits, locks, memory, storage, replication and failures.
6. **Internal logs and historical events** explains database-resident log or event sources when the product makes them queryable.
7. **Deeper diagnosis and rollout guidance** covers escalation paths, least-privilege deployment, validation and collection overhead.
8. **References** cite official product documentation, either in a dedicated section or alongside the relevant guidance.

Query identifiers such as `Q01` are local to their document. The same identifier in two guides does not imply that the queries are equivalent. Placeholders, thresholds, intervals and object names are examples unless the guide explicitly states otherwise.

## Guide index

| Product | Guide | Versions or service scope covered | Primary query interface | Scope notes |
|---|---|---|---|---|
| Apache Cassandra | [Apache Cassandra monitoring queries](apache_cassandra_monitoring_queries.md) | 4.0, 4.1 and 5.0 | CQL and `system_views` virtual tables | Later releases can add virtual tables and columns; discover the schema on each supported version. |
| ClickHouse | [ClickHouse monitoring queries](clickhouse_monitoring_queries.md) | Self-managed 25.3 LTS, 25.8 LTS, 26.3 LTS and 26.8 LTS; ClickHouse Cloud notes | SQL and `system` tables | Cloud availability, retention and privileges can differ from self-managed deployments. |
| MariaDB | [MariaDB monitoring queries](mariadb_monitoring_queries.md) | Community Server LTS 10.11, 11.4, 11.8 and 12.3 | SQL, Performance Schema and Information Schema | MariaDB 10.6 is treated as legacy and is outside the primary matrix; InnoDB is the principal storage engine. |
| MongoDB | [MongoDB monitoring queries](mongodb-monitoring-queries.md) | MongoDB Server 6.0, 7.0 and 8.0 | `mongosh`, database commands and aggregation pipelines | Later rapid releases and MongoDB 9.0 are outside the compatibility matrix. |
| MySQL | [MySQL monitoring queries](mysql-monitoring-queries.md) | Oracle MySQL 5.7, 8.0 and 8.4 | SQL, Performance Schema, Information Schema and `sys` | MySQL 5.7 is included for installed-estate compatibility; InnoDB is the principal storage engine. |
| Oracle Database | [Oracle Database monitoring queries](oracle-database-monitoring-queries.md) | 12.2, 19c, 21c and Oracle AI Database 26ai | SQL and dynamic performance views | Earlier releases are legacy; 26ai replaces the former 23ai branding and release line. |
| PostgreSQL | [PostgreSQL monitoring queries](postgresql-monitoring-queries.md) | Community PostgreSQL 14 through 18 | SQL, statistics views and catalog views | PostgreSQL 19 is pre-release and PostgreSQL 13 and earlier are outside the matrix. |
| SAP HANA | [SAP HANA monitoring queries](sap_hana_monitoring_queries.md) | SAP HANA Platform 2.0 SPS 05 through SPS 08; SAP HANA Cloud | SQL and monitoring views | Availability depends on deployment model, revision, tenant context, edition and privileges. |
| Snowflake | [Snowflake monitoring queries](snowflake_monitoring_queries.md) | Continuously delivered Snowflake service | SQL, Information Schema and `SNOWFLAKE.ACCOUNT_USAGE` | Compatibility is governed by interface, privilege and edition rather than customer-selected engine versions. |
| SQLite | [SQLite monitoring queries](sqlite_monitoring_queries.md) | SQLite 3.37 through 3.54 | SQL, pragmas and optional compile-time interfaces | Important compatibility landmarks include 3.37, 3.46, 3.53 and 3.54. |
| SQL Server | [SQL Server monitoring queries](sqlserver-monitoring-queries.md) | SQL Server 2016, 2017, 2019, 2022 and 2025 | T-SQL, dynamic management views and catalog views | Older releases are included for installed-estate compatibility. |

## Using the guides

1. Identify the exact product release, edition, topology and enabled monitoring features.
2. Read the guide's scope, prerequisites and compatibility matrix before selecting queries.
3. Start with the environment and capability checks, then add only the query families needed for the monitoring objective.
4. Bind parameters where supported, bound result sizes and collect an observation timestamp and instance or node identity with every sample.
5. Validate queries with least-privilege credentials on the exact target release and measure their overhead before production rollout.

## Interpretation conventions

- Compatibility symbols and qualifications are defined within each guide and should be interpreted in that guide's context.
- Cumulative counters normally require two samples and a time-normalized delta; gauges and current-state values should not be differenced.
- Live activity views describe current state and do not provide historical evidence unless a collector persists samples.
- In clustered or distributed products, a query may be node-local even when it is syntactically valid on every node.
- Optional monitoring repositories, statement histories and internal logs may require explicit enablement, licensing, configuration or elevated privileges.

## Maintaining this index

When a guide adds or removes product-version coverage, update its scope and compatibility matrix together with the corresponding row in this index. Product inclusion alone must not be interpreted as support for every edition, managed-service variant, optional feature or patch release.
