<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Python application detector logic

Discovery matches Python processes while excluding obvious package/test and
osquery validation commands, plus common application-server executables.
Because Python is a general runtime, this is intentionally broader than a
framework-specific detector. PID/start time, executable, working directory,
launch command, virtual environment, OpenTelemetry service name, and Windows
service name provide available instance identifiers.

Python logging handlers can emit to streams, files, sockets, syslog, email, or
application-defined handlers. Gunicorn adds access/error files, stdio capture,
syslog, and StatsD; Uvicorn accepts JSON/YAML/INI logging configuration and
normally writes to stdio. Linux queries report actual open log/config files and
safe environment keys. Windows core osquery cannot read another process's
environment or open files, so it reports CLI and conventional candidates.

OpenTelemetry exporter settings are exact when visible in Linux process
environment data. Listening sockets are not labelled as Prometheus endpoints:
their paths depend on the framework and application. Exporter authentication
headers are deliberately not collected. In-code `dictConfig`, custom handlers,
programmatically constructed metrics exporters, and secrets cannot be inferred
from host metadata alone.

