<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Oracle Database 26ai (23.26.x) detector

Detector name: `oracle_database_26`  
Detector version: `1.1.0`  
Product release status: `stable`

This folder contains strict Linux and Windows osquery packs. It reports runtime
instances, Oracle ASM instances, candidate configuration-file and log locations
in separate query results, and locally listening ports. Product-specific
relationship or deployment evidence is included in the additional queries. Run
it from the repository root with:

```sh
python3 runner.py --detector oracle_database_26
```

Exact version discovery depends on observable path, command-line, environment,
service, or installed-program evidence. Use `--include-undetected` only while
diagnosing unusual installations, then review the evidence before treating the
result as a positive detection.

See [detailed detector logic](osquery_logic.md)
for discovery evidence, ASM, RAC and ORDS handling, query output, and limitations.

## Documentation used

- https://docs.oracle.com/en/database/oracle/oracle-database/26/rilin/how-oracle-database-uses-the-listener-file-listener-ora.html
- https://docs.oracle.com/en/database/oracle/oracle-database/26/netag/oracle-net-services-log-file-names.html
- https://docs.oracle.com/en/database/oracle/oracle-database/26/netrf/index.html
- https://docs.oracle.com/en/database/oracle/oracle-database/26/ostmg/admin-asm-instance.html
- https://docs.oracle.com/en/database/oracle/oracle-rest-data-services/24.4/ordig/installing-and-configuring-oracle-rest-data-services.html

