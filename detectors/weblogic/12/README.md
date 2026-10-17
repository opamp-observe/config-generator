<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Oracle WebLogic Server 12.2.1.4 detector

Detector name: `weblogic_12`  
Detector version: `1.1.0`  
Product release status: `stable`

This folder contains strict Linux and Windows osquery packs. It reports runtime
instances, candidate configuration-file and log locations in separate query
results, and locally listening
ports. Product-specific relationship or deployment evidence is included in the
additional queries. Run it from the repository root with:

```sh
python3 runner.py --detector weblogic_12
```

Exact version discovery depends on observable path, command-line, environment,
service, or installed-program evidence. Use `--include-undetected` only while
diagnosing unusual installations, then review the evidence before treating the
result as a positive detection.

See [detailed detector logic](osquery_logic.md) for
discovery evidence, server mapping, query output, and limitations.

Observability output includes candidate health, ReadyApp/operator readiness,
and WebLogic Monitoring Exporter URLs. Separate queries report JVM/JDK version
evidence and listening JMX, JDP, or JDWP endpoints.

## Documentation used

- https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/12.2.1.4/admrf/weblogicserver.html
- https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/12.2.1.4/wllog/logging_services.html
- https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/12.2.1.4/wlach/taskhelp/domainconfig/CreateManagedServers.html
- https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/12.2.1.4/depgd/managing.html
- https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/12.2.1.4/wlrsr/monitor-servers.html
- https://docs.oracle.com/en/java/javase/17/management/monitoring-and-management-using-jmx-technology.html
- https://oracle.github.io/weblogic-kubernetes-operator/managing-domains/domain-lifecycle/liveness-readiness-probe-customization/

