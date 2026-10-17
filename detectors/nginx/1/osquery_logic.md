<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# NGINX detector logic

The detector matches a live `nginx` process. It separates master/single and
worker evidence where the operating system exposes enough parent or command
information. Host UUID, PID, start time, executable, launch command, and
Windows service name form the instance identity.

`configuration_files` reports the `-c` file, `-p` prefix, and documented or
distribution defaults. `log_locations` reports Linux descriptors that are
actually open and candidates from `access_log`, `error_log`, `-e`, stderr, and
syslog. Relative paths are resolved by NGINX against its active prefix, which
cannot always be reconstructed from core osquery data.

`metrics_outputs` returns listener bases only. The `stub_status` location is
chosen in configuration and the newer NGINX API may be configured separately;
therefore every row is marked as a candidate pending configuration review or a
probe. The detector does not assume `/basic_status`, HTTP rather than HTTPS, or
that a status module was compiled in.

Core osquery does not parse NGINX configuration text and the detector does not
execute `nginx -V`. Exact build versions, compile-time paths, included config
files, virtual-host logs, syslog targets, and status locations may require a
privileged follow-up collector.

