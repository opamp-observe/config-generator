<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# SQLite detector logic

Linux discovery uses open files to find conventional `.db`, `.sqlite`, and
`.sqlite3` databases and their rollback-journal/WAL companions. It then reports
the owning CLI or embedding application. SQLite permits arbitrary filenames,
so a no-extension database without an observable `sqlite3` command cannot be
identified from metadata alone. Windows core osquery lacks
`process_open_files`; its detector is consequently limited to the CLI and
database names exposed in process commands.

The configuration inventory classifies main database, `-journal`, `-wal`, and
`-shm` files. WAL and rollback journals are database state, not application
logs. Stable identity is the host UUID plus database path; an active owner is
identified by PID plus start time.

SQLite has no daemon state, listener, log destination, or native metrics
endpoint. Those belong to the embedding process. `service_state`,
`network_ports`, `log_locations`, and `metrics_outputs` say this explicitly
instead of creating fictitious SQLite endpoints. Runtime PRAGMAs, in-memory
databases, statically linked library versions, and dynamically chosen database
filenames require application-level instrumentation.

