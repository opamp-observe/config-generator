<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Linux system capabilities detector

Detector name: `linux_system_1`  
Detector version: `1.0.0`  
Product release status: `stable`

This Linux-only detector complements `host_inventory_1`. The host inventory
continues to provide portable identity and environment data; this detector
provides Linux kernel and networking detail plus logging capability checks.

Run it from the repository root with:

```sh
python3 runner.py --detector linux_system_1
```

The detector returns every visible interface and address, observed network and
transport protocols, the route table, listening sockets, DNS configuration,
kernel information, a kernel-log access assessment, and syslog provider
availability. See [detailed detector logic](osquery_logic.md) for field
interpretation and namespace, permission, and container limitations.

## Documentation used

- https://github.com/osquery/osquery/blob/master/specs/kernel_info.table
- https://github.com/osquery/osquery/blob/master/specs/interface_addresses.table
- https://github.com/osquery/osquery/blob/master/specs/interface_details.table
- https://github.com/osquery/osquery/blob/master/specs/routes.table
- https://github.com/osquery/osquery/blob/master/specs/listening_ports.table
- https://github.com/osquery/osquery/blob/master/specs/posix/dns_resolvers.table
- https://github.com/osquery/osquery/blob/master/specs/linux/syslog_events.table
