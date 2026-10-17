# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for template identity and compatibility metadata."""

from __future__ import annotations

from pathlib import Path

import pytest

from config_template_transformer.errors import TransformerError
from config_template_transformer.template_metadata import load_template_metadata
from conftest import write_text

TEMPLATE_METADATA_TEXT = """# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0.
api_version: opamp.info/v1alpha1
kind: ObservabilityTemplateMetadata
metadata:
  name: fluent_bit_inputs
  version: 1.0.0
spec:
  engine: jinja2
  template: fluent_bit_inputs.yaml.j2
  template_api_version: "1.0"
  target:
    tool: fluent-bit
    version_constraint: ">=3.2,<5.0"
  supports:
    artifact_kind: input_fragment
    signals: [logs]
    capabilities: [file_tail_inputs, stable_empty_fragment]
"""


def test_template_metadata_loads_support_contract(tmp_path: Path) -> None:
    """Normalize template identity, target range, signals, and capabilities."""

    metadata_path = write_text(tmp_path / "metadata.yaml", TEMPLATE_METADATA_TEXT)
    metadata = load_template_metadata(metadata_path)
    assert metadata.name == "fluent_bit_inputs"
    assert metadata.version == "1.0.0"
    assert metadata.target_tool == "fluent-bit"
    assert metadata.target_version_constraint == ">=3.2,<5.0"
    assert metadata.artifact_kind == "input_fragment"
    assert metadata.signals == ("logs",)
    assert metadata.capabilities == ("file_tail_inputs", "stable_empty_fragment")


@pytest.mark.parametrize(
    ("metadata_text", "expected_message"),
    [
        ("[]", "must be a mapping"),
        (
            TEMPLATE_METADATA_TEXT.replace("version: 1.0.0", "version: invalid"),
            "Invalid template metadata version",
        ),
        (
            TEMPLATE_METADATA_TEXT.replace('">=3.2,<5.0"', '"invalid"'),
            "Invalid template target version constraint",
        ),
        (
            TEMPLATE_METADATA_TEXT.replace("fluent_bit_inputs.yaml.j2", "../outside.yaml.j2"),
            "must stay relative",
        ),
        (
            TEMPLATE_METADATA_TEXT.replace("ObservabilityTemplateMetadata", "UnknownMetadata"),
            "Invalid template metadata",
        ),
    ],
)
def test_template_metadata_rejects_invalid_contracts(
    tmp_path: Path,
    metadata_text: str,
    expected_message: str,
) -> None:
    """Reject invalid resource shapes, versions, constraints, and paths."""

    metadata_path = write_text(tmp_path / "metadata.yaml", metadata_text)
    with pytest.raises(TransformerError, match=expected_message):
        load_template_metadata(metadata_path)


def test_template_metadata_reports_unreadable_yaml(tmp_path: Path) -> None:
    """Wrap missing and malformed metadata YAML with concise errors."""

    with pytest.raises(TransformerError, match="Unable to load template metadata"):
        load_template_metadata(tmp_path / "missing.yaml")
    malformed_path = write_text(tmp_path / "malformed.yaml", "value: [")
    with pytest.raises(TransformerError, match="Unable to load template metadata"):
        load_template_metadata(malformed_path)
