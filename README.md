<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Osquery product detectors

This repository contains separate, versioned osquery detectors for:

- NGINX and Apache HTTP Server
- Python, Node.js, and Java applications
- SQLite databases and their embedding processes
- Oracle WebLogic Server 12.2.1.4 and 14.1.1
- Oracle Database 19c, 21c, and 26ai
- PostgreSQL 17, 18, and the PostgreSQL 19 development line
- Cross-platform host identity and deployment-environment inventory

Every setup lives below `detectors/<product>/<version>/` and contains a
self-identifying manifest, Linux and Windows osquery packs, and product-specific
documentation. PostgreSQL 19 is deliberately marked `development`; as of
2026-10-14 the PostgreSQL project and official image publish 19 beta builds, not
a production release.

## Run all detectors

Linux or a Linux container:

```sh
./scripts/run_detectors.sh
```

PowerShell:

```powershell
.\scripts\run_detectors.ps1
```

Command Prompt:

```batch
scripts\run_detectors.cmd
```

Use `--detector weblogic_14` (or the PowerShell `-Detector weblogic_14`
parameter) to select one detector. Use `--include-undetected` only for
diagnostics: it runs detail queries even when exact version evidence is absent.

The aggregate `detector-results.json` records the detector name and detector
version, product version, exact discovery evidence, runtime mapping, candidate
configuration-file locations, log locations, metrics outputs, service state,
unique identifiers, listening ports, and detector errors.
Configuration files and logs are emitted as separate `configuration_files` and
`log_locations` query results.
The aggregate output can be validated with
[`schemas/detector_results.schema.json`](schemas/detector_results.schema.json),
which references a dedicated result schema for every detector. See the
[schema guide](schemas/README.md) for the contract and validation command.

Run `--detector host_inventory_1` to publish hostname, interface addresses, OS
version, possible container/VM evidence, and visible user roles independently
of the product detectors.

The [detector catalogue](detectors/catalogue.md) lists supported product
versions and operating systems. The [detector logic index](docs/osquery_logic.md)
links to the detailed logic document colocated with every detector.
The [Fluent Bit transformation findings](docs/fluent_bit_transform_findings.md)
describe how validated detector results can be combined with declarative
mappings and deployment policy to generate Fluent Bit YAML.

## Generate observability configuration fragments

The standalone [configuration template transformer](transformers/config-template-transformer/readme.md)
uses versioned YAML definitions, RFC 9535 JSONPath selection, and sandboxed
Jinja templates to convert detector results into configuration fragments. Its
JSON orchestration manifest records template, transform, detector, target, and
artifact versions and checksums before includes are injected into a parent
configuration.
Each template also has a validated
[metadata sidecar](transformers/config-template-transformer/docs/template_metadata.md)
that declares its capabilities, signals, target observability tool, and
supported tool-version range.

Fluent Bit YAML is the first implemented target and is covered by unit tests
and a native Fluent Bit 4.2 dry-run system test. The target-adapter contract is
designed for the other agents listed in
`universal-obs-agent-installer/spec.md`: Fluentd, Vector, OpenTelemetry
Collector, Telegraf, Elastic Agent, and Filebeat.

## Validate

```powershell
.\tests\run_validation.ps1
```

The validation suite checks manifests and pack structure, calls
`osqueryi --config_check` for every pack, and executes every SQL statement for
the current platform. See [container testing](docs/container_testing.md) for
Linux and product-image testing.

