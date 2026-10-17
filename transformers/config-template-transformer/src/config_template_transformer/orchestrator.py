# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Tool-neutral selection and Jinja transformation orchestration."""

from __future__ import annotations

import datetime as datetime_module
import json
import logging
from pathlib import Path
from typing import Any

import jsonpath_rfc9535 as jsonpath
from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from config_template_transformer import APPLICATION_NAME, APPLICATION_VERSION
from config_template_transformer.adapters import TargetAdapter, get_target_adapter
from config_template_transformer.constants import (
    ARTIFACTS_KEY,
    DEFAULT_MAX_PLUGIN_COUNT,
    DETECTED_KEY,
    DETECTOR_NAME_KEY,
    DETECTOR_VERSION_KEY,
    DETECTORS_KEY,
    ERRORS_KEY,
    INCLUDE_KEY,
    LITERAL_KEY,
    MANIFEST_SCHEMA_RESOURCE,
    PATH_KEY,
    SCHEMA_VERSION,
    SELECTION_DETECTOR_ERRORS,
    SELECTION_DETECTOR_NOT_DETECTED,
    SELECTION_DETECTOR_NOT_FOUND,
    SELECTION_RENDERED,
    SHA256_KEY,
    STRATEGY_KEY,
    TARGET_KEY,
    TOOL_KEY,
)
from config_template_transformer.definitions import load_transform_definition
from config_template_transformer.errors import TransformerError
from config_template_transformer.files import (
    load_json_object,
    resolve_output_path,
    sha256_bytes,
    sha256_file,
    write_bytes_atomically,
    write_json_atomically,
)
from config_template_transformer.models import (
    ArtifactRecord,
    GeneratorRecord,
    IncludeRecord,
    OrchestrationManifest,
    SourceRecord,
    TargetRecord,
    TemplateMetadata,
    TemplateRecord,
    TemplateSupportRecord,
    TemplateTargetRecord,
    TransformDefinition,
)
from config_template_transformer.renderer import JinjaFragmentRenderer
from config_template_transformer.template_metadata import load_template_metadata
from config_template_transformer.validation import (
    load_packaged_schema,
    validate_document,
    validate_external_schema,
)

LOGGER = logging.getLogger(__name__)


class TransformationOrchestrator:
    """Coordinate definitions, detector selection, rendering, and manifests.

    Attributes:
        renderer: Reusable sandboxed Jinja renderer.
        max_plugin_count: Maximum normalized plugins allowed per artifact.
    """

    def __init__(
        self,
        template_root: Path,
        max_plugin_count: int = DEFAULT_MAX_PLUGIN_COUNT,
    ) -> None:
        """Create an orchestrator for one approved template root.

        Args:
            template_root: Directory containing Jinja templates.
            max_plugin_count: Maximum plugins emitted by one transform.
        """

        self.renderer = JinjaFragmentRenderer(
            template_root=template_root,
            max_plugin_count=max_plugin_count,
        )
        self.max_plugin_count = max_plugin_count

    def render(
        self,
        detector_results_path: Path,
        definition_paths: list[Path],
        output_root: Path,
        manifest_output: Path,
        target_version: str,
        detector_schema_path: Path | None = None,
    ) -> OrchestrationManifest:
        """Render all definitions and write their JSON orchestration manifest.

        Args:
            detector_results_path: Aggregate detector-result JSON input.
            definition_paths: YAML transform definitions to apply.
            output_root: Root directory authorized for fragment artifacts.
            manifest_output: JSON manifest output path.
            target_version: Installed or intended target-tool version.
            detector_schema_path: Optional aggregate detector JSON Schema.

        Returns:
            Validated manifest describing every artifact and include instruction.

        Raises:
            TransformerError: Inputs, versions, selections, or rendering are invalid.
        """

        if not definition_paths:
            raise TransformerError("At least one transform definition is required")
        detector_results = load_json_object(detector_results_path)
        validate_external_schema(detector_results, detector_schema_path)
        detector_entries = detector_results.get(DETECTORS_KEY)
        if not isinstance(detector_entries, list):
            raise TransformerError("Detector results must contain a detectors array")

        definitions = sorted(
            (load_transform_definition(path) for path in definition_paths),
            key=lambda definition: definition.name,
        )
        adapter = self._resolve_common_adapter(definitions)
        target_version_value = self._parse_version(target_version, "target version")
        artifacts = tuple(
            self._render_definition(
                definition=definition,
                detector_entries=detector_entries,
                output_root=output_root,
                adapter=adapter,
                target_version=target_version_value,
            )
            for definition in definitions
        )
        manifest = OrchestrationManifest(
            schema_version=SCHEMA_VERSION,
            generated_at=datetime_module.datetime.now(datetime_module.timezone.utc).isoformat(),
            generator=GeneratorRecord(name=APPLICATION_NAME, version=APPLICATION_VERSION),
            target=TargetRecord(
                tool=adapter.tool_name,
                version=str(target_version_value),
                configuration_format=adapter.configuration_format,
                include_strategy=adapter.include_strategy,
            ),
            source=SourceRecord(
                detector_results_path=str(detector_results_path),
                sha256=sha256_file(detector_results_path),
            ),
            artifacts=artifacts,
        )
        manifest_document = manifest.to_dict()
        validate_document(
            manifest_document,
            load_packaged_schema(MANIFEST_SCHEMA_RESOURCE),
            "orchestration manifest",
        )
        write_json_atomically(manifest_output, manifest_document)
        LOGGER.debug("Wrote orchestration manifest to %s", manifest_output)
        return manifest

    def _render_definition(
        self,
        definition: TransformDefinition,
        detector_entries: list[Any],
        output_root: Path,
        adapter: TargetAdapter,
        target_version: Version,
    ) -> ArtifactRecord:
        """Render one definition into an artifact record and file.

        Args:
            definition: Validated transform definition.
            detector_entries: Aggregate detector results available for selection.
            output_root: Root directory authorized for fragment output.
            adapter: Target adapter that validates and serializes the fragment.
            target_version: Parsed target version checked against the definition.

        Returns:
            Artifact provenance and include record for the manifest.
        """

        if target_version not in SpecifierSet(definition.target_version_constraint):
            raise TransformerError(
                f"Target {adapter.tool_name} {target_version} does not satisfy "
                f"{definition.target_version_constraint} for {definition.name}"
            )
        metadata_path = self.renderer.template_path(definition.template_metadata_name)
        template_metadata = load_template_metadata(metadata_path)
        self._validate_template_compatibility(
            definition,
            template_metadata,
            target_version,
        )
        detector_entry, selection_status = self._select_detector(
            definition,
            detector_entries,
        )
        plugins: list[dict[str, Any]] = []
        if detector_entry is not None:
            if selection_status == SELECTION_RENDERED:
                plugins = self._build_plugins(definition, detector_entry)

        fragment = self.renderer.render(
            template_name=definition.template_name,
            context_name=definition.context_name,
            plugins=plugins,
        )
        artifact_bytes = adapter.serialize_fragment(fragment, definition)
        destination = resolve_output_path(output_root, definition.artifact_path)
        write_bytes_atomically(destination, artifact_bytes)
        template_path = self.renderer.template_path(definition.template_name)
        LOGGER.debug(
            "Rendered %s plugins for %s to %s",
            len(plugins),
            definition.name,
            destination,
        )
        return ArtifactRecord(
            transform_name=definition.name,
            transform_version=definition.version,
            detector_name=definition.detector_name,
            detector_version=(
                str(detector_entry[DETECTOR_VERSION_KEY]) if detector_entry is not None else ""
            ),
            selection_status=selection_status,
            path=definition.artifact_path.as_posix(),
            sha256=sha256_bytes(artifact_bytes),
            media_type=adapter.media_type,
            plugin_count=len(plugins),
            template=TemplateRecord(
                name=template_metadata.name,
                path=definition.template_name,
                version=definition.template_version,
                api_version=definition.template_api_version,
                engine=template_metadata.engine,
                sha256=sha256_file(template_path),
                metadata_path=definition.template_metadata_name,
                metadata_api_version=template_metadata.api_version,
                metadata_sha256=sha256_file(metadata_path),
                target=TemplateTargetRecord(
                    tool=template_metadata.target_tool,
                    version_constraint=template_metadata.target_version_constraint,
                ),
                supports=TemplateSupportRecord(
                    artifact_kind=template_metadata.artifact_kind,
                    signals=template_metadata.signals,
                    capabilities=template_metadata.capabilities,
                ),
            ),
            include=IncludeRecord(
                strategy=adapter.include_strategy,
                path=definition.include_path,
                literal=True,
            ),
        )

    @staticmethod
    def _validate_template_compatibility(
        definition: TransformDefinition,
        metadata: TemplateMetadata,
        target_version: Version,
    ) -> None:
        """Require transform declarations to agree with template metadata.

        Args:
            definition: Transform selecting the template and target.
            metadata: Independently validated template sidecar.
            target_version: Installed or intended observability-tool version.

        Raises:
            TransformerError: Template identity, API, tool, or version is incompatible.
        """

        expected_values = (
            ("template path", definition.template_name, metadata.template_name),
            ("template version", definition.template_version, metadata.version),
            (
                "template API version",
                definition.template_api_version,
                metadata.template_api_version,
            ),
            ("target tool", definition.target_tool, metadata.target_tool),
        )
        for description, declared_value, metadata_value in expected_values:
            if declared_value != metadata_value:
                raise TransformerError(
                    f"Transform {definition.name} {description} '{declared_value}' "
                    f"does not match template metadata '{metadata_value}'"
                )
        if target_version not in SpecifierSet(metadata.target_version_constraint):
            raise TransformerError(
                f"Template {metadata.name} does not support {metadata.target_tool} "
                f"{target_version}; supported versions are "
                f"{metadata.target_version_constraint}"
            )

    def _select_detector(
        self,
        definition: TransformDefinition,
        detector_entries: list[Any],
    ) -> tuple[dict[str, Any] | None, str]:
        """Select one compatible detector result and classify its usability.

        Args:
            definition: Transform declaring detector identity and compatibility.
            detector_entries: Untrusted entries from the aggregate detector array.

        Returns:
            Selected detector mapping, if present, and its selection status.

        Raises:
            TransformerError: Multiple results match or the version is incompatible.
        """

        matches = [
            entry
            for entry in detector_entries
            if isinstance(entry, dict) and entry.get(DETECTOR_NAME_KEY) == definition.detector_name
        ]
        if not matches:
            return None, SELECTION_DETECTOR_NOT_FOUND
        if len(matches) > 1:
            raise TransformerError(f"Multiple detector results match {definition.detector_name}")
        detector_entry = matches[0]
        detector_version = self._parse_version(
            str(detector_entry.get(DETECTOR_VERSION_KEY, "")),
            f"detector version for {definition.detector_name}",
        )
        if detector_version not in SpecifierSet(definition.detector_version_constraint):
            raise TransformerError(
                f"Detector {definition.detector_name} {detector_version} does not satisfy "
                f"{definition.detector_version_constraint}"
            )
        if detector_entry.get(DETECTED_KEY) is not True:
            return detector_entry, SELECTION_DETECTOR_NOT_DETECTED
        detector_errors = detector_entry.get(ERRORS_KEY, [])
        if detector_errors:
            return detector_entry, SELECTION_DETECTOR_ERRORS
        return detector_entry, SELECTION_RENDERED

    def _build_plugins(
        self,
        definition: TransformDefinition,
        detector_entry: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Evaluate RFC 9535 rules and deterministically deduplicate plugins.

        Args:
            definition: Transform containing ordered selection rules.
            detector_entry: Compatible detected product result.

        Returns:
            Ordered JSON-compatible plugin mappings.

        Raises:
            TransformerError: JSONPath evaluation fails or exceeds the safety limit.
        """

        plugins: list[dict[str, Any]] = []
        seen_identities: set[str] = set()
        try:
            for rule in definition.rules:
                source_nodes = jsonpath.find(rule.for_each, detector_entry)
                for source_node in source_nodes:
                    path_nodes = jsonpath.find(rule.path_from, source_node.value)
                    for path_node in path_nodes:
                        if not isinstance(path_node.value, str) or not path_node.value.strip():
                            continue
                        plugin = dict(rule.values)
                        plugin[PATH_KEY] = path_node.value.strip()
                        identity = json.dumps(
                            plugin,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            sort_keys=True,
                        )
                        if identity in seen_identities:
                            continue
                        seen_identities.add(identity)
                        plugins.append(plugin)
                        if len(plugins) > self.max_plugin_count:
                            raise TransformerError(
                                f"Transform {definition.name} exceeds plugin limit "
                                f"{self.max_plugin_count}"
                            )
        except jsonpath.JSONPathError as error:
            raise TransformerError(
                f"JSONPath evaluation failed for transform {definition.name}: {error}"
            ) from error
        return plugins

    @staticmethod
    def _resolve_common_adapter(
        definitions: list[TransformDefinition],
    ) -> TargetAdapter:
        """Require one target tool per manifest and return its adapter.

        Args:
            definitions: Definitions included in one render operation.

        Returns:
            Registered adapter shared by all definitions.

        Raises:
            TransformerError: Definitions mix target tools.
        """

        target_tools = {definition.target_tool for definition in definitions}
        if len(target_tools) != 1:
            raise TransformerError("One orchestration manifest cannot mix target tools")
        return get_target_adapter(target_tools.pop())

    @staticmethod
    def _parse_version(value: str, description: str) -> Version:
        """Parse one version and translate packaging errors for the CLI.

        Args:
            value: Version string to parse.
            description: Human-readable field name used in an error.

        Returns:
            Parsed PEP 440 version.

        Raises:
            TransformerError: The version string is invalid.
        """

        try:
            return Version(value)
        except InvalidVersion as error:
            raise TransformerError(f"Invalid {description}: {value}") from error


def inject_manifest_includes(
    manifest_path: Path,
    parent_path: Path,
    output_path: Path,
    artifact_root: Path | None = None,
) -> None:
    """Verify a manifest and inject its includes into a parent configuration.

    Args:
        manifest_path: Orchestration JSON produced by the render command.
        parent_path: Existing target parent configuration.
        output_path: Destination for the updated parent configuration.
        artifact_root: Optional root used to verify artifact paths and hashes.

    Raises:
        TransformerError: Manifest, artifacts, or target include behavior are invalid.
    """

    manifest = load_json_object(manifest_path)
    validate_document(
        manifest,
        load_packaged_schema(MANIFEST_SCHEMA_RESOURCE),
        "orchestration manifest",
    )
    target = manifest[TARGET_KEY]
    adapter = get_target_adapter(target[TOOL_KEY])
    resolved_artifact_root = (artifact_root or manifest_path.parent).resolve()
    include_paths: list[str] = []
    for artifact in manifest[ARTIFACTS_KEY]:
        include = artifact[INCLUDE_KEY]
        if include[STRATEGY_KEY] != adapter.include_strategy or include[LITERAL_KEY] is not True:
            raise TransformerError("Manifest include instruction does not match target adapter")
        artifact_path = resolve_output_path(resolved_artifact_root, Path(artifact[PATH_KEY]))
        if not artifact_path.is_file() or sha256_file(artifact_path) != artifact[SHA256_KEY]:
            raise TransformerError(f"Generated artifact is missing or changed: {artifact_path}")
        include_paths.append(include[PATH_KEY])
    adapter.inject_includes(parent_path, include_paths, output_path)
    LOGGER.debug("Injected %s includes into %s", len(include_paths), output_path)
