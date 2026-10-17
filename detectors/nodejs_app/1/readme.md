<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Node.js application generic detector

Detector name: `nodejs_app_1`  
Detector version: `1.0.0`  
Product versions: any observable Node.js application runtime

The packs inventory Node.js processes, services, entry-command identity,
configuration candidates, application logs and diagnostic outputs, sockets,
and OpenTelemetry metrics evidence.

```sh
python3 runner.py --detector nodejs_app_1
```

See [detailed detector logic](osquery_logic.md).

## Documentation used

- https://nodejs.org/api/cli.html
- https://nodejs.org/api/report.html
- https://opentelemetry.io/docs/languages/js/exporters/
- https://opentelemetry.io/docs/languages/js/resources/
- https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/

