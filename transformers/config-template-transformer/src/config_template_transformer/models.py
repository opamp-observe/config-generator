# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Typed transformation definitions and orchestration manifest records."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TransformRule:
    """Describe one JSONPath selection that emits normalized plugin objects.

    Attributes:
        name: Stable rule name used in diagnostics.
        for_each: RFC 9535 JSONPath selecting source rows.
        path_from: Optional RFC 9535 JSONPath selecting paths from each source row.
        path_match: Optional regular expression restricting selected path values.
        fields_from: Output field names mapped to RFC 9535 selectors on each row.
        values: Static plugin values copied into every emitted object.
        source_format: Stable payload-format hint consumed by semantic mappings.
    """

    name: str
    for_each: str
    path_from: str | None
    path_match: str | None
    fields_from: dict[str, str]
    values: dict[str, Any]
    source_format: str


@dataclass(frozen=True)
class PluginProvenanceRecord:
    """Link one generated input plugin to exact detector evidence.

    Attributes:
        plugin_id: Stable content-derived plugin identity.
        source_format: Machine-readable payload format hint.
        human_link: Explanation suitable for operators and audit reports.
        detector_link: Stable detector URI pointing at the source query row.
        rule_name: Transform rule that selected the row.
        source_selector: Exact JSONPath-like pointer to the detector row.
        source_index: Zero-based position within the rule selection.
        properties: Normalized plugin values used by the target template.
        configuration_sha256: Digest of the normalized plugin values.
    """

    plugin_id: str
    source_format: str
    human_link: str
    detector_link: str
    rule_name: str
    source_selector: str
    source_index: int
    properties: dict[str, Any]
    configuration_sha256: str


@dataclass(frozen=True)
class AgentMapping:
    """Associate one detector transform with an agent compatibility floor.

    Attributes:
        agent_type: Stable observability-agent adapter name.
        minimum_agent_version: Lowest agent version that can use this mapping.
        definition: Normalized transform selected when the version floor matches.
        source_path: JSON mapping file retained for diagnostics.
    """

    agent_type: str
    minimum_agent_version: str
    definition: TransformDefinition
    source_path: Path


@dataclass(frozen=True)
class TransformDefinition:
    """Hold one validated, versioned detector-to-target transform.

    Attributes:
        api_version: Version of the transform-definition contract.
        name: Stable transform identifier.
        version: Semantic version of this transform definition.
        detector_name: Detector result identifier consumed by this transform.
        detector_version_constraint: Compatible detector-version range.
        target_tool: Observability tool handled by an adapter.
        target_version_constraint: Compatible target-tool version range.
        template_name: Jinja template path relative to the template root.
        template_metadata_name: Metadata path relative to the template root.
        template_version: Semantic version of the Jinja template contract.
        template_api_version: Context contract version consumed by the template.
        context_name: Jinja variable receiving normalized plugin objects.
        artifact_path: Output path relative to the output root.
        include_path: Literal path written to the orchestration include instruction.
        rules: Ordered rules used to create plugin objects.
        source_path: Definition file used to load this object.
    """

    api_version: str
    name: str
    version: str
    detector_name: str
    detector_version_constraint: str
    target_tool: str
    target_version_constraint: str
    template_name: str
    template_metadata_name: str
    template_version: str
    template_api_version: str
    context_name: str
    artifact_path: Path
    include_path: str
    rules: tuple[TransformRule, ...]
    source_path: Path


@dataclass(frozen=True)
class TemplateMetadata:
    """Describe one template's identity, contract, and supported target.

    Attributes:
        api_version: Version of the template-metadata resource contract.
        name: Stable template identity.
        version: Semantic version of the template implementation.
        engine: Rendering engine required by the template.
        template_name: Jinja file path relative to the template root.
        template_api_version: Context contract consumed by the template.
        target_tool: Supported observability tool adapter name.
        target_version_constraint: Supported target-tool version range.
        artifact_kind: Kind of configuration fragment produced.
        signals: Observability signals represented by the template.
        capabilities: Stable feature identifiers supported by the template.
        source_path: Metadata file used to load this object.
    """

    api_version: str
    name: str
    version: str
    engine: str
    template_name: str
    template_api_version: str
    target_tool: str
    target_version_constraint: str
    artifact_kind: str
    signals: tuple[str, ...]
    capabilities: tuple[str, ...]
    source_path: Path


@dataclass(frozen=True)
class GeneratorRecord:
    """Identify the application version that produced a manifest.

    Attributes:
        name: Stable application package name.
        version: Installed application semantic version.
    """

    name: str
    version: str


@dataclass(frozen=True)
class TargetRecord:
    """Identify the observability configuration target.

    Attributes:
        tool: Stable target-adapter name.
        version: Target tool version requested by the caller.
        configuration_format: Artifact syntax produced by the adapter.
        include_strategy: Adapter-specific method used to inject artifacts.
    """

    tool: str
    version: str
    configuration_format: str
    include_strategy: str


@dataclass(frozen=True)
class SourceRecord:
    """Identify and checksum the detector-result input.

    Attributes:
        detector_results_path: User-supplied detector-result path.
        sha256: SHA-256 digest of the exact source bytes.
    """

    detector_results_path: str
    sha256: str


@dataclass(frozen=True)
class TemplateTargetRecord:
    """Record the observability target declared by template metadata.

    Attributes:
        tool: Stable observability-tool adapter name.
        version_constraint: Supported tool-version range.
    """

    tool: str
    version_constraint: str


@dataclass(frozen=True)
class TemplateSupportRecord:
    """Record the behaviors and signals declared by template metadata.

    Attributes:
        artifact_kind: Kind of configuration fragment produced.
        signals: Observability signals represented by the template.
        capabilities: Stable feature identifiers supported by the template.
    """

    artifact_kind: str
    signals: tuple[str, ...]
    capabilities: tuple[str, ...]


@dataclass(frozen=True)
class TemplateRecord:
    """Identify the template and its compatibility contract.

    Attributes:
        name: Stable template identity from its metadata.
        path: Template path relative to the configured template root.
        version: Semantic version declared by the transform.
        api_version: Context API expected by the template.
        engine: Rendering engine required by the template.
        sha256: SHA-256 digest of the exact Jinja template bytes.
        metadata_path: Metadata path relative to the template root.
        metadata_api_version: Version of the metadata resource contract.
        metadata_sha256: SHA-256 digest of the exact metadata bytes.
        target: Supported observability tool and version range.
        supports: Declared artifact, signal, and rendering capabilities.
    """

    name: str
    path: str
    version: str
    api_version: str
    engine: str
    sha256: str
    metadata_path: str
    metadata_api_version: str
    metadata_sha256: str
    target: TemplateTargetRecord
    supports: TemplateSupportRecord


@dataclass(frozen=True)
class IncludeRecord:
    """Describe how a parent configuration should include an artifact.

    Attributes:
        strategy: Adapter-specific include injection strategy.
        path: Literal include path for the parent configuration.
        literal: Whether the target must receive the path without expansion.
    """

    strategy: str
    path: str
    literal: bool


@dataclass(frozen=True)
class ArtifactRecord:
    """Describe one rendered fragment and the transform that produced it.

    Attributes:
        transform_name: Stable transform definition name.
        transform_version: Semantic version of the transform definition.
        detector_name: Detector result selected by the transform.
        detector_version: Observed detector version, or an empty value when absent.
        selection_status: Reason plugins were rendered or skipped.
        path: Artifact path relative to the output root.
        sha256: Digest of the exact rendered artifact bytes.
        media_type: Target-specific artifact media type.
        plugin_count: Number of normalized plugin entries in the fragment.
        template: Versioned template identity and digest.
        include: Parent-configuration include instruction.
        plugins: Per-input links back to exact detector evidence.
    """

    transform_name: str
    transform_version: str
    detector_name: str
    detector_version: str
    selection_status: str
    path: str
    sha256: str
    media_type: str
    plugin_count: int
    template: TemplateRecord
    include: IncludeRecord
    plugins: tuple[PluginProvenanceRecord, ...]


@dataclass(frozen=True)
class OrchestrationManifest:
    """Represent the JSON handoff between rendering and parent injection.

    Attributes:
        schema_version: Version of the orchestration JSON contract.
        generated_at: UTC generation timestamp in RFC 3339 form.
        generator: Application identity used for reproducibility.
        target: Target tool and include behavior.
        source: Detector-result source identity.
        artifacts: Ordered generated artifacts and include instructions.
    """

    schema_version: str
    generated_at: str
    generator: GeneratorRecord
    target: TargetRecord
    source: SourceRecord
    artifacts: tuple[ArtifactRecord, ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a mapping whose tuples are normalized to JSON arrays.

        Returns:
            JSON-compatible mapping for schema validation and writing.
        """

        return json.loads(json.dumps(asdict(self)))
