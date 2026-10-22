<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Configuration transformer usage

The transformer separates discovery, rendering, and parent-configuration
mutation. It accepts aggregate detector JSON, applies versioned YAML transform
definitions, renders approved Jinja templates, and writes a checksummed JSON
manifest. The separate injection command verifies those checksums before it
adds literal include paths to a parent configuration.

For normal use, pass the external `mappings` catalogue and an agent type. The
manual `--definition` workflow remains available for individual transforms.
To create a new mapping, including plugin defaults and Fluent Bit processors,
follow the beginner-oriented [mapping authoring guide](mapping_authoring_guide.md).

## Install in the component virtual environment

From `transformers/config-template-transformer`:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

The environment belongs only to this component. Runtime and development
dependencies are declared in `pyproject.toml`.

## Render the Fluent Bit example

Automatic Fluent Bit 5 mapping selection:

```powershell
.\.venv\Scripts\obs-config-transformer.exe render `
  --detector-results examples/detector_results.json `
  --mapping-root mappings `
  --target-tool fluent-bit `
  --output-root build `
  --manifest-output build/orchestration.json `
  --target-version 5.0.0
```

The selector chooses, for each detected product, the mapping with the highest
`minimum_version` that does not exceed `--target-version`. Fluent Bit 4.x uses
the 4.x templates; Fluent Bit 5.x uses the 5.x templates. PostgreSQL's 4.x
mapping starts at 4.0.4 because Lua processor support begins there.

The equivalent manual-definition example is:

```powershell
.\.venv\Scripts\obs-config-transformer.exe render `
  --detector-results examples/detector_results.json `
  --definition examples/transforms/nginx_1_logs.yaml `
  --output-root build `
  --manifest-output build/orchestration.json `
  --target-version 4.2.0
```

This writes `build/generated/nginx_1.inputs.yaml` and
`build/orchestration.json`. The manifest identifies the generator, target,
detector and transform versions; the template name, API version, version and
digest; the artifact digest; and the literal include instruction.

Stable empty fragments are generated if a detector is absent, not detected,
or contains errors. This prevents a parent include from retaining stale input
plugins.

## Render OpenTelemetry Collector Contrib

The maintained NGINX mapping has a Collector Contrib 0.163.0 minimum, which was
the latest release when this mapping was authored:

```powershell
.\.venv\Scripts\obs-config-transformer.exe render `
  --detector-results examples/detector_results.json `
  --mapping-root mappings `
  --target-tool otelcol-contrib `
  --output-root build `
  --manifest-output build/orchestration.json `
  --target-version 0.163.0
```

The generated configuration uses `filelog` for NGINX logs and the `nginx`
receiver for metrics. Collector composition uses repeated `--config` arguments;
the generic `inject` command therefore does not rewrite a Collector parent:

```powershell
otelcol-contrib --config base.yaml `
  --config build/generated/otelcol-contrib/nginx.yaml
```

## Inject includes into a parent

```powershell
.\.venv\Scripts\obs-config-transformer.exe inject `
  --manifest build/orchestration.json `
  --artifact-root build `
  --parent-config examples/fluent_bit_parent.yaml `
  --output build/fluent-bit.yaml
```

The injected Fluent Bit YAML uses its top-level `includes` list. Existing
entries and comments are retained, and duplicate paths are not added.

Validate the assembled result with Fluent Bit 4.2 or newer:

```powershell
fluent-bit --config build/fluent-bit.yaml --dry-run
```

The optional system test uses the official container image when it is already
available locally:

```powershell
docker pull fluent/fluent-bit:4.2
.\.venv\Scripts\python.exe -m pytest -q -s -m system
```

The include path is interpreted relative to the parent configuration by
Fluent Bit. Keep the generated directory beside the assembled parent, or use
an include path appropriate for the final deployment layout.

## Generate semantic payload configuration

After `render`, optionally generate parsing and OpenTelemetry semantic payload
configuration from the per-plugin provenance records:

```powershell
.\.venv\Scripts\obs-config-transformer.exe semantic-map `
  --manifest build/orchestration.json `
  --detector-results examples/detector_results.json `
  --mapping-root semantic-mappings `
  --output-root build `
  --semantic-manifest-output build/semantic-manifest.json
```

Use repeated `--mapping` arguments instead of `--mapping-root` when a custom
NGINX format or PostgreSQL logging configuration needs an explicitly selected
mapping. The generated semantic configuration replaces the source-only inputs;
loading both would collect the same log files twice. See the repository
[semantic payload mapping guide](../../../docs/semantic_payload_mapping.md)
for the full contracts, mappings, agent behavior, and extension workflow.

## Define another mapping or transform

Each transform definition declares:

- a versioned definition identity;
- detector and target version constraints;
- an artifact path and literal deployment include path;
- Jinja template version and context API version;
- the template metadata sidecar that declares supported capabilities, signals,
  observability tool, and tool-version range;
- RFC 9535 JSONPath rules that select detector results and emit normalized
  plugin objects.

Definitions can be repeated with `--definition`. One manifest intentionally
targets one tool, while each generated artifact stays independent.

The transform's template path, version, context API, and target are checked
against the independently validated sidecar before rendering. The requested
`--target-version` must satisfy both the transform and template ranges. See the
[template metadata contract](template_metadata.md) for the schema, field
semantics, versioning policy, compatibility checks, and extension workflow.

For a reusable agent mapping, add a JSON resource below `mappings/<agent>/`
instead. Mapping resources support static `values`, an optional `path_from`,
and `fields_from` entries for copying detector fields such as endpoint host and
port. Nested structures in `values`, including Fluent Bit `processors`, are
preserved by the generic templates. See the [mapping authoring guide](mapping_authoring_guide.md)
for the complete workflow and [agent mappings](agent_mappings.md) for the
resource contract.

## Add another observability tool

The selection, JSONPath, versioning, sandboxing, atomic-write, and manifest
logic is target-neutral. To support another tool from
`universal-obs-agent-installer/spec.md`, implement the `TargetAdapter` contract
in `adapters.py` with:

- a stable tool name and configuration media type;
- structural validation and serialization of rendered fragments;
- the target's parent composition mechanism.

This extension point covers Fluentd includes, Vector configuration composition,
OpenTelemetry Collector configuration, Telegraf includes, Elastic Agent policy
fragments, and Filebeat configuration without changing detector selection or
the JSON orchestration contract. A target-specific Jinja template and transform
definition provide the target syntax and normalized plugin properties.

## Safety and failure behavior

Jinja runs in an immutable sandbox with strict undefined variables. Definitions
and manifests are JSON Schema validated; paths cannot escape their configured
roots; detector and target versions must satisfy their declared constraints;
render size and plugin counts are bounded; artifacts are written atomically;
and injection refuses missing or modified artifacts. Logging defaults to DEBUG,
and expected errors return a non-zero status without a traceback.
