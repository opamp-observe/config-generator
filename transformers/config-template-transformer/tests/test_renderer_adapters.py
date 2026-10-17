# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for sandboxed rendering and Fluent Bit adaptation."""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from config_template_transformer.adapters import FluentBitAdapter, get_target_adapter
from config_template_transformer.constants import INPUTS_KEY, PIPELINE_KEY, UTF8_ENCODING
from config_template_transformer.definitions import load_transform_definition
from config_template_transformer.errors import TransformerError
from config_template_transformer.renderer import JinjaFragmentRenderer
from conftest import TRANSFORM_TEXT, write_text


def test_renderer_enforces_limits_and_structure(tmp_path: Path) -> None:
    """Reject excess plugin counts, bytes, undefined values, and non-mappings."""

    template_path = write_text(tmp_path / "template.j2", "{{ missing_value }}")
    renderer = JinjaFragmentRenderer(tmp_path, max_plugin_count=0)
    with pytest.raises(TransformerError, match="Plugin count"):
        renderer.render(template_path.name, "plugins", [{"name": "tail"}])

    renderer = JinjaFragmentRenderer(tmp_path)
    with pytest.raises(TransformerError, match="Jinja rendering failed"):
        renderer.render(template_path.name, "plugins", [])

    write_text(template_path, "- item")
    with pytest.raises(TransformerError, match="must be a mapping"):
        renderer.render(template_path.name, "plugins", [])

    write_text(template_path, "value: [")
    with pytest.raises(TransformerError, match="Rendered YAML is invalid"):
        renderer.render(template_path.name, "plugins", [])

    write_text(template_path, "value: abcdef")
    small_renderer = JinjaFragmentRenderer(tmp_path, max_rendered_bytes=2)
    with pytest.raises(TransformerError, match="Rendered output exceeds"):
        small_renderer.render(template_path.name, "plugins", [])


def test_renderer_rejects_missing_or_escaping_template(tmp_path: Path) -> None:
    """Keep resolved templates inside the approved root and require files."""

    renderer = JinjaFragmentRenderer(tmp_path)
    with pytest.raises(TransformerError, match="outside the template root or missing"):
        renderer.template_path("missing.j2")
    outside_path = write_text(tmp_path.parent / "outside.j2", "value: true")
    with pytest.raises(TransformerError, match="outside the template root or missing"):
        renderer.template_path(f"../{outside_path.name}")


def test_fluent_bit_adapter_serializes_empty_fragment(tmp_path: Path) -> None:
    """Serialize a stable empty input fragment with provenance versions."""

    definition_path = write_text(tmp_path / "definition.yaml", TRANSFORM_TEXT)
    definition = load_transform_definition(definition_path)
    fragment = {PIPELINE_KEY: {INPUTS_KEY: []}}
    content = FluentBitAdapter().serialize_fragment(fragment, definition)
    assert b"transform=nginx_1_logs@1.0.0" in content
    parsed = YAML(typ="safe").load(content.decode(UTF8_ENCODING))
    assert parsed == fragment


@pytest.mark.parametrize(
    "fragment",
    [
        {},
        {PIPELINE_KEY: []},
        {PIPELINE_KEY: {INPUTS_KEY: {}}},
        {PIPELINE_KEY: {INPUTS_KEY: [{}]}},
    ],
)
def test_fluent_bit_adapter_rejects_invalid_fragments(
    tmp_path: Path,
    fragment: dict[str, object],
) -> None:
    """Require a named plugin list beneath the Fluent Bit pipeline."""

    definition = load_transform_definition(write_text(tmp_path / "definition.yaml", TRANSFORM_TEXT))
    with pytest.raises(TransformerError, match="Fluent Bit"):
        FluentBitAdapter().serialize_fragment(fragment, definition)


def test_fluent_bit_adapter_validates_parent_and_registry(tmp_path: Path) -> None:
    """Reject malformed parents and unsupported target adapter names."""

    adapter = get_target_adapter("fluent-bit")
    assert isinstance(adapter, FluentBitAdapter)
    with pytest.raises(TransformerError, match="Unsupported target tool"):
        get_target_adapter("vector")

    output_path = tmp_path / "output.yaml"
    malformed_path = write_text(tmp_path / "malformed.yaml", "value: [")
    with pytest.raises(TransformerError, match="Unable to load"):
        adapter.inject_includes(malformed_path, [], output_path)

    sequence_path = write_text(tmp_path / "sequence.yaml", "- item\n")
    with pytest.raises(TransformerError, match="must be a mapping"):
        adapter.inject_includes(sequence_path, [], output_path)

    invalid_includes_path = write_text(tmp_path / "includes.yaml", "includes: value\n")
    with pytest.raises(TransformerError, match="includes must be a list"):
        adapter.inject_includes(invalid_includes_path, [], output_path)

    duplicate_path = write_text(tmp_path / "duplicate.yaml", "includes:\n  - same.yaml\n")
    adapter.inject_includes(duplicate_path, ["same.yaml"], output_path)
    output = YAML(typ="safe").load(output_path.read_text(encoding=UTF8_ENCODING))
    assert output["includes"] == ["same.yaml"]
