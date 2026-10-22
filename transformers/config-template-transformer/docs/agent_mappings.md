<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Agent mapping catalogue

Agent mappings connect detector output contracts to observability-agent
templates without embedding product choices in Python. They live below the
component's `mappings/` directory, outside the packaged `src/` tree, so an
operator can review, replace, or mount the catalogue independently.

Readers new to Fluent Bit plugins, mapping defaults, processors, or Jinja
should start with the [mapping authoring guide](mapping_authoring_guide.md).
This page is the concise resource and selection contract.

## Layout and selection

The maintained hierarchy groups mappings first by stable agent type and then
by compatibility floor:

```text
mappings/
  fluent-bit/
    4.0/
      nginx_1.json
    4.0.4/
      postgresql_17.json
      postgresql_18.json
      postgresql_19.json
    5.0/
      nginx_1.json
      postgresql_17.json
      postgresql_18.json
      postgresql_19.json
  otelcol-contrib/
    0.163/
      nginx_1.json
```

Directory names are organizational; compatibility comes from each document's
`spec.agent.type` and `spec.agent.minimum_version`. For every detector in the
input, the selector filters to the requested agent and floors less than or
equal to the requested version, then chooses the single highest floor. Equal
best floors are rejected as ambiguous. PEP 440 version parsing is used for
ordering and comparison.

Mappings are selected only for detector names present in the aggregate input.
Once selected, the normal detector-version, template-metadata, rendering,
artifact, and manifest checks still apply.

## Resource format

Each JSON file is validated as an `ObservabilityAgentMapping`:

```json
{
  "_comment": "Copyright 2026 opamp.info; licensed under the Apache License, Version 2.0.",
  "api_version": "opamp.info/v1alpha1",
  "kind": "ObservabilityAgentMapping",
  "metadata": {"name": "fluent_bit_5_nginx_1", "version": "1.0.0"},
  "spec": {
    "detector": {"name": "nginx_1", "version_constraint": ">=1,<2"},
    "agent": {"type": "fluent-bit", "minimum_version": "5.0.0"},
    "output": {
      "path": "generated/fluent-bit/nginx.inputs.yaml",
      "include_path": "generated/fluent-bit/nginx.inputs.yaml"
    },
    "render": {
      "engine": "jinja2",
      "template": "fluent_bit_5_pipeline.yaml.j2",
      "metadata_file": "fluent_bit_5_pipeline.metadata.yaml",
      "version": "1.0.0",
      "template_api_version": "1.0",
      "context_name": "plugins"
    },
    "rules": [{
      "name": "nginx_logs",
      "for_each": "$.queries.log_locations[*]",
      "path_from": "$.path_or_destination",
      "values": {"name": "tail", "tag": "nginx.logs"}
    }]
  }
}
```

`for_each` selects source rows. `values` supplies fixed template properties.
An optional `path_from` can emit one plugin per non-empty path selected from a
row. Optional `fields_from` maps output property names to JSONPath selectors
evaluated against that row, with exactly one match required for each field. A
missing dynamic field skips the row; multiple matches are rejected because
their intended pairing would be ambiguous.
Optional `path_match` restricts selected paths with a regular expression, which
is useful when evidence also contains explanatory candidates. Optional
`source_format` is copied to per-plugin provenance for the semantic mapping
stage; omitted values become `unstructured`.

## How mapping rules are established

A mapping rule is the explicit contract between one detector query and one
target-agent plugin or receiver. It is not inferred from matching field names,
and template metadata does not create it. An author establishes a rule from
these three inputs:

1. **Detector output contract:** identify the detector, query, and exact column
   aliases emitted by its osquery pack. The detector manifest identifies the
   required queries, while the detector schema and pack define the available
   result structure and row fields.
2. **Agent plugin contract:** identify the target plugin or receiver and the
   attributes accepted by the intended agent version. This determines the
   normalized output field names and any fixed values.
3. **Template context contract:** confirm that the selected Jinja template
   consumes those normalized fields and that its metadata advertises the
   required capability and compatible agent range.

The rule is then written and reviewed using this procedure:

1. Set `for_each` to the detector query rows that represent one possible plugin
   instance.
2. Put constant agent settings in `values`, including the plugin `name` or
   receiver `kind`.
3. Use `fields_from` for detector values that should become named agent
   attributes, such as a detected endpoint host or port.
4. Use `path_from` when a selected detector value should become the normalized
   `path` attribute. The template can then handle path-specific formatting.
5. Set `spec.agent.minimum_version` to the first agent release supporting every
   feature used by the rule and template.
6. Add an integration test containing representative detector rows and assert
   the final rendered agent configuration, not only the intermediate plugin
   object.

The source paths and target attributes must therefore be deliberate. Adding a
new detector column does not automatically expose it to a template, and adding
a template property does not automatically populate it from detector output.

## Rule fields and evaluation scope

| Field | Evaluation scope | Result |
| --- | --- | --- |
| `name` | Not evaluated | Stable rule identity used in diagnostics. |
| `for_each` | The complete selected detector entry | Produces zero or more source rows, normally from `$.queries.<query_name>[*]`. |
| `values` | Not evaluated | Starts each normalized plugin object with fixed JSON-compatible values. |
| `fields_from` | Each row returned by `for_each` | Copies one scalar match into each named output attribute. A missing match skips that row; multiple matches are an error. |
| `path_from` | Each row returned by `for_each` | Emits a plugin for every non-empty string match, placing the trimmed value in `path`. It is optional for plugins without a file path. |
| `path_match` | Each non-empty `path_from` value | Emits only paths matching the regular expression. |
| `source_format` | Emitted plugin provenance | Selects an optional semantic payload mapping without becoming an agent plugin property. |

Values are applied in this order:

```text
values → fields_from → path_from as path
```

A later stage replaces an earlier value with the same output name. The final
plugin objects are canonically deduplicated, and the configured plugin-count
limit is enforced before rendering.

## Worked NGINX mapping

Given this row from `nginx_1.queries.metrics_outputs`:

```json
{
  "endpoint_host": "127.0.0.1",
  "port": "80",
  "endpoint_path": "/configured-location"
}
```

the Fluent Bit rule is:

```json
{
  "name": "nginx_metrics",
  "for_each": "$.queries.metrics_outputs[*]",
  "fields_from": {
    "host": "$.endpoint_host",
    "port": "$.port"
  },
  "values": {
    "name": "nginx_metrics",
    "tag": "nginx.metrics",
    "status_url": "/status",
    "nginx_plus": false,
    "interval_sec": 10
  }
}
```

`for_each` is evaluated against the complete `nginx_1` detector entry. Each
`fields_from` selector is then evaluated against one metrics row. The rule
produces this normalized object:

```json
{
  "name": "nginx_metrics",
  "tag": "nginx.metrics",
  "status_url": "/status",
  "nginx_plus": false,
  "interval_sec": 10,
  "host": "127.0.0.1",
  "port": "80"
}
```

The Fluent Bit pipeline template iterates over that object and renders its
properties beneath one `pipeline.inputs` item. The mapping deliberately uses a
fixed `/status` value because the detector reports a candidate endpoint rather
than confirming an active NGINX status location; deployments must expose or
adjust that location.

The NGINX log rule follows the same process, but uses
`path_from: $.path_or_destination`. This creates a `tail` input whose `path`
comes from the detector row while `name`, `tag`, and `read_from_head` come from
`values`.

## Worked PostgreSQL mapping

For PostgreSQL, `for_each` selects `$.queries.log_locations[*]` and
`path_from` reads `$.log_directory_candidate`. The rule adds
`path_suffix: "/*.log"`; the Fluent Bit template combines the detected
directory and suffix into the rendered `path` and does not emit `path_suffix`
as a plugin property.

The nested `processors` value is static target configuration. It declares the
Lua processor name, deployment-owned script path, and callback. No Lua values
are inferred from osquery. The minimum Fluent Bit 4.x version is consequently
4.0.4, the first compatible processor version used by this mapping.

## Source-of-truth checklist

When adding or changing a rule, review all of these together:

- detector manifest under `detectors/<product>/<version>/detector.json`;
- detector pack query aliases under its `packs/` directory;
- detector result schema under `schemas/detectors/`;
- agent mapping under `mappings/<agent>/<minimum_version>/`;
- Jinja template and metadata sidecar under
  `src/config_template_transformer/templates/`;
- target adapter structural validation; and
- unit or integration tests asserting the rendered configuration.

If a detector alias, normalized field, plugin attribute, minimum agent version,
or template behavior changes, update the corresponding mapping, tests, and
documentation in the same change.

## Maintained behavior

The Fluent Bit NGINX mappings generate `tail` inputs for detected log files and
an `nginx_metrics` input for each detected endpoint. The PostgreSQL 17, 18, and
19 mappings generate `tail` inputs for each detected log directory. They also
include a Lua processor placeholder that expects this deployment-owned file
and callback:

```text
/etc/fluent-bit/scripts/postgresql.lua
process_postgresql_record
```

The transformer does not generate or install the Lua script. A deployment must
provide it or remove the placeholder before starting Fluent Bit.

The OpenTelemetry Collector Contrib NGINX mapping has a 0.163.0 minimum. It
generates `filelog` and `nginx` receivers and connects them to logs and metrics
pipelines. It uses the Contrib distribution because both receivers are Contrib
components.

The relevant upstream references are the
[Fluent Bit NGINX metrics input](https://docs.fluentbit.io/manual/data-pipeline/inputs/nginx),
[Fluent Bit Lua processor](https://docs.fluentbit.io/manual/data-pipeline/processors/lua),
[Collector Contrib NGINX receiver](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/v0.163.0/receiver/nginxreceiver),
and [Collector Contrib 0.163.0 release](https://github.com/open-telemetry/opentelemetry-collector-contrib/releases/tag/v0.163.0).
