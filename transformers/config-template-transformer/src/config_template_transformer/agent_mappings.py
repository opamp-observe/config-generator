# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Load and select external detector-to-agent JSON mapping configurations."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

from config_template_transformer.constants import (
    AGENT_KEY,
    AGENT_MAPPING_SCHEMA_RESOURCE,
    API_VERSION_KEY,
    DETECTOR_KEY,
    KIND_KEY,
    METADATA_KEY,
    MINIMUM_VERSION_KEY,
    OUTPUT_KEY,
    RENDER_KEY,
    RULES_KEY,
    SPEC_KEY,
    TARGET_KEY,
    TOOL_KEY,
    TRANSFORM_API_VERSION,
    TRANSFORM_KIND,
    TYPE_KEY,
    VERSION_CONSTRAINT_KEY,
)
from config_template_transformer.definitions import build_transform_definition
from config_template_transformer.errors import TransformerError
from config_template_transformer.files import load_json_object
from config_template_transformer.models import AgentMapping, TransformDefinition
from config_template_transformer.validation import load_packaged_schema, validate_document


def load_agent_mapping(mapping_path: Path) -> AgentMapping:
    """Load, validate, and normalize one agent mapping JSON document.

    Args:
        mapping_path: JSON mapping configuration to load.

    Returns:
        Validated mapping with its reusable transform definition.

    Raises:
        TransformerError: JSON, schema, version, or path values are invalid.
    """

    document = load_json_object(mapping_path)
    validate_document(
        document,
        load_packaged_schema(AGENT_MAPPING_SCHEMA_RESOURCE),
        f"agent mapping {mapping_path}",
    )
    specification = document[SPEC_KEY]
    agent = specification[AGENT_KEY]
    minimum_version = agent[MINIMUM_VERSION_KEY]
    _parse_version(minimum_version, f"minimum agent version in {mapping_path}")
    transform_document: dict[str, Any] = {
        API_VERSION_KEY: TRANSFORM_API_VERSION,
        KIND_KEY: TRANSFORM_KIND,
        METADATA_KEY: document[METADATA_KEY],
        SPEC_KEY: {
            DETECTOR_KEY: specification[DETECTOR_KEY],
            TARGET_KEY: {
                TOOL_KEY: agent[TYPE_KEY],
                VERSION_CONSTRAINT_KEY: f">={minimum_version}",
            },
            OUTPUT_KEY: specification[OUTPUT_KEY],
            RENDER_KEY: specification[RENDER_KEY],
            RULES_KEY: specification[RULES_KEY],
        },
    }
    definition = build_transform_definition(transform_document, mapping_path)
    return AgentMapping(
        agent_type=agent[TYPE_KEY],
        minimum_agent_version=minimum_version,
        definition=definition,
        source_path=mapping_path,
    )


def select_agent_mapping_definitions(
    mapping_root: Path,
    detector_names: set[str],
    agent_type: str,
    agent_version: Version,
) -> list[TransformDefinition]:
    """Select the newest compatible mapping floor for every detected product.

    Args:
        mapping_root: Directory recursively containing JSON mapping files.
        detector_names: Detector identifiers present in the input document.
        agent_type: Requested observability-agent adapter name.
        agent_version: Parsed installed or intended agent version.

    Returns:
        Deterministically ordered transform definitions, one per mapped detector.

    Raises:
        TransformerError: The catalogue is missing, empty, ambiguous, or incompatible.
    """

    candidates_by_detector = _load_compatible_candidates(
        mapping_root,
        detector_names,
        agent_type,
        agent_version,
    )

    selected_definitions: list[TransformDefinition] = []
    for detector_name, candidates in sorted(candidates_by_detector.items()):
        if not candidates:
            raise TransformerError(
                f"No mappings support {agent_type} {agent_version} for detector {detector_name}"
            )
        highest_minimum_version = max(minimum_version for minimum_version, _ in candidates)
        best_mappings = [
            mapping
            for minimum_version, mapping in candidates
            if minimum_version == highest_minimum_version
        ]
        if len(best_mappings) != 1:
            mapping_paths_text = ", ".join(
                str(mapping.source_path) for mapping in best_mappings
            )
            raise TransformerError(
                f"Multiple {agent_type} mappings for {detector_name} have minimum version "
                f"{highest_minimum_version}: {mapping_paths_text}"
            )
        selected_definitions.append(best_mappings[0].definition)

    if not selected_definitions:
        raise TransformerError(
            f"No mappings support {agent_type} {agent_version} for the supplied detectors"
        )
    return selected_definitions


def _load_compatible_candidates(
    mapping_root: Path,
    detector_names: set[str],
    agent_type: str,
    agent_version: Version,
) -> dict[str, list[tuple[Version, AgentMapping]]]:
    """Load mapping files and group those compatible with the request.

    Args:
        mapping_root: Directory recursively containing mapping resources.
        detector_names: Detector identities available in the input.
        agent_type: Requested observability agent type.
        agent_version: Requested installed or intended agent version.

    Returns:
        Compatible candidates grouped by detector identity.

    Raises:
        TransformerError: The catalogue root is absent or contains no JSON files.
    """

    resolved_root = mapping_root.resolve()
    if not resolved_root.is_dir():
        raise TransformerError(f"Agent mapping root is not a directory: {mapping_root}")
    mapping_paths = sorted(resolved_root.rglob("*.json"))
    if not mapping_paths:
        raise TransformerError(f"No agent mapping JSON files found below {mapping_root}")

    candidates_by_detector: dict[str, list[tuple[Version, AgentMapping]]] = defaultdict(list)
    for mapping_path in mapping_paths:
        mapping = load_agent_mapping(mapping_path)
        detector_name = mapping.definition.detector_name
        if mapping.agent_type != agent_type or detector_name not in detector_names:
            continue
        candidates_by_detector.setdefault(detector_name, [])
        minimum_version = _parse_version(
            mapping.minimum_agent_version,
            f"minimum agent version in {mapping.source_path}",
        )
        if minimum_version <= agent_version:
            candidates_by_detector[detector_name].append((minimum_version, mapping))
    return candidates_by_detector


def _parse_version(value: str, description: str) -> Version:
    """Parse one mapping version with a component-specific error.

    Args:
        value: Version string to parse.
        description: Field description used in an error.

    Returns:
        Parsed PEP 440 version.

    Raises:
        TransformerError: The value is not a valid version.
    """

    try:
        return Version(value)
    except InvalidVersion as error:
        raise TransformerError(f"Invalid {description}: {value}") from error
