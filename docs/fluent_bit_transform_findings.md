<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Detector output to Fluent Bit configuration

## Problem statement

The detector suite discovers product processes, configuration locations, log
locations, listening ports, and related runtime details. The aggregate
`detector-results.json` document is validated by
[`schemas/detector_results.schema.json`](../schemas/detector_results.schema.json).
The objective is to turn applicable detector findings into Fluent Bit YAML
fragments that can collect the discovered product logs. The fragments are
included by an overall parent configuration rather than each transform having
to generate a complete Fluent Bit configuration.

The JSON Schema documents cannot, by themselves, supply a complete Fluent Bit
configuration. A schema describes and validates the structure of detector
results. It does not contain the paths discovered on a particular host, and it
does not know the deployment's log destination, credentials, TLS policy,
buffering policy, or parser choices. Those values come from three distinct
inputs:

1. The detector result instance supplies discovered log paths and product,
   version, platform, and deployment evidence.
2. A detector-to-Fluent-Bit YAML transform definition supplies the meaning of
   each result field, including iteration, input plugin, tag, and parser rules.
3. A deployment profile supplies environment-owned settings such as outputs,
   endpoints, authentication, TLS, storage, and buffering.

Consequently, the transformation should consume a validated
`detector-results.json` instance. The schemas remain the input contract rather
than becoming the source of discovered values.

## Findings

### Fluent Bit YAML is a structured target

Fluent Bit YAML configuration is the standard configuration format from
Fluent Bit 3.2 onward. It supports top-level sections including `service`,
`pipeline`, `parsers`, and `multiline_parsers`. The `pipeline` section contains
arrays of `inputs`, `filters`, and `outputs`. The transformer should therefore
construct a JSON-compatible object with this structure and serialize that
object as YAML. Generating YAML by concatenating text would make quoting,
escaping, indentation, and list construction unnecessarily fragile.

Sources:

- [Fluent Bit configuration formats](https://docs.fluentbit.io/manual/administration/configuring-fluent-bit)
- [Fluent Bit YAML sections](https://docs.fluentbit.io/manual/4.2/administration/configuring-fluent-bit/yaml)
- [Fluent Bit pipeline structure](https://docs.fluentbit.io/manual/administration/configuring-fluent-bit/yaml/pipeline-section)

### Included fragments are supported natively

The parent Fluent Bit YAML file can use the top-level `includes` section to
merge generated files into its configuration. Include entries may be relative
or absolute paths. Relative paths are resolved relative to the file containing
the `includes` section. Include paths must be literal strings; Fluent Bit does
not expand environment variables in this section.

Fluent Bit merges multiple `pipeline` sections into one internal pipeline.
This allows a generated fragment to contain only `pipeline.inputs`, while the
parent owns the single `service` section and shared filters and outputs. Parser
definitions may also be supplied by included files when a detector needs them.

Sources:

- [Fluent Bit YAML includes](https://docs.fluentbit.io/manual/administration/configuring-fluent-bit/yaml/includes-section)
- [Fluent Bit YAML pipeline merging](https://docs.fluentbit.io/manual/4.2/administration/configuring-fluent-bit/yaml/pipeline-section)

### Selection and transformation are separate concerns

[JSONPath RFC 9535](https://www.rfc-editor.org/rfc/rfc9535.html) provides a
standard way to select values from JSON. It is suitable for mapping expressions
such as a path to an Oracle alert-log field, but it does not define how to build
the complete Fluent Bit object. [JSON Pointer RFC 6901](https://www.rfc-editor.org/info/rfc6901/)
can address one exact value and is useful for fixed locations, but it is less
convenient for filtering detector arrays.

A transformation language or implementation is still required to iterate over
selected values, remove duplicates, construct input entries, add tags, and
merge deployment-owned configuration.

### Serialization is not transformation

YAML 1.2 was designed as a superset of JSON, so an already-constructed JSON
value can be serialized directly as YAML. Converting a JSON document to YAML
without first reshaping it, however, would only reproduce the detector result
in different syntax; it would not produce a Fluent Bit configuration.

Sources:

- [YAML 1.2.2 specification](https://yaml.org/spec/1.2/)
- [yq JSON and YAML conversion](https://mikefarah.gitbook.io/yq/usage/convert)

### The deployment policy cannot be inferred safely

Detection can identify candidate files, but it cannot decide where records
should be sent or which credentials should be used. Output plugins and secrets
must therefore be supplied separately. Keeping deployment policy out of the
detector mappings also allows the same discovery result to be rendered for
stdout during testing and for an environment-specific destination in
production.

### Candidate paths need explicit treatment

Some detector fields are candidates or glob patterns rather than confirmed
files. For example, Oracle Database can return `text_alert_log_glob`,
`xml_alert_log_glob`, and `listener_log_glob`. A mapping must explicitly name
the eligible fields and their parsers. The transformer should not turn every
string in `log_locations` into a Tail input.

The current detector result schemas deliberately allow flat osquery rows with
product-specific column names. This makes separate YAML transform definitions
preferable to guessing field semantics from suffixes such as `_path`,
`_directory`, or `_glob`.

### A transform rule must support cardinality

One detector result can contain multiple rows and each row can identify a
different log file or glob. A transform rule must therefore use `for_each`
semantics: every selected non-empty value produces a separate Fluent Bit input.
The transform must not stop after the first match or collapse unrelated files
into one Tail input implicitly.

Iteration must be deterministic. Selected values should retain detector-result
order, then be deduplicated using the rendered input identity, normally
`name`, `path`, and `tag`. This permits several database instances or
WebLogic managed servers to generate several Tail inputs without producing
duplicates when multiple discovery records refer to the same file.

## Evaluated standards and libraries

| Option | Strengths | Limitations | Best use |
|---|---|---|---|
| JSONPath | IETF standard for selecting JSON values | Does not construct the complete output | Portable selectors in mapping files |
| JSON Pointer | IETF standard for exact JSON locations | No filtering or iteration | Fixed-value references |
| JSONata | Declarative selection and complete object construction | Not an IETF standard; runtime choice must be controlled | Externally editable transformation rules |
| jq and yq | Mature, portable command-line processing and YAML emission | Shell quoting differs across platforms; mappings can become difficult to maintain | Prototypes and command-line workflows |
| CUE | Combines configuration, validation, defaults, and YAML export | Introduces another configuration language and toolchain | Policy-heavy configuration generation |
| Jsonnet | Reusable templates, composition, and YAML manifestation | Introduces another language and runtime | Large families of related generated configurations |
| Python, `jsonschema`, and `ruamel.yaml` | Fits the existing runner and tests; explicit iteration, fragment construction, and YAML 1.2 input/output | Transformation behavior must be implemented and maintained | Recommended repository implementation |
| Jinja2 | Familiar templates with loops, conditions, includes, and macros | Operates on YAML text and therefore requires safe quoting and YAML re-parsing | Fragment rendering after JSONPath normalization |

Relevant implementation references:

- [JSONata construction](https://docs.jsonata.org/construction)
- [jq object and array construction](https://jqlang.org/manual/dev/)
- [CUE export](https://cuelang.org/docs/concept/using-the-cue-export-command/)
- [Jsonnet YAML manifestation](https://jsonnet.org/ref/stdlib.html)
- [`ruamel.yaml` YAML 1.2 loader and dumper](https://pypi.org/project/ruamel.yaml/)

## Recommended architecture

Use a Python transformer with `jsonschema` validation, standards-based JSONPath
selectors in YAML transform definitions, and `ruamel.yaml` parsing and
serialization:

```text
detector schemas ── validate ──┐
                               │
detector-results.json ─────────┼─► transformer ─► generated fragments
YAML transform definitions ────┘                         │
                                                       ▼
parent fluent-bit.yaml ─────────────────────────► includes + merged pipeline
```

The primary output mode should be `fragment`. A generated fragment must be a
valid Fluent Bit YAML document, but it is not required to contain `service` or
`pipeline.outputs`. An optional future `standalone` mode may add a deployment
profile, but fragment generation must not depend on that mode.

The stages should be:

1. Validate the aggregate detector result with the master schema.
2. Select only results with `detected: true` and without blocking errors.
3. Parse the YAML transform definition matching `detector_name` and
   `detector_version`.
4. For each transform rule, evaluate its `for_each` JSONPath against the
   detector result.
5. Loop over every selected item, skip missing or empty source values, and
   render one structured input object per item.
6. Normalize separators and remove duplicate rendered inputs without
   destroying valid glob syntax.
7. Construct a fragment containing `pipeline.inputs` and any parser or filter
   definitions explicitly owned by the transform.
8. Serialize the fragment as YAML 1.2 at a deterministic path.
9. Include the fragment path literally in the parent Fluent Bit configuration.
10. Validate the assembled parent configuration with Fluent Bit itself.

A conceptual YAML transform definition is:

```yaml
api_version: opamp.info/v1alpha2
kind: ObservabilityFragmentTransform
metadata:
  name: oracle_database_19_logs
  version: 1.0.0
spec:
  detector:
    name: oracle_database_19
    version_constraint: ">=1.0,<2.0"
  target:
    tool: fluent-bit
    version_constraint: ">=3.2,<5.0"
  output:
    path: generated/oracle_database_19.inputs.yaml
    include_path: generated/oracle_database_19.inputs.yaml
  render:
    engine: jinja2
    template: fluent_bit_inputs.yaml.j2
    metadata_file: fluent_bit_inputs.metadata.yaml
    version: 1.0.0
    template_api_version: "1.0"
    context_name: plugins
  rules:
    - name: alert_logs
      for_each: $.queries.log_locations[*]
      path_from: $.text_alert_log_glob
      values:
        name: tail
        tag: oracle_database_19.alert
        parser: oracle_alert
    - name: listener_logs
      for_each: $.queries.log_locations[*]
      path_from: $.listener_log_glob
      values:
        name: tail
        tag: oracle_database_19.listener
        parser: oracle_listener
```

`for_each` selects all log-location rows. Each selected row becomes the root
query argument for `path_from`, keeping both expressions compatible with RFC
9535 JSONPath. The transformer adds the resulting scalar as the emitted input's
`path`. With three distinct alert-log rows, the first rule therefore produces
three Tail inputs. `path_from` values that are absent, null, or empty do not
produce an input.

The generated fragment would contain entries such as:

```yaml
pipeline:
  inputs:
    - name: tail
      path: /opt/oracle/diag/rdbms/*/trace/alert_*.log
      tag: oracle_database_19.alert
      parser: oracle_alert
    - name: tail
      path: /opt/oracle/diag/rdbms/finance/trace/alert_FINANCE.log
      tag: oracle_database_19.alert
      parser: oracle_alert
```

The parent configuration owns global and destination settings and includes the
fragment using a literal path:

```yaml
includes:
  - generated/oracle_database_19.inputs.yaml

service:
  log_level: info

pipeline:
  outputs:
    - name: stdout
      match: "*"
```

For a stable parent include list, the transformer should always write each
declared fragment path atomically. When no matching logs are found, it should
write a valid fragment with `pipeline.inputs: []` rather than leave a stale
fragment or remove a file still named by the parent.

## Jinja rendering option

Jinja can provide the template-oriented `for each` layer without replacing
JSONPath. JSONPath should remain responsible for selecting detector values and
Python should normalize and deduplicate those values. Jinja should receive only
a JSON-compatible `plugins` list and render the Fluent Bit fragment.

This separation prevents templates from needing access to the complete detector
document or to the JSONPath engine:

```text
detector result
    │
    ├─ JSONPath selection
    ├─ validation, normalization, and deduplication
    ▼
plugins: list[object]
    │
    ├─ sandboxed Jinja rendering
    ├─ YAML safe-load and structural validation
    ▼
generated Fluent Bit include fragment
```

The YAML transform definition can select the Jinja renderer and template while
retaining the structured rules that build the rendering context:

```yaml
api_version: opamp.info/v1alpha2
kind: ObservabilityFragmentTransform
metadata:
  name: oracle_database_19_logs
  version: 1.0.0
spec:
  detector:
    name: oracle_database_19
    version_constraint: ">=1.0,<2.0"
  target:
    tool: fluent-bit
    version_constraint: ">=3.2,<5.0"
  output:
    path: generated/oracle_database_19.inputs.yaml
    include_path: generated/oracle_database_19.inputs.yaml
  render:
    engine: jinja2
    template: fluent_bit_inputs.yaml.j2
    metadata_file: fluent_bit_inputs.metadata.yaml
    version: 1.0.0
    template_api_version: "1.0"
    context_name: plugins
  rules:
    - name: alert_logs
      for_each: $.queries.log_locations[*]
      path_from: $.text_alert_log_glob
      values:
        name: tail
        tag: oracle_database_19.alert
        parser: oracle_alert
    - name: listener_logs
      for_each: $.queries.log_locations[*]
      path_from: $.listener_log_glob
      values:
        name: tail
        tag: oracle_database_19.listener
        parser: oracle_listener
```

Each successful rule iteration appends an object containing `name`, `path`,
`tag`, and optional `parser` values to `plugins`. The Jinja template
then loops over those normalized objects:

```jinja
pipeline:
{% if plugins %}
  inputs:
{% for plugin in plugins %}
    - name: {{ plugin.name | tojson }}
      path: {{ plugin.path | tojson }}
      tag: {{ plugin.tag | tojson }}
{% if plugin.parser is defined and plugin.parser %}
      parser: {{ plugin.parser | tojson }}
{% endif %}
{% endfor %}
{% else %}
  inputs: []
{% endif %}
```

The `tojson` filter is important even though the target is YAML. A JSON-quoted
string is a valid YAML 1.2 scalar and protects paths and tags containing
backslashes, colons, hash characters, quotes, or YAML-like boolean words. The
empty branch produces the stable `pipeline.inputs: []` fragment required by a
parent with a fixed include list.

A Python rendering adapter could have the following shape:

```python
from pathlib import Path
from typing import Any

from jinja2 import FileSystemLoader
from jinja2 import StrictUndefined
from jinja2.sandbox import ImmutableSandboxedEnvironment
from ruamel.yaml import YAML


def render_fragment(
    template_root: Path,
    template_name: str,
    plugins: list[dict[str, Any]],
) -> dict[str, Any]:
    """Render normalized Tail inputs and return a parsed YAML fragment."""

    template_environment = ImmutableSandboxedEnvironment(
        loader=FileSystemLoader(template_root),
        undefined=StrictUndefined,
        autoescape=False,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    rendered_yaml = template_environment.get_template(template_name).render(
        plugins=plugins
    )

    yaml_parser = YAML(typ="safe")
    fragment = yaml_parser.load(rendered_yaml)
    if not isinstance(fragment, dict):
        raise ValueError("The rendered Fluent Bit fragment must be a mapping")
    return fragment
```

The production implementation should create one configured environment, load
and compile each template once, and reuse it across detector results. The parsed
fragment should be validated before it is serialized canonically with
`ruamel.yaml` and written atomically.

Use `ImmutableSandboxedEnvironment` and `StrictUndefined` so templates cannot
silently consume missing values or mutate supplied lists and dictionaries. Only
JSON-compatible values should enter the template context; do not expose file
handles, application objects, callables, the JSONPath engine, or operating-system
functions. Jinja notes that sandboxing is not complete resource isolation, so
the transformer must also limit input collection size, rendered output size,
and execution time.

References:

- [Jinja template engine](https://jinja.palletsprojects.com/en/stable/intro/)
- [Jinja sandbox](https://jinja.palletsprojects.com/en/stable/sandbox/)
- [Jinja strict undefined values](https://jinja.palletsprojects.com/en/stable/api/)

## Validation and testing

Transformation tests should cover:

- validation failures for malformed detector results;
- detected and undetected products;
- empty, duplicate, wildcard, Windows, and container-visible paths;
- mapping-version mismatches;
- parser and tag selection for every mapped log field;
- zero, one, and multiple iterations for each `for_each` rule;
- one Tail input per distinct rendered path;
- Jinja rendering with zero, one, and multiple `plugins`;
- failure on undefined Jinja values;
- YAML-safe rendering of quotes, backslashes, colons, and hash characters;
- stable empty fragments for parent configurations with fixed include lists;
- literal relative and absolute include paths;
- deterministic output ordering;
- parent-owned output configuration without embedding credentials in test fixtures;
- YAML parsing after serialization; and
- Fluent Bit validation of the assembled parent configuration.

Use Fluent Bit's native configuration check on the parent as the final
authority. Validation must run with the generated fragments at the same
relative paths they will have at runtime:

```sh
fluent-bit --dry-run -c parent/fluent-bit.yaml
```

Fluent Bit 4.2 and later performs full plugin-property validation during
`--dry-run`, in addition to configuration syntax checking. See the
[Fluent Bit validation documentation](https://docs.fluentbit.io/manual/4.2/administration/configuring-fluent-bit).

## Implemented initial contract

The standalone
[configuration template transformer](../transformers/config-template-transformer/readme.md)
implements the initial recommendation with these decisions:

- `jsonpath-rfc9535` evaluates selection rules;
- JSON Schema validates `opamp.info/v1alpha2` YAML transform definitions;
- every template has validated metadata declaring its version, context API,
  capabilities, observability signals, target tool, and supported tool versions;
- each transform owns one stable fragment path and semantic version;
- rules emit explicit detector values without requiring the path to exist on
  the machine running the transformer;
- canonical JSON identity deduplicates complete normalized plugin objects;
- an immutable Jinja sandbox with strict undefined values renders only a
  normalized JSON-compatible plugin list;
- the versioned JSON orchestration manifest records checksums and literal
  include instructions; and
- the Fluent Bit adapter emits YAML `pipeline.inputs`, injects top-level
  `includes`, and is validated with Fluent Bit 4.2 `--dry-run`.

Windows deployment-path mapping, format-specific parsers such as XML
multiline handling, and environment-driven deployment-profile overrides remain
deployment-policy concerns rather than implicit transformer behavior.
Production parents continue to own every external output and its credentials.
