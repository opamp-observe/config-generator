<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# PostgreSQL 17 detector logic

Detector: `postgresql_17` version `1.0.0`  
Packs: [Linux](packs/linux.conf) and [Windows](packs/windows.conf)

## Discovery

Linux discovery requires the `postgres` postmaster process and excludes worker
process command lines beginning with `postgres:`. Version 17 must be visible in
`PG_MAJOR`, the executable/data path, or the command line. Windows discovery
requires a PostgreSQL service plus version evidence in its name, executable
path, or an installed-program record.

## Runtime, files, and network output

`runtime` returns the postmaster or Windows service and its data-directory
evidence. Linux prefers `PGDATA`, then the `-D` argument, then the process
working directory. Windows derives the data directory from the service
command. `network_ports` returns sockets owned by the postmaster or resolved
service process.

`configuration_files` reports candidates for `postgresql.conf`,
`postgresql.auto.conf`, `pg_hba.conf`, and `pg_ident.conf`. `log_locations`
reports the conventional data-directory `log` candidate and notes that stderr
may instead be captured by a container runtime or service manager.
`version_evidence` returns the environment, path, command-line, service, or
installed-program evidence used to identify PostgreSQL 17.

Settings such as `config_file`, `hba_file`, `ident_file`, `data_directory`, and
`log_directory` can override the reported candidates. Core osquery does not
parse PostgreSQL configuration content, so these remain candidates.

## Documentation used

- https://www.postgresql.org/docs/17/runtime-config-file-locations.html
- https://www.postgresql.org/docs/17/app-postgres.html
- https://www.postgresql.org/docs/17/storage-file-layout.html

