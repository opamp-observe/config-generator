<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Linux system capabilities detector logic

Detector: `linux_system_1` version `1.0.0`  
Pack: [Linux](packs/linux.conf)

## Separation from basic host inventory

This detector is Linux-only and does not duplicate the portable host identity,
deployment-environment, or user-role contract in `host_inventory_1`. Discovery
matches a Linux `os_version` row and then publishes Linux kernel, network, and
logging capabilities as a separate result.

## Network inventory

- `network_interfaces` returns every visible interface, its link and traffic
  counters, and every assigned IPv4 or IPv6 address. Interfaces without an
  address remain in the result as `address_family: unassigned`.
- `network_protocols` reports all network and transport protocols observed in
  interface addresses, routes, or listening sockets. It is an observed-support
  inventory, not a claim that every protocol compiled into the kernel is
  enabled or externally reachable.
- `network_routes` returns the complete active route table visible to osquery,
  including address family and default-route classification.
- `listening_sockets` returns IPv4, IPv6, and Unix listeners with their network
  namespace and owning process when that process is visible.
- `dns_resolvers` returns nameservers, search entries, sort-list entries, and
  resolver options.

Network results are scoped to the namespace in which osquery runs. A container
or sidecar can therefore expose only its attached interfaces, routes, and
sockets unless it shares the target network namespace.

## Kernel log access

`kernel_log_access` checks the visible direct devices, conventional kernel log
files, and system journal directories. It compares their POSIX ownership and
mode bits with osquery's effective user and supplementary groups, returning an
`access_available` string plus source counts and paths.

`access_available` is `true` when at least one readable log file or journal
directory is visible, `false` when no source passes the mode check, and
`unknown` when only a mode-readable kernel device is visible. The latter also
sets `direct_device_probe_required: true` because opening `/dev/kmsg` or
`/proc/kmsg` can still require `CAP_SYSLOG` despite permissive-looking mode bits.

The assessment method is explicitly `posix_mode_estimate`: it does not read or
consume kernel messages. Linux capabilities such as `CAP_SYSLOG`, ACLs,
security modules, and container device policy can still allow or deny access
after mode checks. Consumers that require proof should perform a non-consuming
deployment-level read probe under the final agent identity.

## Syslog availability

`syslog_availability` reports separate rows for systemd-journald, rsyslog,
syslog-ng, and traditional syslogd. A provider is available when its process,
local logging endpoint, or durable log store is visible, according to the
provider-specific evidence. This records collection availability without
enabling osquery's event subscriber or changing host logging configuration.

## Documentation used

- https://github.com/osquery/osquery/blob/master/specs/kernel_info.table
- https://github.com/osquery/osquery/blob/master/specs/interface_addresses.table
- https://github.com/osquery/osquery/blob/master/specs/interface_details.table
- https://github.com/osquery/osquery/blob/master/specs/routes.table
- https://github.com/osquery/osquery/blob/master/specs/listening_ports.table
- https://github.com/osquery/osquery/blob/master/specs/posix/dns_resolvers.table
- https://github.com/osquery/osquery/blob/master/specs/linux/syslog_events.table
