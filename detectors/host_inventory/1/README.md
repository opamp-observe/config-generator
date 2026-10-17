<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Host inventory detector

Detector name: `host_inventory_1`  
Detector version: `1.0.0`  
Product release status: `stable`

This detector publishes host identity, operating-system version, IPv4/IPv6
interface addresses, possible container or virtual-machine evidence, and the
user/role context visible to osquery. Run it from the repository root with:

```sh
python3 runner.py --detector host_inventory_1
```

The aggregate JSON places its rows below the `host_inventory_1` detector's
`queries` object. See [detailed detector logic](osquery_logic.md)
for field interpretation and identity/classification limitations.

## Documentation used

- https://github.com/osquery/osquery/blob/master/specs/system_info.table
- https://github.com/osquery/osquery/blob/master/specs/os_version.table
- https://github.com/osquery/osquery/blob/master/specs/interface_addresses.table
- https://github.com/osquery/osquery/blob/master/specs/processes.table
- https://github.com/osquery/osquery/blob/master/specs/logged_in_users.table
- https://github.com/osquery/osquery/blob/master/specs/users.table
- https://github.com/osquery/osquery/blob/master/specs/groups.table

