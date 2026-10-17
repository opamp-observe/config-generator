<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# SQLite generic detector

Detector name: `sqlite_1`  
Detector version: `1.0.0`  
Product versions: SQLite 3.x or an embedded SQLite library

SQLite is an in-process library rather than a server. The detector maps
database and journal evidence to the owning application, reports that owner's
state and sockets, and records the observability features that must be supplied
by that application.

```sh
python3 runner.py --detector sqlite_1
```

See [detailed detector logic](osquery_logic.md).

## Documentation used

- https://sqlite.org/fileformat.html
- https://sqlite.org/wal.html
- https://sqlite.org/tempfiles.html
- https://sqlite.org/cli.html

