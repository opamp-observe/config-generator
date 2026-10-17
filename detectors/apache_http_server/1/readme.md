<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Apache HTTP Server generic detector

Detector name: `apache_http_server_1`  
Detector version: `1.0.0`  
Product versions: any observable Apache HTTP Server runtime

The packs inventory `httpd`/`apache2` processes, Windows services, instance
identifiers, configuration candidates, logs, listeners, and candidate
`mod_status` output. Run it with:

```sh
python3 runner.py --detector apache_http_server_1
```

See [detailed detector logic](osquery_logic.md).

## Documentation used

- https://httpd.apache.org/docs/2.4/programs/httpd.html
- https://httpd.apache.org/docs/2.4/mod/core.html#errorlog
- https://httpd.apache.org/docs/2.4/mod/mod_log_config.html
- https://httpd.apache.org/docs/2.4/mod/mpm_common.html#pidfile
- https://httpd.apache.org/docs/2.4/mod/mod_status.html

