<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Configuration template transformer

This standalone Python application turns validated osquery detector results
into versioned observability-tool configuration fragments. The initial adapter
renders Fluent Bit YAML input plugins with sandboxed Jinja, writes a JSON
orchestration manifest, and can inject the manifest's literal include paths
into a broader Fluent Bit YAML configuration.

Every Jinja template has validated YAML metadata declaring its semantic
version, context API version, capabilities, observability signals, target tool,
and supported tool-version range. See the
[`template_metadata.md`](docs/template_metadata.md) contract for the complete
format and compatibility rules.

The selection and rendering core is tool-neutral. Target-specific validation,
serialization, and include behavior live behind a `TargetAdapter` contract so
future adapters can cover Fluentd, Vector, OpenTelemetry Collector, Telegraf,
Elastic Agent, and Elastic Beats without changing transform definitions or
detector selection behavior.

## Environment

Create and populate the component-local environment from this directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

The CLI is installed as `obs-config-transformer`. See
[`docs/usage.md`](docs/usage.md) for the rendering, JSON handoff, injection,
and Fluent Bit validation workflow.

