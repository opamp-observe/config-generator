<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Configuration generation execution flow

## End-to-end flow

This diagram shows the path from detector execution through deployment-ready
observability-agent configuration.

```mermaid
flowchart TD
    request([Run detector and configuration workflow])

    subgraph discovery["1. Product and host discovery"]
        runner["Detector runner<br/>runner.py"]
        catalogue["Detector configuration<br/>detector.json and packs/*.conf"]
        osquery["osquery executes the<br/>selected platform queries"]
        aggregate["Aggregate detector result JSON<br/>detectors array"]

        runner --> catalogue
        catalogue --> osquery
        osquery --> aggregate
    end

    subgraph transformation["2. Agent-specific transformation"]
        transformer["Configuration template transformer<br/>render command"]
        mapping_catalogue["Agent mapping JSON<br/>mappings/agent/version/detector.json"]
        selector["Select highest compatible<br/>minimum version per detector"]
        templates["Template and metadata sidecar<br/>templates/*.yaml.j2 and *.metadata.yaml"]
        adapter["Target adapter validates and<br/>serializes agent YAML"]
        artifacts["Generated agent YAML fragments<br/>build/generated/**"]
        manifest["Checksummed orchestration manifest<br/>build/orchestration.json"]

        aggregate --> transformer
        mapping_catalogue --> transformer
        transformer --> selector
        selector --> templates
        templates --> adapter
        adapter --> artifacts
        adapter --> manifest
        artifacts --> manifest
    end

    subgraph deployment["3. Target-specific composition and startup"]
        target_choice{"Target agent"}
        fluent_inject["Verify artifact hashes and inject<br/>Fluent Bit top-level includes"]
        fluent_parent["Parent plus generated includes<br/>build/fluent-bit.yaml"]
        otel_compose["Base YAML plus generated YAML<br/>repeated --config arguments"]
        fluent_agent([Fluent Bit starts])
        otel_agent([OTel Collector Contrib starts])

        manifest --> target_choice
        target_choice -->|fluent-bit| fluent_inject
        artifacts --> fluent_inject
        fluent_inject --> fluent_parent
        fluent_parent --> fluent_agent
        target_choice -->|otelcol-contrib| otel_compose
        artifacts --> otel_compose
        otel_compose --> otel_agent
    end

    request --> runner
```

The detector runner and transformer remain separate processes. Detector results
are the versioned handoff between discovery and configuration generation; the
orchestration manifest is the checksummed handoff between generation and
deployment.

## Detailed transformer flow

This diagram expands the `render` command, including its explicit-definition
compatibility path and the normal agent-mapping path.

```mermaid
flowchart TD
    cli([render command])
    source_choice{"Exactly one source supplied?"}
    input_error([Log validation error and exit 1])
    load_results["Load detector-results JSON"]
    validate_results["Validate optional external schema<br/>and require detectors array"]
    parse_version["Parse target version with PEP 440"]
    source_type{"Transformation source"}

    cli --> source_choice
    source_choice -->|No or both| input_error
    source_choice -->|Yes| load_results
    load_results --> validate_results
    validate_results --> parse_version
    parse_version --> source_type

    subgraph definitions["Definition discovery and compatibility selection"]
        load_yaml["Load and schema-validate each<br/>explicit YAML transform"]
        scan_json["Recursively scan mapping root<br/>for JSON resources"]
        validate_mapping["Validate every agent mapping<br/>against the packaged schema"]
        filter_mapping["Filter by detector name and<br/>requested agent type"]
        compare_floor["Keep minimum versions less than<br/>or equal to target version"]
        select_floor["For each detector select the unique<br/>highest compatible floor"]
        selection_error(["Missing compatible floor or<br/>equal best floors: exit 1"])
        normalize["Normalize mapping into an immutable<br/>transform definition"]

        source_type -->|--definition| load_yaml
        source_type -->|--mapping-root| scan_json
        scan_json --> validate_mapping
        validate_mapping --> filter_mapping
        filter_mapping --> compare_floor
        compare_floor --> select_floor
        select_floor -->|Missing or ambiguous| selection_error
        select_floor -->|Unique match| normalize
    end

    common_adapter["Require one target tool and<br/>resolve its adapter"]
    definition_loop{"Next selected definition"}
    check_target["Check target version constraint"]
    load_template["Resolve template and metadata paths<br/>inside the approved template root"]
    check_metadata["Validate metadata schema, identity,<br/>API, tool, version and capabilities"]
    detector_state{"Matching detector is<br/>present, detected and error-free?"}
    empty_plugins["Use an empty plugin list and<br/>record the selection status"]

    load_yaml --> common_adapter
    normalize --> common_adapter
    common_adapter --> definition_loop
    definition_loop --> check_target
    check_target --> load_template
    load_template --> check_metadata
    check_metadata --> detector_state

    subgraph rules["JSONPath rule normalization"]
        rule_loop{"Next rule and selected row"}
        static_values["Copy static values"]
        dynamic_fields["Resolve fields_from selectors<br/>as singular dynamic values"]
        field_state{"Dynamic field result"}
        skip_row["Skip row"]
        path_choice{"path_from configured?"}
        resolve_paths["Resolve, trim and reject<br/>empty path values"]
        deduplicate["Canonicalize and deduplicate<br/>plugin objects"]
        enforce_limit["Enforce maximum plugin count"]
        more_rows{"More rules or rows?"}

        detector_state -->|Yes| rule_loop
        rule_loop --> static_values
        static_values --> dynamic_fields
        dynamic_fields --> field_state
        field_state -->|Missing| skip_row
        field_state -->|Multiple| input_error
        field_state -->|One value per field| path_choice
        path_choice -->|Yes| resolve_paths
        path_choice -->|No| deduplicate
        resolve_paths --> deduplicate
        deduplicate --> enforce_limit
        enforce_limit --> more_rows
        skip_row --> more_rows
        more_rows -->|Yes| rule_loop
    end

    detector_state -->|No| empty_plugins
    render["Render with immutable sandboxed Jinja<br/>and strict undefined values"]
    parse_yaml["Enforce rendered byte limit<br/>and parse as a YAML mapping"]
    serialize["Adapter validates target structure<br/>and serializes deterministic YAML"]
    write_artifact["Atomically write artifact and<br/>calculate SHA-256 provenance"]
    more_definitions{"More definitions?"}
    build_manifest["Build target, source, template,<br/>artifact and include records"]
    validate_manifest["Validate manifest schema"]
    write_manifest["Atomically write orchestration JSON"]
    success([Exit 0])

    more_rows -->|No| render
    empty_plugins --> render
    render --> parse_yaml
    parse_yaml --> serialize
    serialize --> write_artifact
    write_artifact --> more_definitions
    more_definitions -->|Yes| definition_loop
    more_definitions -->|No| build_manifest
    build_manifest --> validate_manifest
    validate_manifest --> write_manifest
    write_manifest --> success
```

Any schema, path, JSONPath, version, template, size, plugin-count, or adapter
validation failure follows the error outcome and returns a non-zero CLI status.
Artifact files and the final manifest are written atomically.

## Configuration file relationships

This diagram shows which files are authored, which files are generated, and
how references connect them. Solid arrows represent runtime data or explicit
references. Dotted arrows represent schema validation.

```mermaid
flowchart LR
    subgraph detector_files["Detector-owned files"]
        detector_manifest["detectors/product/version/detector.json<br/>identity, platforms, pack and schema paths"]
        detector_pack["detectors/product/version/packs/platform.conf<br/>osquery SQL and output column aliases"]
        detector_schema["schemas/detectors/detector_name.schema.json<br/>detector-result contract"]
        aggregate_schema["schemas/detector_results.schema.json<br/>aggregate-result contract"]
        detector_results["detector-results.json<br/>generated aggregate evidence"]

        detector_manifest -->|selects| detector_pack
        detector_manifest -->|references| detector_schema
        detector_pack -->|produces query rows| detector_results
        detector_schema -. validates each entry .-> detector_results
        aggregate_schema -. validates aggregate .-> detector_results
    end

    subgraph mapping_files["Transformer-authored files"]
        mapping_schema["agent_mapping.schema.json"]
        mapping["mappings/agent/minimum_version/detector.json<br/>JSONPath rules, defaults, output and template reference"]
        transform_schema["transform_definition.schema.json"]
        manual_transform["examples/transforms/*.yaml<br/>optional manual-definition path"]
        metadata_schema["template_metadata.schema.json"]
        metadata["templates/name.metadata.yaml<br/>identity, version, capabilities and target range"]
        template["templates/name.yaml.j2<br/>agent YAML layout"]

        mapping_schema -. validates .-> mapping
        transform_schema -. validates .-> manual_transform
        mapping -->|names detector and version range| detector_results
        mapping -->|references template path and version| template
        mapping -->|references metadata path and version| metadata
        manual_transform -->|references template path and version| template
        manual_transform -->|references metadata path and version| metadata
        metadata_schema -. validates .-> metadata
        metadata -->|identifies and constrains| template
    end

    subgraph render_outputs["Render inputs and generated files"]
        render_command["obs-config-transformer render<br/>target tool, target version and output root"]
        generated_fragment["generated agent fragment<br/>for example nginx.inputs.yaml"]
        manifest_schema["orchestration_manifest.schema.json"]
        orchestration["orchestration.json<br/>versions, paths, hashes and composition strategy"]

        detector_results -->|--detector-results| render_command
        mapping -->|selected from --mapping-root| render_command
        manual_transform -->|alternative --definition input| render_command
        template -->|renders normalized plugin objects| render_command
        metadata -->|checked before rendering| render_command
        render_command -->|writes atomically| generated_fragment
        render_command -->|records artifact| orchestration
        generated_fragment -->|path and SHA-256| orchestration
        manifest_schema -. validates .-> orchestration
    end

    subgraph fluent_composition["Fluent Bit composition"]
        fluent_parent["examples/fluent_bit_parent.yaml<br/>deployment-owned parent"]
        inject_command["obs-config-transformer inject<br/>verifies manifest and artifact hashes"]
        assembled_fluent["assembled Fluent Bit YAML<br/>parent with top-level includes"]

        fluent_parent --> inject_command
        orchestration --> inject_command
        generated_fragment --> inject_command
        inject_command --> assembled_fluent
    end

    subgraph otel_composition["OpenTelemetry Collector composition"]
        otel_base["deployment-owned base Collector YAML"]
        otel_launch["deployment launcher<br/>builds repeated --config arguments"]
        otel_start["otelcol-contrib process"]

        otel_base --> otel_launch
        generated_fragment --> otel_launch
        orchestration -->|declares multiple_config_files strategy| otel_launch
        otel_launch -->|--config base --config generated| otel_start
    end
```

### File usage by stage

| File or hierarchy | Authored or generated | Used by | Purpose |
| --- | --- | --- | --- |
| `detectors/<product>/<version>/detector.json` | Authored | Detector runner | Identifies the detector, platform packs, result schema, and required queries. |
| `detectors/<product>/<version>/packs/<platform>.conf` | Authored | osquery | Defines the SQL that discovers processes, paths, ports, endpoints, and other evidence. |
| `schemas/detectors/*.schema.json` | Authored | Detector validation | Validates each detector's result entry. |
| Aggregate detector-result JSON | Generated | Transformer `render` command | Supplies the product evidence selected by mapping JSONPath rules. |
| `mappings/<agent>/<minimum_version>/<detector>.json` | Authored | Mapping selector and orchestrator | Connects detector fields to plugin attributes, defaults, processors, output paths, and templates. |
| `templates/*.yaml.j2` | Authored | Sandboxed Jinja renderer | Defines the target agent's YAML layout. |
| `templates/*.metadata.yaml` | Authored | Compatibility validation | Locks the template identity, version, context API, target versions, signals, and capabilities. |
| Generated agent fragment | Generated | Fluent Bit include injection or OTel startup | Contains the agent inputs, receivers, processors, and plugin parameters produced for one detector. |
| `orchestration.json` | Generated | Deployment composition | Records provenance, hashes, fragment paths, and the target composition strategy. |
| Fluent Bit parent YAML | Deployment-owned | Transformer `inject` command | Receives verified generated fragment paths in its top-level `includes` list. |
| OTel base YAML | Deployment-owned | `otelcol-contrib` process | Is composed with generated fragments through repeated `--config` arguments. |

The mapping JSON is the central relationship file. It identifies the detector
contract it consumes, the agent/version family it targets, the template and
metadata it requires, and the generated artifact path. The template metadata
does not map detector fields; it independently verifies that the selected
template is suitable for that target and version.
