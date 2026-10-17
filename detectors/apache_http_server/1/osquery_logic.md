<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Apache HTTP Server detector logic

Discovery requires a live `httpd`, `apache2`, or Windows Apache process. The
runtime and service queries retain parent/worker relationships, process state,
start time, Windows service status, and the host/process fields needed to
distinguish instances.

Apache documents `-d` as the initial `ServerRoot`, `-f` as the config file,
and `-E` as a startup error log. `ErrorLog`, `CustomLog`, and `TransferLog` can
select files, syslog, or piped programs. The pack therefore reports command
evidence, standard candidates, and Linux log files observed open by Apache.
It does not pretend that defaults override a directive in an included file.

The documented machine-readable status form is conventionally
`/server-status?auto`, but the handler, access controls, virtual host, TLS, and
location can all alter availability. `metrics_outputs` marks every endpoint as
a candidate requiring config review or a probe.

Core osquery cannot expand Apache `Include` directives or run `httpd -V`.
Exact versions, compiled-in `SERVER_CONFIG_FILE`/`HTTPD_ROOT`, per-vhost logs,
piped logger commands, and status authorization require follow-up collection.

