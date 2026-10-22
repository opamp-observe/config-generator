# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Verify first-stage provenance and orchestrate semantic configuration generation."""

from __future__ import annotations

import datetime as datetime_module
import json
from pathlib import Path
from typing import Any

from config_template_transformer.constants import (
    ARTIFACTS_KEY,
    CONFIGURATION_SHA256_KEY,
    DEFAULT_SOURCE_FORMAT,
    DETECTOR_LINK_KEY,
    DETECTOR_NAME_KEY,
    DETECTOR_VERSION_KEY,
    MANIFEST_SCHEMA_RESOURCE,
    PATH_KEY,
    PLUGIN_ID_KEY,
    PLUGINS_KEY,
    PROPERTIES_KEY,
    SHA256_KEY,
    SOURCE_FORMAT_KEY,
    TARGET_KEY,
    TOOL_KEY,
    UTF8_ENCODING,
)
from config_template_transformer.errors import TransformerError
from config_template_transformer.files import (
    load_json_object,
    resolve_output_path,
    sha256_bytes,
    sha256_file,
    write_bytes_atomically,
    write_json_atomically,
)
from config_template_transformer.semantic_adapters import get_semantic_adapter
from config_template_transformer.semantic_mappings import (
    load_semantic_mapping_catalogue,
    select_semantic_mapping,
)
from config_template_transformer.semantic_models import GeneratedSemanticArtifact, SemanticPlugin
from config_template_transformer.validation import load_packaged_schema, validate_document

SEMANTIC_MANIFEST_SCHEMA_RESOURCE = "semantic_manifest.schema.json"
SEMANTIC_MANIFEST_SCHEMA_VERSION = "1.0"
GENERATED_AT_KEY = "generated_at"
MAPPINGS_KEY = "mappings"
MEDIA_TYPE_KEY = "media_type"
PLUGIN_COUNT_KEY = "plugin_count"
SCHEMA_VERSION_KEY = "schema_version"
SOURCE_KEY = "source"
DETECTOR_RESULTS_PATH_KEY = "detector_results_path"
DETECTOR_RESULTS_SHA256_KEY = "detector_results_sha256"
MAPPING_NAME_KEY = "mapping_name"
MAPPING_PATH_KEY = "mapping_path"
MAPPING_SHA256_KEY = "mapping_sha256"
MAPPING_VERSION_KEY = "mapping_version"
ORCHESTRATION_MANIFEST_PATH_KEY = "orchestration_manifest_path"
ORCHESTRATION_MANIFEST_SHA256_KEY = "orchestration_manifest_sha256"
SEMANTIC_CONVENTIONS_VERSION_KEY = "semantic_conventions_version"


class SemanticMappingOrchestrator:
    """Coordinate the optional post-transform semantic mapping stage."""

    def generate(
        self,
        orchestration_manifest_path: Path,
        detector_results_path: Path,
        output_root: Path,
        semantic_manifest_output: Path,
        mapping_root: Path | None = None,
        mapping_paths: list[Path] | None = None,
    ) -> dict[str, Any]:
        """Generate agent configuration that maps source records to semantic payloads.

        Args:
            orchestration_manifest_path: Verified first-stage manifest.
            detector_results_path: Exact detector result used by the first stage.
            output_root: Root authorized for generated semantic artifacts.
            semantic_manifest_output: Destination for the second-stage audit manifest.
            mapping_root: Optional catalogue selected automatically by plugin format.
            mapping_paths: Optional explicit files for manually controlled mappings.

        Returns:
            Validated semantic-stage manifest.

        Raises:
            TransformerError: Provenance, selection, generation, or validation fails.
        """

        orchestration_manifest = load_json_object(orchestration_manifest_path)
        validate_document(
            orchestration_manifest,
            load_packaged_schema(MANIFEST_SCHEMA_RESOURCE),
            "orchestration manifest",
        )
        expected_detector_digest = orchestration_manifest[SOURCE_KEY][SHA256_KEY]
        if sha256_file(detector_results_path) != expected_detector_digest:
            raise TransformerError(
                "Detector results do not match the source recorded by the orchestration manifest"
            )
        semantic_plugins = self._select_plugins(
            orchestration_manifest,
            load_semantic_mapping_catalogue(
                mapping_root,
                list(mapping_paths or []),
            ),
        )
        if not semantic_plugins:
            raise TransformerError("The orchestration manifest contains no mappable log plugins")
        target_tool = orchestration_manifest[TARGET_KEY][TOOL_KEY]
        adapter = get_semantic_adapter(target_tool)
        generated_artifacts = adapter.generate(semantic_plugins)
        artifact_records = self._write_artifacts(output_root, generated_artifacts)
        semantic_manifest = self._build_manifest(
            orchestration_manifest_path,
            detector_results_path,
            expected_detector_digest,
            target_tool,
            semantic_plugins,
            artifact_records,
        )
        validate_document(
            semantic_manifest,
            load_packaged_schema(SEMANTIC_MANIFEST_SCHEMA_RESOURCE),
            "semantic manifest",
        )
        write_json_atomically(semantic_manifest_output, semantic_manifest)
        return semantic_manifest

    @staticmethod
    def _write_artifacts(
        output_root: Path,
        generated_artifacts: list[GeneratedSemanticArtifact],
    ) -> list[dict[str, str]]:
        """Write generated semantic artifacts and return checksum records.

        Args:
            output_root: Root authorized for generated files.
            generated_artifacts: Adapter outputs to persist atomically.

        Returns:
            Manifest-ready path, media type, and checksum mappings.
        """

        artifact_records: list[dict[str, str]] = []
        for artifact in generated_artifacts:
            destination = resolve_output_path(output_root, artifact.path)
            write_bytes_atomically(destination, artifact.content)
            artifact_records.append(
                {
                    PATH_KEY: artifact.path.as_posix(),
                    MEDIA_TYPE_KEY: artifact.media_type,
                    SHA256_KEY: sha256_bytes(artifact.content),
                }
            )
        return artifact_records

    @staticmethod
    def _build_manifest(
        orchestration_manifest_path: Path,
        detector_results_path: Path,
        expected_detector_digest: str,
        target_tool: str,
        semantic_plugins: list[SemanticPlugin],
        artifact_records: list[dict[str, str]],
    ) -> dict[str, Any]:
        """Build the second-stage audit manifest from verified inputs.

        Args:
            orchestration_manifest_path: First-stage manifest path.
            detector_results_path: Verified detector-result path.
            expected_detector_digest: Detector digest recorded by stage one.
            target_tool: Agent implementation used for generation.
            semantic_plugins: Plugins paired with selected mappings.
            artifact_records: Checksums for persisted agent artifacts.

        Returns:
            JSON-compatible semantic-stage manifest.
        """

        return {
            SCHEMA_VERSION_KEY: SEMANTIC_MANIFEST_SCHEMA_VERSION,
            GENERATED_AT_KEY: datetime_module.datetime.now(
                datetime_module.timezone.utc
            ).isoformat(),
            TARGET_KEY: {TOOL_KEY: target_tool, PLUGIN_COUNT_KEY: len(semantic_plugins)},
            SOURCE_KEY: {
                ORCHESTRATION_MANIFEST_PATH_KEY: str(orchestration_manifest_path),
                ORCHESTRATION_MANIFEST_SHA256_KEY: sha256_file(
                    orchestration_manifest_path
                ),
                DETECTOR_RESULTS_PATH_KEY: str(detector_results_path),
                DETECTOR_RESULTS_SHA256_KEY: expected_detector_digest,
            },
            MAPPINGS_KEY: [
                {
                    PLUGIN_ID_KEY: selected.plugin[PLUGIN_ID_KEY],
                    MAPPING_NAME_KEY: selected.mapping.name,
                    MAPPING_VERSION_KEY: selected.mapping.version,
                    MAPPING_PATH_KEY: str(selected.mapping.source_path),
                    MAPPING_SHA256_KEY: sha256_file(selected.mapping.source_path),
                    SEMANTIC_CONVENTIONS_VERSION_KEY: (
                        selected.mapping.semantic_conventions_version
                    ),
                    DETECTOR_LINK_KEY: selected.plugin[DETECTOR_LINK_KEY],
                }
                for selected in semantic_plugins
            ],
            ARTIFACTS_KEY: artifact_records,
        }

    @staticmethod
    def _select_plugins(
        orchestration_manifest: dict[str, Any],
        mappings: list[Any],
    ) -> list[SemanticPlugin]:
        """Pair every explicitly formatted plugin with one compatible mapping.

        Args:
            orchestration_manifest: Schema-valid first-stage manifest.
            mappings: Loaded semantic mappings from the selected source.

        Returns:
            Ordered plugins paired with their selected semantic mappings.
        """

        semantic_plugins: list[SemanticPlugin] = []
        for artifact in orchestration_manifest[ARTIFACTS_KEY]:
            detector_name = artifact[DETECTOR_NAME_KEY]
            detector_version = artifact[DETECTOR_VERSION_KEY]
            for plugin in artifact[PLUGINS_KEY]:
                plugin_identity = json.dumps(
                    plugin[PROPERTIES_KEY],
                    ensure_ascii=False,
                    separators=(",", ":"),
                    sort_keys=True,
                ).encode(UTF8_ENCODING)
                if sha256_bytes(plugin_identity) != plugin[CONFIGURATION_SHA256_KEY]:
                    raise TransformerError(
                        f"Plugin provenance digest changed: {plugin[PLUGIN_ID_KEY]}"
                    )
                if plugin[SOURCE_FORMAT_KEY] == DEFAULT_SOURCE_FORMAT:
                    continue
                mapping = select_semantic_mapping(
                    mappings,
                    detector_name,
                    detector_version,
                    plugin,
                )
                semantic_plugins.append(
                    SemanticPlugin(
                        detector_name=detector_name,
                        detector_version=detector_version,
                        plugin=plugin,
                        mapping=mapping,
                    )
                )
        return semantic_plugins
