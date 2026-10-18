<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Configuration template transformer

This standalone Python application turns validated osquery detector results
into versioned observability-tool configuration fragments. Agent-specific JSON
mappings automatically select the newest compatible template floor for Fluent
Bit or OpenTelemetry Collector Contrib. The transformer renders sandboxed
Jinja, writes a JSON orchestration manifest, and can inject Fluent Bit's
literal include paths into a broader YAML configuration.

Every Jinja template has validated YAML metadata declaring its semantic
version, context API version, capabilities, observability signals, target tool,
and supported tool-version range. See the
[`template_metadata.md`](docs/template_metadata.md) contract for the complete
format and compatibility rules.

The external [`mappings`](mappings) hierarchy contains the maintained NGINX
and PostgreSQL mappings. See the [`agent_mappings.md`](docs/agent_mappings.md)
contract for catalogue layout, version selection, and the supplied templates.
The beginner-oriented [`mapping_authoring_guide.md`](docs/mapping_authoring_guide.md)
explains agent plugins, defaults, JSONPath rules, basic Jinja syntax, Fluent Bit
plugin parameters, processors, and configuration injection.
The [`execution_flow.md`](docs/execution_flow.md) architecture page includes
Mermaid diagrams for the complete detector-to-agent workflow, the detailed
transformer execution path, and the relationships between authored, generated,
and deployment-owned configuration files.
The repository-level
[`observability_configuration_roadmap.md`](../../docs/roadmap/observability_configuration_roadmap.md)
defines the planned log-source, database, agent, regression, and version-audit
workstreams.

The selection and rendering core is tool-neutral. Target-specific validation,
serialization, and include behavior live behind a `TargetAdapter` contract so
future adapters can cover Fluentd, Vector, Telegraf, Elastic Agent, and Elastic
Beats without changing mapping definitions or detector selection behavior.

## Environment

Create and populate the component-local environment from this directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

The CLI is installed as `obs-config-transformer`. See
[`docs/usage.md`](docs/usage.md) for the rendering, JSON handoff, injection,
and Fluent Bit validation workflow.

