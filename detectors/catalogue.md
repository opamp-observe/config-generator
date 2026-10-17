<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Detector catalogue

This catalogue lists the detector versions, product versions, release status,
and operating-system packs supplied by the repository. Linux and Windows mean
that a detector has an osquery pack for that operating system; consult its logic
document for discovery limitations and container visibility requirements.

| Product | Detector | Product version | Detector version | Release status | Operating systems | Documentation |
|---|---|---:|---:|---|---|---|
| Apache HTTP Server | `apache_http_server_1` | Any | 1.0.0 | Stable | Linux, Windows | [README](apache_http_server/1/readme.md) · [Logic](apache_http_server/1/osquery_logic.md) |
| Host Inventory | `host_inventory_1` | 1 | 1.0.0 | Stable | Linux, Windows | [README](host_inventory/1/README.md) · [Logic](host_inventory/1/osquery_logic.md) |
| Java Application | `java_app_1` | Any | 1.0.0 | Stable | Linux, Windows | [README](java_app/1/readme.md) · [Logic](java_app/1/osquery_logic.md) |
| NGINX | `nginx_1` | Any | 1.0.0 | Stable | Linux, Windows | [README](nginx/1/readme.md) · [Logic](nginx/1/osquery_logic.md) |
| Node.js Application | `nodejs_app_1` | Any | 1.0.0 | Stable | Linux, Windows | [README](nodejs_app/1/readme.md) · [Logic](nodejs_app/1/osquery_logic.md) |
| Oracle Database | `oracle_database_19` | 19c | 1.0.0 | Stable | Linux, Windows | [README](oracle_database/19/README.md) · [Logic](oracle_database/19/osquery_logic.md) |
| Oracle Database | `oracle_database_21` | 21c | 1.0.0 | Stable | Linux, Windows | [README](oracle_database/21/README.md) · [Logic](oracle_database/21/osquery_logic.md) |
| Oracle Database | `oracle_database_26` | 26ai (23.26.x) | 1.0.0 | Stable | Linux, Windows | [README](oracle_database/26/README.md) · [Logic](oracle_database/26/osquery_logic.md) |
| PostgreSQL | `postgresql_17` | 17 | 1.0.0 | Stable | Linux, Windows | [README](postgresql/17/README.md) · [Logic](postgresql/17/osquery_logic.md) |
| PostgreSQL | `postgresql_18` | 18 | 1.0.0 | Stable | Linux, Windows | [README](postgresql/18/README.md) · [Logic](postgresql/18/osquery_logic.md) |
| PostgreSQL | `postgresql_19` | 19 | 1.0.0 | Development | Linux, Windows | [README](postgresql/19/README.md) · [Logic](postgresql/19/osquery_logic.md) |
| Python Application | `python_app_1` | Any | 1.0.0 | Stable | Linux, Windows | [README](python_app/1/readme.md) · [Logic](python_app/1/osquery_logic.md) |
| SQLite | `sqlite_1` | 3.x or embedded | 1.0.0 | Stable | Linux, Windows | [README](sqlite/1/readme.md) · [Logic](sqlite/1/osquery_logic.md) |
| Oracle WebLogic Server | `weblogic_12` | 12.2.1.4 | 1.1.0 | Stable | Linux, Windows | [README](weblogic/12/README.md) · [Logic](weblogic/12/osquery_logic.md) |
| Oracle WebLogic Server | `weblogic_14` | 14.1.1 | 1.1.0 | Stable | Linux, Windows | [README](weblogic/14/README.md) · [Logic](weblogic/14/osquery_logic.md) |

The detector manifest in each version directory is the machine-readable source
of truth for identity, product version, release status, supported platforms,
pack paths, output contract, schema, and source documentation.
