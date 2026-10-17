<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Java application generic detector

Detector name: `java_app_1`  
Detector version: `1.0.0`  
Product versions: any observable JVM application runtime

The packs inventory JVM processes, services, launch identities, configuration
and log outputs, sockets, JMX, OpenTelemetry, and Spring Actuator candidates.

```sh
python3 runner.py --detector java_app_1
```

See [detailed detector logic](osquery_logic.md).

## Documentation used

- https://docs.oracle.com/en/java/javase/25/docs/specs/man/java.html
- https://docs.oracle.com/en/java/javase/25/management/monitoring-and-management-using-jmx-technology.html
- https://docs.spring.io/spring-boot/reference/features/logging.html
- https://docs.spring.io/spring-boot/reference/actuator/endpoints.html
- https://opentelemetry.io/docs/zero-code/java/agent/configuration/
- https://opentelemetry.io/docs/languages/java/jmx/
- https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/

