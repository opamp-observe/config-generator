<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Oracle Database 19c detector logic

Detector: `oracle_database_19` version `1.1.0`  
Packs: [Linux](packs/linux.conf) and [Windows](packs/windows.conf)

## Discovery

Linux discovery requires an `ora_pmon_<SID>` process plus 19c evidence in its
path, command line, or process environment. Windows discovery requires an
`OracleService<SID>` service plus 19c evidence in the service path or an Oracle
Database installed-program record. Accepted path/version markers include
`19c`, `19.x`, and a versioned `19` directory.

## Database, network, and path output

`runtime` returns the SID/instance name, Oracle binary, command line, and
derived `ORACLE_HOME`/`ORACLE_BASE` evidence. `network_ports` returns sockets
owned by Oracle Net Listener and independently running ORDS processes.

`configuration_files` reports candidates for `listener.ora`, `tnsnames.ora`,
`sqlnet.ora`, the instance SPFILE, and the instance PFILE. `log_locations`
reports ADR text alert-log, XML alert-log, and listener-log globs. Linux prefers
`ORACLE_HOME` and `ORACLE_BASE`; Windows derives candidates from service and
installation paths.

## ASM, RAC, and ORDS

`asm_instances` detects the Linux `asm_pmon_+ASM...` process or Windows
`OracleASMService+ASM...` service. Linux rows include the ASM SID, Grid home,
Oracle base, binary, and candidate PFILE and ADR alert-log paths. Windows rows
include the ASM service identity, state, command, and Grid Infrastructure
installation evidence.

`deployment_features` reports ASM independently from RAC because ASM can run
under Oracle Restart on a non-clustered server. RAC requires Clusterware,
agent, or SCAN-listener evidence. ORDS is separately deployed when an
independent `ords` process, an ORDS Java command line, or an open `ords.war` is
visible. `ords_details` returns its command line, path, socket context, and
`ORDS_CONFIG` or working-directory candidate.

Negative results mean that evidence was not visible to osquery; they do not
prove that a stopped, remote, or namespace-isolated component is absent.

## Documentation used

- https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/DIAGNOSTIC_DEST.html
- https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/SPFILE.html
- https://docs.oracle.com/en/database/oracle/oracle-database/19/netrf/oracle-net-listener-parameters-in-listener-ora.html
- https://docs.oracle.com/en/database/oracle/oracle-database/19/ostmg/asm-instance.html
- https://docs.oracle.com/en/database/oracle/oracle-rest-data-services/24.4/ordig/installing-and-configuring-oracle-rest-data-services.html

