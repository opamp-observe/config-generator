<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Template metadata contract

Every Jinja template has a YAML metadata sidecar. The sidecar is the
machine-readable declaration of the template's identity, context contract,
supported observability tool, supported tool versions, output kind, signals,
and capabilities. A transform references it through `render.metadata_file`.

This keeps compatibility information with the template rather than relying on
file names or documentation conventions. Rendering stops before an artifact is
written when the transform and metadata disagree.

## Resource format

Template metadata uses the `opamp.info/v1alpha1` API and
`ObservabilityTemplateMetadata` kind:

```yaml
api_version: opamp.info/v1alpha1
kind: ObservabilityTemplateMetadata
metadata:
  name: fluent_bit_inputs
  version: 1.0.0
spec:
  engine: jinja2
  template: fluent_bit_inputs.yaml.j2
  template_api_version: "1.0"
  target:
    tool: fluent-bit
    version_constraint: ">=3.2,<5.0"
  supports:
    artifact_kind: input_fragment
    signals:
      - logs
    capabilities:
      - file_tail_inputs
      - arbitrary_plugin_properties
      - multiple_inputs
      - stable_empty_fragment
```

The packaged JSON Schema is
`config_template_transformer/schemas/template_metadata.schema.json`. Unknown
fields are rejected.

## Field meanings

| Field | Meaning |
| --- | --- |
| `metadata.name` | Stable template identity used by automation and manifests. |
| `metadata.version` | PEP 440-compatible template implementation version. Increase it when rendered behavior changes. |
| `spec.engine` | Required rendering engine. The current contract permits `jinja2`. |
| `spec.template` | Jinja file path relative to the approved template root. |
| `spec.template_api_version` | Version of the context supplied to the template. Increase it when required context fields or meanings change incompatibly. |
| `spec.target.tool` | Stable `TargetAdapter` name for the supported observability tool. |
| `spec.target.version_constraint` | PEP 440 constraint describing supported versions of that tool. |
| `spec.supports.artifact_kind` | Stable description of the fragment produced, such as `input_fragment`. |
| `spec.supports.signals` | Observability signals represented by the template, such as `logs`, `metrics`, or `traces`. |
| `spec.supports.capabilities` | Stable feature identifiers that callers can use to select an appropriate template. |

Capability names use lowercase snake case. They describe behavior rather than
a specific detector. New capabilities can be added in a new metadata version;
removing or changing their meaning requires a template version increase.

## Transform reference and enforcement

A transform retains explicit expectations and points to the sidecar:

```yaml
api_version: opamp.info/v1alpha2
render:
  engine: jinja2
  template: fluent_bit_inputs.yaml.j2
  metadata_file: fluent_bit_inputs.metadata.yaml
  version: 1.0.0
  template_api_version: "1.0"
  context_name: plugins
```

Before detector selection or Jinja execution, the transformer validates that:

1. both resources satisfy their JSON Schemas;
2. the transform's template path matches `spec.template`;
3. the transform's version matches `metadata.version`;
4. the context API versions match;
5. the transform target matches `spec.target.tool`; and
6. the requested tool version satisfies both the transform constraint and the
   template's `spec.target.version_constraint`.

The duplication in the transform is intentional. It acts as a compatibility
lock: updating a template sidecar cannot silently change the behavior or target
range of an existing transform.

`opamp.info/v1alpha2` transform definitions require `render.metadata_file`.
The generated orchestration manifest uses schema version `2.0`, which adds the
required template target, support, metadata path, and metadata digest fields.

## Manifest provenance

Each artifact's `template` object in `orchestration.json` contains:

- stable template name and Jinja path;
- template and context API versions;
- rendering engine and metadata resource API version;
- template path and SHA-256 digest;
- metadata path and SHA-256 digest;
- supported tool and tool-version constraint; and
- artifact kind, signals, and capabilities.

Downstream orchestration can therefore inspect support and verify both files
without parsing Jinja or trusting mutable file names.

## Adding a template for another tool

Create the Jinja file and metadata sidecar together, implement or select the
matching `TargetAdapter`, then create a transform whose `target` and `render`
expectations agree with the metadata. Use the stable tool keys documented for
the adapters. The same contract applies to Fluentd, Vector, OpenTelemetry
Collector, Telegraf, Elastic Agent, and Filebeat templates.
