<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# NGINX generic detector

Detector name: `nginx_1`  
Detector version: `1.0.0`  
Product versions: any observable NGINX runtime

The Linux and Windows packs inventory NGINX processes, service state, stable
instance identifiers, configuration candidates, log outputs, sockets, and
candidate status/metrics endpoints. Run it from the repository root with:

```sh
python3 runner.py --detector nginx_1
```

See [detailed detector logic](osquery_logic.md) for evidence levels and
limitations.

## Documentation used

- https://nginx.org/en/docs/switches.html
- https://nginx.org/en/docs/configure.html
- https://nginx.org/en/docs/http/ngx_http_log_module.html
- https://nginx.org/en/docs/ngx_core_module.html#error_log
- https://nginx.org/en/docs/syslog.html
- https://nginx.org/en/docs/http/ngx_http_stub_status_module.html

