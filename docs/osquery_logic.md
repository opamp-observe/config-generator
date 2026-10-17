<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Osquery detector logic

## Design

A detector is a manifest plus one osquery query pack per supported operating
system. Discovery is deliberately strict: a product process must exist and
version evidence must appear in a binary path, command line, process
environment (Linux), Windows service registration, or installed-program record.
This avoids reporting the same running product as every supported version.

The runner evaluates discovery immediately with `osqueryi --json`, then runs
the pack's detail queries and writes one aggregate JSON document. Standard pack
intervals remain present so the same pack can also be scheduled by
`osqueryd`.

Every pack exposes configuration paths and log paths independently. The
`configuration_files` result contains only configuration-file candidates, while
`log_locations` contains log-file, log-directory, or log-glob candidates. This
keeps the two inventories separately addressable in both direct pack execution
and the aggregate runner output.
See [Detector output to Fluent Bit configuration](fluent_bit_transform_findings.md)
for the transformation problem, evaluated standards and libraries, and the
recommended schema-validated generation pipeline.

Osquery observes a listening socket; it does not probe reachability through
host firewalls, container publishing rules, Kubernetes Services, or load
balancers. Therefore `network_ports` means locally listening endpoints, not
guaranteed externally reachable ports.

## Detector-specific logic

Each detector has its own colocated logic document containing its
version-matching evidence, output interpretation, limitations, and source
documentation. The [detector catalogue](../detectors/catalogue.md) summarises
the supported product versions and operating systems.

- [WebLogic Server 12.2.1.4](../detectors/weblogic/12/osquery_logic.md)
- [WebLogic Server 14.1.1](../detectors/weblogic/14/osquery_logic.md)
- [NGINX](../detectors/nginx/1/osquery_logic.md)
- [Apache HTTP Server](../detectors/apache_http_server/1/osquery_logic.md)
- [Python applications](../detectors/python_app/1/osquery_logic.md)
- [Node.js applications](../detectors/nodejs_app/1/osquery_logic.md)
- [Java applications](../detectors/java_app/1/osquery_logic.md)
- [SQLite](../detectors/sqlite/1/osquery_logic.md)
- [Oracle Database 19c](../detectors/oracle_database/19/osquery_logic.md)
- [Oracle Database 21c](../detectors/oracle_database/21/osquery_logic.md)
- [Oracle Database 26ai](../detectors/oracle_database/26/osquery_logic.md)
- [PostgreSQL 17](../detectors/postgresql/17/osquery_logic.md)
- [PostgreSQL 18](../detectors/postgresql/18/osquery_logic.md)
- [PostgreSQL 19](../detectors/postgresql/19/osquery_logic.md)
- [Host inventory](../detectors/host_inventory/1/osquery_logic.md)

## Container boundary

Run osquery in the target container or in an image derived from it for complete
filesystem and process visibility. A host osquery process sees host-side
container shims and published ports, not the application process namespace.
A PID/network sidecar can see processes and sockets when configured with the
target namespaces, but it does not automatically see the target image's root
filesystem. See [container testing](container_testing.md).

