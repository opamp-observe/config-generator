# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Load, validate, and select declarative OpenTelemetry semantic mappings."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from config_template_transformer.constants import (
    DETECTOR_KEY,
    NAME_KEY,
    PATH_KEY,
    PLUGIN_ID_KEY,
    PROPERTIES_KEY,
    SOURCE_FORMAT_KEY,
    SPEC_KEY,
    VERSION_CONSTRAINT_KEY,
    VERSION_KEY,
)
from config_template_transformer.errors import TransformerError
from config_template_transformer.files import load_json_object
from config_template_transformer.semantic_models import SemanticMapping
from config_template_transformer.validation import load_packaged_schema, validate_document

SEMANTIC_MAPPING_SCHEMA_RESOURCE = "semantic_mapping.schema.json"
BODY_FROM_KEY = "body_from"
FIELD_MAPPINGS_KEY = "field_mappings"
FORMATS_KEY = "formats"
METADATA_KEY = "metadata"
PARSE_KEY = "parse"
PATH_REGEX_KEY = "path_regex"
PAYLOAD_KEY = "payload"
PRIORITY_KEY = "priority"
RECORD_ATTRIBUTES_KEY = "record_attributes"
RESOURCE_ATTRIBUTES_KEY = "resource_attributes"
SEMANTIC_CONVENTIONS_KEY = "semantic_conventions"
SOURCE_KEY = "source"


def load_semantic_mapping(mapping_path: Path) -> SemanticMapping:
    """Load and normalize one schema-valid semantic mapping.

    Args:
        mapping_path: JSON mapping document to validate.

    Returns:
        Immutable semantic mapping.

    Raises:
        TransformerError: Schema, version, or regular-expression data is invalid.
    """

    document = load_json_object(mapping_path)
    validate_document(
        document,
        load_packaged_schema(SEMANTIC_MAPPING_SCHEMA_RESOURCE),
        f"semantic mapping {mapping_path}",
    )
    metadata = document[METADATA_KEY]
    specification = document[SPEC_KEY]
    detector = specification[DETECTOR_KEY]
    source = specification[SOURCE_KEY]
    payload = specification[PAYLOAD_KEY]
    _parse_version(metadata[VERSION_KEY], f"mapping version in {mapping_path}")
    _parse_specifier(
        detector[VERSION_CONSTRAINT_KEY],
        f"detector version constraint in {mapping_path}",
    )
    path_regex = source.get(PATH_REGEX_KEY)
    if path_regex is not None:
        try:
            re.compile(path_regex)
        except re.error as error:
            raise TransformerError(
                f"Invalid path regular expression in {mapping_path}: {error}"
            ) from error
    return SemanticMapping(
        name=metadata[NAME_KEY],
        version=metadata[VERSION_KEY],
        detector_name=detector[NAME_KEY],
        detector_version_constraint=detector[VERSION_CONSTRAINT_KEY],
        source_formats=tuple(source[FORMATS_KEY]),
        path_regex=path_regex,
        priority=source.get(PRIORITY_KEY, 0),
        semantic_conventions_version=specification[SEMANTIC_CONVENTIONS_KEY][VERSION_KEY],
        parse=dict(specification[PARSE_KEY]),
        body_from=payload[BODY_FROM_KEY],
        field_mappings=dict(payload[FIELD_MAPPINGS_KEY]),
        resource_attributes=dict(payload[RESOURCE_ATTRIBUTES_KEY]),
        record_attributes=dict(payload[RECORD_ATTRIBUTES_KEY]),
        source_path=mapping_path,
    )


def load_semantic_mapping_catalogue(
    mapping_root: Path | None,
    mapping_paths: list[Path],
) -> list[SemanticMapping]:
    """Load explicit mappings or every mapping beneath a catalogue root.

    Args:
        mapping_root: Optional root recursively containing JSON mappings.
        mapping_paths: Explicit mapping files used for manual selection.

    Returns:
        Deterministically ordered semantic mappings.

    Raises:
        TransformerError: Sources are mixed, missing, or empty.
    """

    if mapping_root is not None and mapping_paths:
        raise TransformerError("Use explicit semantic mappings or a mapping root, not both")
    if mapping_root is not None:
        resolved_root = mapping_root.resolve()
        if not resolved_root.is_dir():
            raise TransformerError(f"Semantic mapping root is not a directory: {mapping_root}")
        mapping_paths = sorted(resolved_root.rglob("*.json"))
    if not mapping_paths:
        raise TransformerError("At least one semantic mapping is required")
    return sorted(
        (load_semantic_mapping(mapping_path) for mapping_path in mapping_paths),
        key=lambda mapping: (mapping.detector_name, mapping.name, mapping.version),
    )


def select_semantic_mapping(
    mappings: list[SemanticMapping],
    detector_name: str,
    detector_version: str,
    plugin: dict[str, Any],
) -> SemanticMapping:
    """Select one highest-priority mapping for a verified plugin record.

    Args:
        mappings: Candidate catalogue or manually supplied mapping set.
        detector_name: Detector identity from the first-stage artifact.
        detector_version: Exact detector version from the first-stage artifact.
        plugin: Per-plugin provenance record containing format and properties.

    Returns:
        Unique compatible mapping with the highest declared priority.

    Raises:
        TransformerError: No mapping matches or the highest priority is ambiguous.
    """

    version_value = _parse_version(detector_version, f"detector version for {detector_name}")
    source_format = str(plugin[SOURCE_FORMAT_KEY])
    properties = plugin[PROPERTIES_KEY]
    plugin_path = str(properties.get(PATH_KEY, ""))
    candidates = [
        mapping
        for mapping in mappings
        if mapping.detector_name == detector_name
        and version_value in SpecifierSet(mapping.detector_version_constraint)
        and source_format in mapping.source_formats
        and (mapping.path_regex is None or re.search(mapping.path_regex, plugin_path) is not None)
    ]
    if not candidates:
        raise TransformerError(
            f"No semantic mapping matches plugin {plugin[PLUGIN_ID_KEY]} "
            f"({detector_name} {source_format}, path {plugin_path!r})"
        )
    highest_priority = max(mapping.priority for mapping in candidates)
    selected = [mapping for mapping in candidates if mapping.priority == highest_priority]
    if len(selected) != 1:
        names = ", ".join(mapping.name for mapping in selected)
        raise TransformerError(
            f"Semantic mappings are ambiguous for plugin {plugin[PLUGIN_ID_KEY]}: {names}"
        )
    return selected[0]


def _parse_version(value: str, description: str) -> Version:
    """Parse one version value and provide a component-level diagnostic.

    Args:
        value: Version text to parse.
        description: Human-readable field description.

    Returns:
        Parsed version.

    Raises:
        TransformerError: The value is not PEP 440 compatible.
    """

    try:
        return Version(value)
    except InvalidVersion as error:
        raise TransformerError(f"Invalid {description}: {value}") from error


def _parse_specifier(value: str, description: str) -> SpecifierSet:
    """Parse one version constraint and provide a component-level diagnostic.

    Args:
        value: Constraint text to parse.
        description: Human-readable field description.

    Returns:
        Parsed constraint set.

    Raises:
        TransformerError: The constraint is invalid.
    """

    try:
        return SpecifierSet(value)
    except InvalidSpecifier as error:
        raise TransformerError(f"Invalid {description}: {value}") from error
