# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Load and validate template identity and compatibility metadata."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version
from ruamel.yaml import YAML, YAMLError

from config_template_transformer.constants import (
    API_VERSION_KEY,
    ARTIFACT_KIND_KEY,
    CAPABILITIES_KEY,
    ENGINE_KEY,
    METADATA_KEY,
    NAME_KEY,
    SIGNALS_KEY,
    SPEC_KEY,
    SUPPORTS_KEY,
    TARGET_KEY,
    TEMPLATE_API_VERSION_KEY,
    TEMPLATE_KEY,
    TEMPLATE_METADATA_SCHEMA_RESOURCE,
    TOOL_KEY,
    UTF8_ENCODING,
    VERSION_CONSTRAINT_KEY,
    VERSION_KEY,
)
from config_template_transformer.errors import TransformerError
from config_template_transformer.models import TemplateMetadata
from config_template_transformer.validation import load_packaged_schema, validate_document


def load_template_metadata(metadata_path: Path) -> TemplateMetadata:
    """Load and normalize one template metadata sidecar.

    Args:
        metadata_path: YAML metadata resource located in the approved template root.

    Returns:
        Immutable metadata used for compatibility enforcement and provenance.

    Raises:
        TransformerError: YAML, schema, path, or version fields are invalid.
    """

    yaml_parser = YAML(typ="safe")
    try:
        loaded_value = yaml_parser.load(metadata_path.read_text(encoding=UTF8_ENCODING))
    except (OSError, YAMLError) as error:
        raise TransformerError(
            f"Unable to load template metadata {metadata_path}: {error}"
        ) from error
    if not isinstance(loaded_value, dict):
        raise TransformerError(f"Template metadata must be a mapping: {metadata_path}")
    validate_document(
        loaded_value,
        load_packaged_schema(TEMPLATE_METADATA_SCHEMA_RESOURCE),
        f"template metadata {metadata_path}",
    )
    return _build_template_metadata(loaded_value, metadata_path)


def _build_template_metadata(
    document: dict[str, Any],
    metadata_path: Path,
) -> TemplateMetadata:
    """Convert schema-valid metadata into its immutable representation.

    Args:
        document: Schema-valid template metadata mapping.
        metadata_path: Source path retained for provenance and diagnostics.

    Returns:
        Normalized template metadata.
    """

    metadata = document[METADATA_KEY]
    specification = document[SPEC_KEY]
    target = specification[TARGET_KEY]
    supports = specification[SUPPORTS_KEY]
    _validate_version(metadata[VERSION_KEY])
    _validate_specifier(target[VERSION_CONSTRAINT_KEY])
    template_name = specification[TEMPLATE_KEY]
    template_path = PurePosixPath(template_name)
    if template_path.is_absolute() or ".." in template_path.parts:
        raise TransformerError(f"Template metadata path must stay relative: {template_name}")
    return TemplateMetadata(
        api_version=document[API_VERSION_KEY],
        name=metadata[NAME_KEY],
        version=metadata[VERSION_KEY],
        engine=specification[ENGINE_KEY],
        template_name=template_name,
        template_api_version=specification[TEMPLATE_API_VERSION_KEY],
        target_tool=target[TOOL_KEY],
        target_version_constraint=target[VERSION_CONSTRAINT_KEY],
        artifact_kind=supports[ARTIFACT_KIND_KEY],
        signals=tuple(supports[SIGNALS_KEY]),
        capabilities=tuple(supports[CAPABILITIES_KEY]),
        source_path=metadata_path,
    )


def _validate_version(value: str) -> None:
    """Require a PEP 440 compatible template version.

    Args:
        value: Template version from the metadata resource.

    Raises:
        TransformerError: The version cannot be parsed.
    """

    try:
        Version(value)
    except InvalidVersion as error:
        raise TransformerError(f"Invalid template metadata version: {value}") from error


def _validate_specifier(value: str) -> None:
    """Require a PEP 440 compatible target-version constraint.

    Args:
        value: Target constraint from the metadata resource.

    Raises:
        TransformerError: The constraint cannot be parsed.
    """

    try:
        SpecifierSet(value)
    except InvalidSpecifier as error:
        raise TransformerError(f"Invalid template target version constraint: {value}") from error
