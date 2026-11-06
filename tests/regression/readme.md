<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# NGINX and PostgreSQL regression container

This regression image starts real NGINX and PostgreSQL 17 deployments in one
container, runs the `nginx_1` and `postgresql_17` osquery detectors, and passes
their aggregate JSON through both Fluent Bit transforms. It is intentionally
not a complete observability deployment: it verifies discovery, transformation,
manifest generation, fragment generation, and parent include composition.

The image is based on the official PostgreSQL 17 Bookworm image. It installs
the Debian NGINX package and copies the self-contained `osqueryd` binary from
the osquery Debian image. Both products therefore share the PID, filesystem,
and network namespaces inspected by osquery.

## Run

From the repository root on PowerShell:

```powershell
.\tests\regression\run_regression.ps1
```

On a POSIX shell:

```sh
bash ./tests/regression/run_regression_container.sh
```

Both launchers build `opamp-nginx-postgresql-regression:test`, run it without
published ports, and retain output below `build/regression-artifacts` by
default. Pass a different output directory as the first argument.

The launchers grant `SYS_PTRACE` and use the unconfined seccomp profile so the
root osquery process can inspect the PostgreSQL process running as its
unprivileged operating-system user. These permissions apply only to the
short-lived, unpublished regression container.

To exercise the same flow through the opt-in Python regression test:

```powershell
$env:RUN_CONTAINER_REGRESSION = "1"
py -3 -m unittest tests.test_regression_container
```

## Produced artifacts

- `detector-results.json`: aggregate osquery results for both deployments;
- `orchestration.json`: versioned transformer manifest with checksums and
  template support metadata;
- `generated/nginx_1.inputs.yaml`: generated NGINX Fluent Bit inputs;
- `generated/postgresql_17.inputs.yaml`: generated PostgreSQL Fluent Bit input;
- `fluent-bit.yaml`: parent configuration containing both literal includes;
- `nginx-service.log` and `postgresql-service.log`: deployment diagnostics;
- `regression-verification.json`: success report written only after validation.

`verify_artifacts.py` requires both detectors to match without errors, requires
log-location evidence, checks both manifest records and SHA-256 digests,
requires non-empty `pipeline.inputs` fragments, and verifies that the assembled
parent includes both fragments. Any failed check makes the container exit
non-zero.

PostgreSQL trust authentication is enabled only inside this disposable,
unpublished regression container. The image and generated configuration are
not production deployment examples.
