<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Retired
-------------------------------------------------
This branch is only retained as it illustrates the complexity of an idea, and supports a blog. This branch must NEVER be merged intro main or be updated
-------------------------------------------------

# Osquery product detectors

This repository contains separate, versioned osquery detectors for:

- NGINX and Apache HTTP Server
- Python, Node.js, and Java applications
- SQLite databases and their embedding processes
- Oracle WebLogic Server 12.2.1.4 and 14.1.1
- Oracle Database 19c, 21c, and 26ai
- PostgreSQL 17, 18, and the PostgreSQL 19 development line
- Cross-platform host identity and deployment-environment inventory
- Linux network, kernel-log access, and syslog capability inventory

Every setup lives below `detectors/<product>/<version>/` and contains a
self-identifying manifest, osquery packs for its declared operating systems,
and product-specific documentation. PostgreSQL 19 is deliberately marked
`development`; as of 2026-10-14 the PostgreSQL project and official image
publish 19 beta builds, not a production release.

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

Run `--detector linux_system_1` for the separate Linux-specific inventory of
interfaces, observed network protocols, routes, listeners, DNS resolvers,
kernel details, kernel-log access, and syslog availability.

The [detector catalogue](detectors/catalogue.md) lists supported product
versions and operating systems. The [detector logic index](docs/osquery_logic.md)
links to the detailed logic document colocated with every detector.
The [Fluent Bit transformation findings](docs/fluent_bit_transform_findings.md)
describe how validated detector results can be combined with declarative
mappings and deployment policy to generate Fluent Bit YAML.

## Generate observability configuration fragments

The standalone [configuration template transformer](transformers/config-template-transformer/readme.md)
uses agent-specific [JSON mapping catalogues](transformers/config-template-transformer/docs/agent_mappings.md),
RFC 9535 JSONPath selection, and sandboxed Jinja templates to convert detector
results into configuration fragments. It selects the highest compatible
minimum agent version and records template, mapping, detector, target, and
artifact versions and checksums in a JSON orchestration manifest.
Each template also has a validated
[metadata sidecar](transformers/config-template-transformer/docs/template_metadata.md)
that declares its capabilities, signals, target observability tool, and
supported tool-version range.
See the [execution-flow diagrams](transformers/config-template-transformer/docs/execution_flow.md)
for the complete detector-to-agent workflow, detailed transformer logic, and
configuration-file relationships.
The [mapping authoring guide](transformers/config-template-transformer/docs/mapping_authoring_guide.md)
is the beginner-focused walkthrough for plugin parameters, defaults, JSONPath,
Jinja templates, and Fluent Bit processors.
The [semantic payload mapping guide](docs/semantic_payload_mapping.md) documents
the optional post-transform stage, per-plugin detector provenance, maintained
NGINX/PostgreSQL mappings, manual overrides, and the Fluent Bit and Collector
adapter implementations.
The [observability configuration roadmap](docs/roadmap/observability_configuration_roadmap.md)
tracks normalized log discovery and deduplication, database queries, MongoDB,
additional agents, regression evidence, and mapping-version audits.
The [adaptive dashboard generation proposal](docs/roadmap/adaptive_dashboard_generation.md)
describes how bounded agents can turn transformer provenance and telemetry
contracts into validated Grafana or Kibana dashboard bundles for Loki,
Prometheus, ClickHouse, and Elasticsearch backends.

Fluent Bit 4.x/5+ YAML and OpenTelemetry Collector Contrib 0.163+ YAML are
implemented targets. The maintained catalogue maps NGINX logs and metrics to
both agents and PostgreSQL logs to both Fluent Bit tail inputs and Collector
filelog receivers. The optional semantic stage generates source parsing and
OpenTelemetry-shaped payload configuration. The target-adapter contracts are designed for the other agents
listed in `universal-obs-agent-installer/spec.md`: Fluentd, Vector, Telegraf,
Elastic Agent, and Filebeat.

## Validate

```powershell
.\tests\run_validation.ps1
```

The validation suite checks manifests and pack structure, calls
`osqueryi --config_check` for every pack, and executes every SQL statement for
the current platform. See [container testing](docs/container_testing.md) for
Linux and product-image testing.

