<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# PostgreSQL 19 detector

Detector name: `postgresql_19`  
Detector version: `1.0.0`  
Product release status: `development`

This folder contains strict Linux and Windows osquery packs. It reports runtime
instances, candidate configuration-file and log locations in separate query
results, and locally listening
ports. Product-specific relationship or deployment evidence is included in the
additional queries. Run it from the repository root with:

```sh
python3 runner.py --detector postgresql_19
```

Exact version discovery depends on observable path, command-line, environment,
service, or installed-program evidence. Use `--include-undetected` only while
diagnosing unusual installations, then review the evidence before treating the
result as a positive detection.

See [detailed detector logic](osquery_logic.md) for
discovery evidence, path derivation, query output, and limitations.

## Documentation used

- https://www.postgresql.org/docs/19/runtime-config-file-locations.html
- https://www.postgresql.org/docs/19/app-postgres.html
- https://www.postgresql.org/docs/19/runtime-config-logging.html

