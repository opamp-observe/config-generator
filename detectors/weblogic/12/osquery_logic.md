<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# WebLogic Server 12.2.1.4 detector logic

Detector: `weblogic_12` version `1.1.0`  
Packs: [Linux](packs/linux.conf) and [Windows](packs/windows.conf)

## Discovery

The detector requires a running JVM whose command line contains
`weblogic.Server`. It then requires 12.2.1.4 evidence (`12.2.1.4` or `12214`)
in the executable path, command line, Linux process environment, or a Windows
installed-program record. Osquery processes are excluded to prevent the SQL
text itself from becoming detection evidence.

## Server mapping and output

`runtime` extracts `-Dweblogic.Name` as the server name. A JVM with
`-Dweblogic.management.server` is classified as a Managed Server and the value
supplies its Administration Server endpoint; a JVM without that option is
classified as the Administration Server. `network_ports` associates sockets
owned by each JVM with that mapping.

`configuration_files` reports the central
`DOMAIN_HOME/config/config.xml` candidate. `DOMAIN_HOME` or `WL_DOMAIN_HOME`
is preferred on Linux; otherwise the working directory, with a trailing `bin`
removed, is used. `log_locations` reports the per-server `servers/<name>/logs`
directory, server log candidate, and Node Manager log candidate.

`version_evidence` returns the process path and command line that caused the
release to match. All paths are candidates derived from observable process
state; the detector does not parse `config.xml` or Java system properties that
are not present in the command line.

## Observability URLs

`observability_urls` derives candidate URLs for every TCP socket owned by a
matched WebLogic JVM. It reports the authenticated WebLogic server-runtime
health resource, ReadyApp `/ready`, the WebLogic Kubernetes Operator
`/weblogic/ready` path, and `/wls-exporter/metrics` for the separately deployed
WebLogic Monitoring Exporter.

The query does not make HTTP requests, identify which WebLogic channel is HTTP,
or prove that the ReadyApp/exporter applications are deployed. URLs therefore
carry `candidate_not_probed`, assume HTTP, and require TLS/channel verification.
The operator's default liveness probe uses Node Manager rather than a standard
HTTP URL, so `liveness_url_candidate` is empty and `liveness_note` explains the
result instead of inventing an endpoint.

## JVM and Java monitoring

`jvm_runtime` reports the Java executable, `JAVA_HOME`, vendor evidence, and a
JVM/JDK version. Linux prefers process environment values and falls back to a
Debian/RPM package candidate; Windows correlates the executable with an
installed JDK record. `version_source` identifies the evidence strength.

`java_monitoring_endpoints` returns only sockets that are both listening and
explicitly matched by JVM arguments for JMX registry/RMI, JDP discovery, or
JDWP debugging. It constructs the appropriate monitoring URL and reports the
visible JMX authentication and SSL settings. Dynamic RMI ports that are not
pinned with `com.sun.management.jmxremote.rmi.port` cannot be identified
reliably from command-line evidence.

## Documentation used

- https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/12.2.1.4/admrf/weblogicserver.html
- https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/12.2.1.4/wllog/logging_services.html
- https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/12.2.1.4/wlach/taskhelp/domainconfig/CreateManagedServers.html
- https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/12.2.1.4/depgd/managing.html
- https://docs.oracle.com/en/middleware/fusion-middleware/weblogic-server/12.2.1.4/wlrsr/monitor-servers.html
- https://docs.oracle.com/en/java/javase/17/management/monitoring-and-management-using-jmx-technology.html
- https://oracle.github.io/weblogic-kubernetes-operator/managing-domains/domain-lifecycle/liveness-readiness-probe-customization/

