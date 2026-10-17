# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""JSON Schema validation helpers for packaged contracts and detector input."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from config_template_transformer.constants import UTF8_ENCODING
from config_template_transformer.errors import TransformerError

SCHEMA_PACKAGE_NAME = "config_template_transformer.schemas"


def load_packaged_schema(resource_name: str) -> dict[str, Any]:
    """Load a packaged JSON Schema object.

    Args:
        resource_name: Schema filename inside the package schema directory.

    Returns:
        Parsed JSON Schema mapping.
    """

    schema_text = (
        files(SCHEMA_PACKAGE_NAME).joinpath(resource_name).read_text(encoding=UTF8_ENCODING)
    )
    loaded_schema = json.loads(schema_text)
    if not isinstance(loaded_schema, dict):
        raise TransformerError(f"Packaged schema is not an object: {resource_name}")
    return loaded_schema


def validate_document(
    document: dict[str, Any],
    schema: dict[str, Any],
    description: str,
) -> None:
    """Validate a document and raise a concise path-aware error.

    Args:
        document: JSON-compatible mapping to validate.
        schema: Draft 2020-12 schema used for validation.
        description: Human-readable input name included in errors.

    Raises:
        TransformerError: The document violates its schema.
    """

    validator = Draft202012Validator(schema)
    first_error = next(iter(sorted(validator.iter_errors(document), key=_error_path)), None)
    if first_error is None:
        return
    path_text = "/".join(str(segment) for segment in first_error.absolute_path) or "<root>"
    raise TransformerError(f"Invalid {description} at {path_text}: {first_error.message}")


def validate_external_schema(
    document: dict[str, Any],
    schema_path: Path | None,
) -> None:
    """Optionally validate detector results with a caller-supplied schema.

    Args:
        document: Detector-result mapping to validate.
        schema_path: Optional Draft 2020-12 schema path.

    Raises:
        TransformerError: The schema cannot be loaded or validation fails.
    """

    if schema_path is None:
        return
    try:
        schema = json.loads(schema_path.read_text(encoding=UTF8_ENCODING))
        Draft202012Validator(schema).validate(document)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        raise TransformerError(
            f"Detector results failed schema validation with {schema_path}: {error}"
        ) from error


def _error_path(error: ValidationError) -> tuple[str, ...]:
    """Build a stable sortable path for a JSON Schema validation error.

    Args:
        error: Validation error returned by jsonschema.

    Returns:
        Tuple of string path segments suitable for deterministic sorting.
    """

    return tuple(str(segment) for segment in error.absolute_path)
