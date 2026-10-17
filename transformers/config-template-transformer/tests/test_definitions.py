# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for transform definition loading and validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from config_template_transformer.definitions import load_transform_definition
from config_template_transformer.errors import TransformerError
from conftest import TRANSFORM_TEXT, write_text


@pytest.mark.parametrize(
    ("source", "expected_message"),
    [
        ("[]", "must be a mapping"),
        (TRANSFORM_TEXT.replace("ObservabilityFragmentTransform", "OtherTransform"), "Invalid"),
        (TRANSFORM_TEXT.replace("jinja2", "other-engine"), "Invalid transform definition"),
        (
            TRANSFORM_TEXT.replace("version: 1.0.0", "version: not-a-version", 1),
            "Invalid transform version",
        ),
        (
            TRANSFORM_TEXT.replace('">=1,<2"', '"not-a-specifier"'),
            "Invalid detector version constraint",
        ),
        (
            TRANSFORM_TEXT.replace("generated/nginx.inputs.yaml", "../escape.yaml", 1),
            "must stay relative",
        ),
        (TRANSFORM_TEXT.replace("fluent_bit_inputs.yaml.j2", "../escape.j2"), "must stay relative"),
        (
            TRANSFORM_TEXT.replace("fluent_bit_inputs.metadata.yaml", "../escape.metadata.yaml"),
            "must stay relative",
        ),
    ],
)
def test_definition_rejects_invalid_values(
    tmp_path: Path,
    source: str,
    expected_message: str,
) -> None:
    """Reject invalid schema, engine, version, specifier, and path values."""

    definition_path = write_text(tmp_path / "definition.yaml", source)
    with pytest.raises(TransformerError, match=expected_message):
        load_transform_definition(definition_path)


def test_definition_reports_unreadable_yaml(tmp_path: Path) -> None:
    """Wrap missing and malformed YAML failures with component errors."""

    with pytest.raises(TransformerError, match="Unable to load transform"):
        load_transform_definition(tmp_path / "missing.yaml")

    malformed_path = write_text(tmp_path / "malformed.yaml", "value: [")
    with pytest.raises(TransformerError, match="Unable to load transform"):
        load_transform_definition(malformed_path)
