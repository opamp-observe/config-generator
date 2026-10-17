<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Java application detector logic

Discovery requires a live `java` or `javaw` process. Host UUID, PID/start time,
JVM path, launch target, working directory, `JAVA_HOME`, OpenTelemetry service
name, and Windows service name provide instance identity.

Configuration evidence covers JUL, Logback, Log4j, Spring application config,
and the OpenTelemetry Java agent. Log discovery covers stdio, JVM unified
logging (`-Xlog`), fatal-error and heap-dump files, JFR, Spring
`logging.file.*`, logging-framework appenders, and OpenTelemetry agent output.
Linux adds open-file and selected environment evidence; Windows is limited to
process commands, conventional candidates, and service data.

JMX registry/connector ports are matched to explicit JVM properties. Other
listeners are labelled application candidates; Spring Actuator paths such as
`/actuator/prometheus` and `/actuator/metrics` require endpoint exposure and a
probe before use. OpenTelemetry exporter and JMX settings are reported without
collecting exporter headers. Programmatic logging, custom MBeans/exporters,
dynamic configuration, and exact JVM versions cannot be proven from host
metadata alone.

