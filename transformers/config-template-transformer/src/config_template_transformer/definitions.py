# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Load and validate versioned YAML transform definitions."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from ruamel.yaml import YAML, YAMLError

from config_template_transformer.constants import (
    API_VERSION_KEY,
    CONTEXT_NAME_KEY,
    DETECTOR_KEY,
    FIELDS_FROM_KEY,
    FOR_EACH_KEY,
    INCLUDE_PATH_KEY,
    METADATA_FILE_KEY,
    METADATA_KEY,
    NAME_KEY,
    OUTPUT_KEY,
    PATH_FROM_KEY,
    PATH_KEY,
    RENDER_KEY,
    RULES_KEY,
    SPEC_KEY,
    TARGET_KEY,
    TEMPLATE_API_VERSION_KEY,
    TEMPLATE_KEY,
    TOOL_KEY,
    TRANSFORM_SCHEMA_RESOURCE,
    UTF8_ENCODING,
    VALUES_KEY,
    VERSION_CONSTRAINT_KEY,
    VERSION_KEY,
)
from config_template_transformer.errors import TransformerError
from config_template_transformer.models import TransformDefinition, TransformRule
from config_template_transformer.validation import load_packaged_schema, validate_document


def load_transform_definition(definition_path: Path) -> TransformDefinition:
    """Load, schema-check, and normalize one YAML transform definition.

    Args:
        definition_path: YAML definition to load.

    Returns:
        Immutable normalized transform definition.

    Raises:
        TransformerError: YAML, schema, path, or version values are invalid.
    """

    yaml_parser = YAML(typ="safe")
    try:
        loaded_value = yaml_parser.load(definition_path.read_text(encoding=UTF8_ENCODING))
    except (OSError, YAMLError) as error:
        raise TransformerError(f"Unable to load transform {definition_path}: {error}") from error
    if not isinstance(loaded_value, dict):
        raise TransformerError(f"Transform definition must be a mapping: {definition_path}")
    validate_document(
        loaded_value,
        load_packaged_schema(TRANSFORM_SCHEMA_RESOURCE),
        f"transform definition {definition_path}",
    )
    return build_transform_definition(loaded_value, definition_path)


def build_transform_definition(
    document: dict[str, Any],
    definition_path: Path,
) -> TransformDefinition:
    """Convert a schema-valid transform mapping into an immutable definition.

    Args:
        document: Schema-valid transform mapping.
        definition_path: Source path retained for diagnostics.

    Returns:
        Normalized definition used by the orchestrator.
    """

    metadata = document[METADATA_KEY]
    specification = document[SPEC_KEY]
    detector = specification[DETECTOR_KEY]
    target = specification[TARGET_KEY]
    output = specification[OUTPUT_KEY]
    render = specification[RENDER_KEY]
    _validate_version(metadata[VERSION_KEY], "transform version")
    _validate_version(render[VERSION_KEY], "template version")
    _validate_specifier(detector[VERSION_CONSTRAINT_KEY], "detector version constraint")
    _validate_specifier(target[VERSION_CONSTRAINT_KEY], "target version constraint")
    artifact_path = _validate_relative_path(Path(output[PATH_KEY]), "artifact path")
    _validate_relative_path(PurePosixPath(render[TEMPLATE_KEY]), "template path")
    _validate_relative_path(PurePosixPath(render[METADATA_FILE_KEY]), "template metadata path")

    rules = tuple(
        TransformRule(
            name=rule[NAME_KEY],
            for_each=rule[FOR_EACH_KEY],
            path_from=rule.get(PATH_FROM_KEY),
            fields_from=dict(rule.get(FIELDS_FROM_KEY, {})),
            values=dict(rule[VALUES_KEY]),
        )
        for rule in specification[RULES_KEY]
    )
    return TransformDefinition(
        api_version=document[API_VERSION_KEY],
        name=metadata[NAME_KEY],
        version=metadata[VERSION_KEY],
        detector_name=detector[NAME_KEY],
        detector_version_constraint=detector[VERSION_CONSTRAINT_KEY],
        target_tool=target[TOOL_KEY],
        target_version_constraint=target[VERSION_CONSTRAINT_KEY],
        template_name=render[TEMPLATE_KEY],
        template_metadata_name=render[METADATA_FILE_KEY],
        template_version=render[VERSION_KEY],
        template_api_version=render[TEMPLATE_API_VERSION_KEY],
        context_name=render[CONTEXT_NAME_KEY],
        artifact_path=artifact_path,
        include_path=output[INCLUDE_PATH_KEY],
        rules=rules,
        source_path=definition_path,
    )


def _validate_version(value: str, description: str) -> None:
    """Require one PEP 440-compatible semantic version.

    Args:
        value: Version text to parse.
        description: Field name included in an error.

    Raises:
        TransformerError: The value cannot be parsed as a version.
    """

    try:
        Version(value)
    except InvalidVersion as error:
        raise TransformerError(f"Invalid {description}: {value}") from error


def _validate_specifier(value: str, description: str) -> None:
    """Require one PEP 440-compatible version constraint.

    Args:
        value: Specifier text to parse.
        description: Field name included in an error.

    Raises:
        TransformerError: The value cannot be parsed as a specifier.
    """

    try:
        SpecifierSet(value)
    except InvalidSpecifier as error:
        raise TransformerError(f"Invalid {description}: {value}") from error


def _validate_relative_path(
    path_value: Path | PurePosixPath,
    description: str,
) -> Path | PurePosixPath:
    """Reject absolute paths and parent traversal in definition-owned paths.

    Args:
        path_value: Artifact or template path supplied by a definition.
        description: Field name included in an error.

    Returns:
        The unchanged safe path.

    Raises:
        TransformerError: The path is absolute or includes parent traversal.
    """

    if path_value.is_absolute() or ".." in path_value.parts:
        raise TransformerError(f"{description.capitalize()} must stay relative: {path_value}")
    return path_value
