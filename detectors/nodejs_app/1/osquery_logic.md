<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Node.js application detector logic

Discovery requires a live `node`/`nodejs` process. The host UUID, PID/start
time, executable, working directory, launch command, npm package name,
`NODE_APP_INSTANCE`, OpenTelemetry service name, and Windows service name are
reported when observable.

Node.js sends application console output and warnings to stdio by default, but
`--redirect-warnings`, diagnostic report/profile flags, custom logger
transports, and process managers can write files. Linux queries report actual
open logs/configs and selected non-secret environment values. Candidates cover
`package.json`, `.env`, `ecosystem.config.*`, `NODE_OPTIONS`, diagnostic output,
and `PM2_HOME/logs`. Windows reports command and working-directory evidence
because core osquery has no cross-process environment/open-file tables there.

Node.js has no universal application metrics URL. OpenTelemetry exporter
variables are exact evidence when visible; listeners are candidates for an
application-configured endpoint. Inspector ports are labelled separately when
the launch command contains `--inspect`, and are not called metrics endpoints.
In-code logger transports, custom metric readers, and dynamic config remain
outside what process metadata can prove.

