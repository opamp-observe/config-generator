<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Python application generic detector

Detector name: `python_app_1`  
Detector version: `1.0.0`  
Product versions: any observable Python application runtime

The packs cover Python interpreters and common Gunicorn, Uvicorn, Hypercorn,
and Celery launchers. They expose runtime and service state, application
identity, configuration/log evidence, network listeners, OpenTelemetry export
settings, Prometheus hints, and Gunicorn StatsD configuration.

```sh
python3 runner.py --detector python_app_1
```

See [detailed detector logic](osquery_logic.md).

## Documentation used

- https://docs.python.org/3/howto/logging.html
- https://docs.python.org/3/library/logging.handlers.html
- https://gunicorn.org/reference/settings/
- https://gunicorn.org/instrumentation/
- https://uvicorn.dev/settings/
- https://opentelemetry.io/docs/zero-code/python/configuration/
- https://opentelemetry.io/docs/specs/otel/configuration/sdk-environment-variables/

