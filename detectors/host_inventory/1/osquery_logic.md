<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Host inventory detector logic

Detector: `host_inventory_1` version `1.0.0`  
Packs: [Linux](packs/linux.conf) and [Windows](packs/windows.conf)

## Discovery

The detector is intentionally universal. It matches when `system_info` returns
the current host record, then publishes the inventory queries below. Unlike a
product detector, it does not require version-specific process evidence.

## JSON query results

- `host_identity` returns hostname, computer/local hostname, host UUID, OS name
  and version components, platform, architecture, hardware vendor/model, and
  the osquery version used to collect the data.
- `network_ips` returns every address from `interface_addresses`, including its
  interface, mask, type, address family, and loopback status. Loopback,
  link-local, virtual-adapter, and container-interface addresses are retained
  so consumers can apply their own filtering.
- `deployment_environment` returns `possible_container`,
  `possible_virtual_machine`, or `physical_or_unknown`, together with the
  evidence used and `classification_method: heuristic`.
- `execution_identity` returns the user and privilege category visible to the
  detector. On Linux this is the effective osquery UID and primary group. On
  Windows this is an active session identity because osquery's Windows process
  table does not expose a usable process-token username; the row therefore sets
  `execution_identity_confirmed` to `false`.
- `user_roles` returns local group memberships for the reported identity.

## Container and virtual-machine inference

Linux container evidence includes `/.dockerenv`, `/run/.containerenv`, an
overlay root filesystem, and container-related PID 1 cgroup text. Windows
container evidence uses the system container registry subtree when visible.

Virtual-machine evidence is inferred from hardware vendor/model strings for
common VMware, VirtualBox, QEMU/KVM, Xen, Hyper-V/cloud, and OpenStack guests.
Container evidence takes precedence over VM evidence because a container can
itself run on a virtual-machine host.

This is deliberately described as a possibility, not proof. Restricted
namespaces, sanitized firmware strings, Windows process isolation, and cloud
hardware abstraction can hide evidence. `physical_or_unknown` means no known
marker was observed.

## Identity limitations

The Linux identity is the account that executes the short-lived `osqueryi`
process spawned by the runner. In a sidecar this is normally the sidecar user,
not the application account in the target container.

On Windows, active session identity and local group membership do not establish
the service account or elevation state of the osquery process. Consumers must
honor `identity_source` and `execution_identity_confirmed` instead of treating
the inferred session user as an exact execution identity.

## Documentation used

- https://github.com/osquery/osquery/blob/master/specs/system_info.table
- https://github.com/osquery/osquery/blob/master/specs/os_version.table
- https://github.com/osquery/osquery/blob/master/specs/interface_addresses.table
- https://github.com/osquery/osquery/blob/master/specs/processes.table
- https://github.com/osquery/osquery/blob/master/specs/logged_in_users.table
- https://github.com/osquery/osquery/blob/master/specs/users.table
- https://github.com/osquery/osquery/blob/master/specs/groups.table
- https://github.com/osquery/osquery/blob/master/specs/utility/osquery_info.table

