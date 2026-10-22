<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Mapping authoring guide

This guide assumes only basic familiarity with JSON and YAML. You do not need
to know Jinja to add another detector-to-plugin mapping when an existing
generic template already supports the target agent.

## The basic idea

An osquery detector reports facts. It does not produce Fluent Bit or
OpenTelemetry Collector configuration. A mapping translates selected detector
facts into a neutral list of plugin objects. A Jinja template then turns that
list into the YAML structure required by one observability agent.

For example, a detector might report:

```json
{
  "log_directory_candidate": "/var/lib/postgresql/17/log"
}
```

The mapping can turn it into this intermediate plugin object:

```json
{
  "name": "tail",
  "path": "/var/lib/postgresql/17/log",
  "path_suffix": "/*.log",
  "tag": "postgresql.17.logs",
  "read_from_head": true
}
```

The Fluent Bit template combines `path` and `path_suffix`, then produces:

```yaml
pipeline:
  inputs:
    - name: tail
      path: /var/lib/postgresql/17/log/*.log
      tag: postgresql.17.logs
      read_from_head: true
```

The important separation is:

| Part | Responsibility |
| --- | --- |
| Detector | Discovers facts and assigns stable query and column names. |
| Mapping JSON | Selects detector rows and names the plugin attributes to create. |
| Jinja template | Arranges normalized plugin objects into the agent's YAML structure. |
| Template metadata | Declares the template identity, compatible agent versions, signals, and capabilities. |
| Target adapter | Performs final structural validation and deterministic serialization. |
| Orchestration manifest | Records generated artifacts, versions, hashes, and composition instructions. |

See the
[configuration file relationship diagram](execution_flow.md#configuration-file-relationships)
for the references and runtime flow between these files.

## Understand the target agent first

An observability agent loads one or more components. In Fluent Bit, an input
plugin gathers records or metrics. Examples include:

- `tail`, which follows files and produces log records;
- `nginx_metrics`, which polls an NGINX status endpoint; and
- processors nested beneath an input, which modify records immediately after
  that input produces them.

An OpenTelemetry Collector receiver has a similar collection role, but its
configuration is placed under `receivers` and then referenced from a
`service.pipelines` entry. That structural difference is why Fluent Bit and
Collector mappings use different templates.

Before writing a mapping, identify the exact target component, its parameter
names, supported data types, and the first agent version supporting every
feature you plan to use. Do not assume that an osquery column name is also a
valid plugin parameter.

## Files involved in a new mapping

For a Fluent Bit 5 mapping of `example_product_1`, the usual files are:

```text
detectors/example_product/1/detector.json
detectors/example_product/1/packs/linux.conf
schemas/detectors/example_product_1.schema.json
transformers/config-template-transformer/
  mappings/fluent-bit/5.0/example_product_1.json
  src/config_template_transformer/templates/
    fluent_bit_5_pipeline.yaml.j2
    fluent_bit_5_pipeline.metadata.yaml
  tests/test_agent_mappings.py
```

If the existing Fluent Bit pipeline template can express the desired input,
only the mapping and tests normally need to change. A new template is necessary
when the target YAML has a different top-level structure or needs rendering
logic that the existing template cannot express safely.

## Step 1: inspect representative detector output

Start with the actual aggregate detector result, not only the osquery SQL. A
selected detector entry has this general form:

```json
{
  "detector_name": "example_product_1",
  "detector_version": "1.0.0",
  "detected": true,
  "queries": {
    "log_locations": [
      {"path_or_destination": "/var/log/example/application.log"}
    ],
    "metrics_outputs": [
      {"endpoint_host": "127.0.0.1", "port": "8080"}
    ]
  },
  "errors": []
}
```

The names beneath `queries` come from the detector pack. A mapping should only
consume fields whose meaning is stable enough to be part of the detector's
output contract.

## Step 2: write down the desired agent YAML

Decide what the final configuration must look like before writing JSONPath.
For a Fluent Bit file input, that might be:

```yaml
pipeline:
  inputs:
    - name: tail
      path: /var/log/example/application.log
      tag: example.logs
      read_from_head: false
      refresh_interval: 10
      skip_long_lines: true
      mem_buf_limit: 10MB
```

This makes the translation explicit:

| Fluent Bit attribute | Source |
| --- | --- |
| `name` | Fixed mapping value: `tail`. |
| `path` | Detector field: `path_or_destination`. |
| `tag` | Fixed mapping value chosen for routing. |
| `read_from_head` | Mapping default. |
| `refresh_interval` | Mapping default. |
| `skip_long_lines` | Mapping default. |
| `mem_buf_limit` | Mapping default. |

## Step 3: choose the mapping location and version floor

Create the JSON file below:

```text
mappings/<agent_type>/<organizational_version>/<detector_name>.json
```

The directory names make the catalogue readable, but selection uses the values
inside the document:

```json
"agent": {
  "type": "fluent-bit",
  "minimum_version": "5.0.0"
}
```

Set `minimum_version` to the first version supporting the complete generated
configuration. If two mappings exist for the same detector and agent, the
transformer chooses the highest minimum version that does not exceed the
requested agent version.

## Step 4: define the resource and output

A reusable mapping starts with identity, compatibility, artifact, and template
information:

```json
{
  "_comment": "Copyright 2026 opamp.info; licensed under the Apache License, Version 2.0.",
  "api_version": "opamp.info/v1alpha1",
  "kind": "ObservabilityAgentMapping",
  "metadata": {
    "name": "fluent_bit_5_example_product_1",
    "version": "1.0.0"
  },
  "spec": {
    "detector": {
      "name": "example_product_1",
      "version_constraint": ">=1,<2"
    },
    "agent": {
      "type": "fluent-bit",
      "minimum_version": "5.0.0"
    },
    "output": {
      "path": "generated/fluent-bit/example.inputs.yaml",
      "include_path": "generated/fluent-bit/example.inputs.yaml"
    },
    "render": {
      "engine": "jinja2",
      "template": "fluent_bit_5_pipeline.yaml.j2",
      "metadata_file": "fluent_bit_5_pipeline.metadata.yaml",
      "version": "1.0.0",
      "template_api_version": "1.0",
      "context_name": "plugins"
    },
    "rules": []
  }
}
```

`output.path` is relative to the render command's `--output-root`.
`output.include_path` is the literal path placed in the manifest for later
composition into the parent Fluent Bit configuration.

## Step 5: define rules

Each rule creates zero or more normalized plugin objects. The four rule fields
have distinct jobs:

- `for_each` selects rows from the complete detector entry.
- `values` supplies fixed plugin attributes and defaults.
- `fields_from` copies named values from each selected row.
- `path_from` copies one or more non-empty string values into the special
  normalized `path` attribute.
- `path_match` rejects selected path values that are explanatory candidates
  rather than usable file paths.
- `source_format` supplies a stable hint for the optional semantic payload
  stage. Omit it for metrics, unknown formats, or other non-log inputs.

For the file-input example:

```json
"rules": [
  {
    "name": "example_logs",
    "for_each": "$.queries.log_locations[*]",
    "path_from": "$.path_or_destination",
    "values": {
      "name": "tail",
      "tag": "example.logs",
      "read_from_head": false,
      "refresh_interval": 10,
      "skip_long_lines": true,
      "mem_buf_limit": "10MB"
    }
  }
]
```

`for_each` is evaluated once against the complete detector entry.
`path_from` and every `fields_from` selector are evaluated relative to each row
returned by `for_each`.

For a plugin without a file path, omit `path_from` and copy the required
detector fields explicitly:

```json
{
  "name": "example_metrics",
  "for_each": "$.queries.metrics_outputs[*]",
  "fields_from": {
    "host": "$.endpoint_host",
    "port": "$.port"
  },
  "values": {
    "name": "example_metrics",
    "scrape_interval": "10s"
  }
}
```

The object keys on the left side of `fields_from` are target plugin attributes.
The JSONPath strings on the right side select detector fields.

### JSONPath mini-primer

Only a few JSONPath forms are needed for the maintained mappings:

| Expression | Meaning in this transformer |
| --- | --- |
| `$` | The value currently being searched. For `for_each`, this is the detector entry; for `fields_from` and `path_from`, this is one selected row. |
| `$.queries.log_locations` | The `log_locations` value nested beneath the detector entry's `queries` object. |
| `$.queries.log_locations[*]` | Every item in the `log_locations` array. |
| `$.path_or_destination` | The `path_or_destination` property on the current row. |

The change in `$` scope is important. The transformer first evaluates
`for_each` against the detector entry. It then evaluates `fields_from` and
`path_from` separately against each value returned by `for_each`. A row-relative
selector should therefore be `$.port`, not
`$.queries.metrics_outputs[*].port`.

## Defaults and overrides

Put defaults and constants in `values`. JSON data types are retained:

```json
"values": {
  "read_from_head": false,
  "refresh_interval": 10,
  "mem_buf_limit": "10MB",
  "labels": {"source": "example"},
  "allowed_extensions": ["log", "txt"]
}
```

This becomes Boolean, numeric, string, mapping, and list data in the rendered
YAML. The `labels` and `allowed_extensions` names above only illustrate nested
data types; use them only if the selected target plugin actually supports those
parameters. Do not quote a Boolean or number unless the target plugin
specifically expects a string.

Values are merged in this order:

```text
values → fields_from → path_from as path
```

Therefore, a dynamic `fields_from` value replaces a default with the same key,
and `path_from` replaces an earlier `path`. However, `fields_from` is not a
fallback operator: if one of its selectors has no match, the complete source
row is skipped. To use a fixed fallback unconditionally, place that property
only in `values`. The current rule contract does not support “copy this field,
otherwise retain the default” in a single rule.

Defaults belong in mappings when they are product or deployment-policy choices.
Defaults belong in a template only when they are intrinsic to that template's
output contract and should apply to every mapping using it.

## Fluent Bit plugin parameters

The Fluent Bit pipeline templates treat nearly every property on a normalized
plugin object as a plugin parameter. For example:

```json
"values": {
  "name": "tail",
  "tag": "example.logs",
  "read_from_head": false,
  "refresh_interval": 10,
  "skip_long_lines": true,
  "mem_buf_limit": "10MB",
  "storage.type": "filesystem"
}
```

renders semantically as:

```yaml
- name: tail
  tag: example.logs
  read_from_head: false
  refresh_interval: 10
  skip_long_lines: true
  mem_buf_limit: 10MB
  storage.type: filesystem
```

Three properties receive special template treatment:

- `name` is always emitted first and identifies the Fluent Bit plugin;
- `path` is emitted as the input path when present; and
- `path_suffix` is appended to `path` and then omitted from the final YAML.

All remaining properties, including nested mappings and lists, are emitted as
plugin parameters. Parameter spelling is not translated or validated against
Fluent Bit's complete plugin catalogue, so the mapping author must use names
supported by the selected plugin and agent version.

## Fluent Bit processors

A Fluent Bit processor is configured beneath the input that should run it.
Processors are injected into that input by placing the complete nested
`processors` structure in the rule's `values` object:

```json
"values": {
  "name": "tail",
  "tag": "postgresql.17.logs",
  "path_suffix": "/*.log",
  "read_from_head": true,
  "processors": {
    "logs": [
      {
        "name": "lua",
        "script": "/etc/fluent-bit/scripts/postgresql.lua",
        "call": "process_postgresql_record"
      }
    ]
  }
}
```

The generic Fluent Bit template preserves this nested object. After final YAML
serialization, it appears beneath the input:

```yaml
pipeline:
  inputs:
    - name: tail
      path: /var/lib/postgresql/17/log/*.log
      tag: postgresql.17.logs
      read_from_head: true
      processors:
        logs:
          - name: lua
            script: /etc/fluent-bit/scripts/postgresql.lua
            call: process_postgresql_record
```

The mapping only references the Lua script. It does not create, validate, or
deploy `/etc/fluent-bit/scripts/postgresql.lua`. The deployment must install
that file, and it must define the named `process_postgresql_record` callback.
The mapping's minimum agent version must also support the processor form being
generated.

Multiple processors can be supplied as additional objects in the `logs` list.
Their list order is retained. Other processor signal groups can be added only
when supported by the target Fluent Bit version and the input's data type.

## Jinja basics for this project

Jinja is a text-template language. This project uses only a small part of it:

- `{{ expression }}` writes a value into the output;
- `{% if condition %}` conditionally includes text;
- `{% for item in items %}` repeats text; and
- `| tojson` safely formats JSON-compatible values so the rendered text remains
  valid YAML.

The Fluent Bit template receives a variable called `plugins`, which is the
list produced by the mapping rules. Its essential behavior is:

```jinja2
{% for plugin in plugins %}
    - name: {{ plugin.name | tojson }}
{% if plugin.path is defined %}
      path: {{ (plugin.path ~ (plugin.path_suffix | default(""))) | tojson }}
{% endif %}
{% for property_name, property_value in plugin.items() %}
{% if property_name not in ["name", "path", "path_suffix"] %}
      {{ property_name }}: {{ property_value | tojson }}
{% endif %}
{% endfor %}
{% endfor %}
```

In plain language, it loops over plugin objects, writes `name`, constructs the
optional path, then writes every other property. Consequently, adding a normal
Fluent Bit parameter or nested processor to `values` does not require a Jinja
change.

Jinja runs in an immutable sandbox with strict undefined values. Templates
cannot modify their input context, and a reference to a missing required value
causes rendering to fail instead of silently producing incomplete YAML.

## Template metadata when reusing a template

The mapping locks these template expectations:

```json
"render": {
  "template": "fluent_bit_5_pipeline.yaml.j2",
  "metadata_file": "fluent_bit_5_pipeline.metadata.yaml",
  "version": "1.0.0",
  "template_api_version": "1.0"
}
```

The referenced metadata must name the same template and versions, target the
same agent, and support the requested agent version. When adding only another
mapping that uses the existing plugin-object contract, do not change the
template version. Change the template and metadata versions together when the
rendered behavior or required context changes.

## Rendering, fragment injection, and processor injection

These are separate operations:

1. **Rendering** reads detector results and mappings, then writes a standalone
   generated fragment plus an orchestration manifest.
2. **Fragment injection** is the `inject` CLI command. For Fluent Bit, it
   verifies the fragment hash and adds the fragment path to the parent YAML's
   top-level `includes` list.
3. **Processor injection** happens earlier during rendering. A mapping's nested
   `values.processors` object becomes part of the generated input plugin. It
   does not modify the parent file directly.

Render a new mapping with:

```powershell
.\.venv\Scripts\obs-config-transformer.exe render `
  --detector-results examples/detector_results.json `
  --mapping-root mappings `
  --target-tool fluent-bit `
  --target-version 5.0.0 `
  --output-root build `
  --manifest-output build/orchestration.json
```

Then compose the generated fragments into a parent configuration:

```powershell
.\.venv\Scripts\obs-config-transformer.exe inject `
  --manifest build/orchestration.json `
  --artifact-root build `
  --parent-config examples/fluent_bit_parent.yaml `
  --output build/fluent-bit.yaml
```

Finally, validate the complete configuration with the same Fluent Bit version
used for mapping selection:

```powershell
fluent-bit --config build/fluent-bit.yaml --dry-run
```

## Testing a new mapping

Tests should prove the complete translation:

1. create representative detector rows;
2. render through the real mapping catalogue and target version;
3. parse the generated YAML;
4. assert plugin names, dynamic attributes, defaults, nested processors, and
   output paths; and
5. verify that a lower agent version either selects the intended older mapping
   or fails with a clear compatibility error.

Use the existing catalogue integration tests in `tests/test_agent_mappings.py`
as examples. Run the component checks from the transformer directory:

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m ruff check src tests
.\.venv\Scripts\python.exe -m pylint src\config_template_transformer tests
.\.venv\Scripts\python.exe -m pytest -q -s
```

For Fluent Bit changes, also run a native or containerized `--dry-run` against
the assembled configuration whenever the required plugins and processor files
are available.

## Author checklist

- The detector and query names match an existing detector contract.
- Every JSONPath is evaluated at the intended scope.
- Every plugin parameter is supported by the target plugin version.
- Defaults use the correct JSON types.
- Dynamic fields intentionally skip rows when their source value is absent.
- `minimum_version` covers every plugin and processor feature used.
- The selected template metadata advertises the required capability.
- Lua or other external processor assets are deployed separately.
- Tests assert the final YAML structure.
- The assembled agent configuration passes its native validation command.
