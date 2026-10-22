<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# NGINX and PostgreSQL regression container

This regression image starts real NGINX and PostgreSQL 17 deployments in one
container, runs the `nginx_1` and `postgresql_17` osquery detectors, renders
source configurations for Fluent Bit and OpenTelemetry Collector Contrib, and
runs the optional semantic payload stage for both agents. It verifies
discovery, per-plugin provenance, transformation, semantic mapping, manifests,
fragment generation, and Fluent Bit parent composition.

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
./tests/regression/run_regression_container.sh
```

Both launchers build `opamp-nginx-postgresql-regression:test`, run it without
published ports, and retain output below `build/regression-artifacts` by
default. Pass a different output directory as the first argument.

To exercise the same flow through the opt-in Python regression test:

```powershell
$env:RUN_CONTAINER_REGRESSION = "1"
py -3 -m unittest tests.test_regression_container
```

## Produced artifacts

- `detector-results.json`: aggregate osquery results for both deployments;
- `orchestration-fluent-bit.json` and `orchestration-otelcol.json`: versioned
  source-transform manifests with per-plugin detector links;
- `semantic-manifest-fluent-bit.json` and `semantic-manifest-otelcol.json`:
  selected semantic mappings and checksums;
- `generated/fluent-bit/`: source fragments plus final semantic YAML and Lua;
- `generated/otelcol-contrib/`: source fragments plus final semantic YAML;
- `otelcol-semantic-parent.yaml`: deployment-owned debug exporter used to
  validate the generated Collector fragment;
- `fluent-bit-source.yaml`: parent containing the source-only includes;
- `fluent-bit-semantic.yaml`: demonstration parent containing the final
  semantic configuration;
- `nginx-service.log` and `postgresql-service.log`: deployment diagnostics;
- `regression-verification.json`: success report written only after validation.

`verify_artifacts.py` requires both detectors to match without errors, requires
log-location evidence, checks source and semantic manifests and SHA-256
digests, validates every plugin detector link, requires NGINX access/error and
PostgreSQL mappings for both agents, and verifies the assembled source parent.
Any failed check makes the container exit non-zero.

PostgreSQL trust authentication is enabled only inside this disposable,
unpublished regression container. The image and generated configuration are
not production deployment examples.
