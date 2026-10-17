# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for safe files and JSON Schema validation helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from config_template_transformer.constants import MANIFEST_SCHEMA_RESOURCE
from config_template_transformer.errors import TransformerError
from config_template_transformer.files import (
    load_json_object,
    resolve_output_path,
    sha256_bytes,
    sha256_file,
    write_bytes_atomically,
    write_json_atomically,
)
from config_template_transformer.validation import (
    load_packaged_schema,
    validate_document,
    validate_external_schema,
)
from conftest import read_json, write_text


def test_file_helpers_round_trip_and_hash(tmp_path: Path) -> None:
    """Write bytes and deterministic JSON atomically and calculate digests."""

    byte_path = tmp_path / "nested" / "value.bin"
    write_bytes_atomically(byte_path, b"value")
    assert sha256_file(byte_path) == sha256_bytes(b"value")

    json_path = tmp_path / "value.json"
    write_json_atomically(json_path, {"value": True})
    assert read_json(json_path)["value"] is True
    assert load_json_object(json_path)["value"] is True


@pytest.mark.parametrize("content", ["[1]", "{"])
def test_load_json_object_rejects_invalid_documents(
    tmp_path: Path,
    content: str,
) -> None:
    """Reject malformed JSON and non-object top-level values."""

    input_path = write_text(tmp_path / "input.json", content)
    with pytest.raises(TransformerError):
        load_json_object(input_path)


def test_output_path_stays_within_root(tmp_path: Path) -> None:
    """Resolve safe paths and reject absolute or parent traversal paths."""

    assert resolve_output_path(tmp_path, Path("child/value")) == tmp_path / "child/value"
    with pytest.raises(TransformerError, match="must be relative"):
        resolve_output_path(tmp_path, tmp_path / "absolute")
    with pytest.raises(TransformerError, match="escapes output root"):
        resolve_output_path(tmp_path, Path("../escape"))


def test_schema_helpers_report_packaged_and_external_errors(tmp_path: Path) -> None:
    """Load packaged schemas and wrap local schema validation failures."""

    schema = load_packaged_schema(MANIFEST_SCHEMA_RESOURCE)
    with pytest.raises(TransformerError, match="Invalid manifest"):
        validate_document({}, schema, "manifest")

    validate_external_schema({}, None)
    schema_path = write_text(
        tmp_path / "schema.json",
        '{"type":"object","required":["required_value"]}',
    )
    with pytest.raises(TransformerError, match="failed schema validation"):
        validate_external_schema({}, schema_path)
    malformed_schema_path = write_text(tmp_path / "malformed.json", "{")
    with pytest.raises(TransformerError, match="failed schema validation"):
        validate_external_schema({}, malformed_schema_path)


def test_packaged_schema_must_be_an_object(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject a corrupted packaged schema with a non-object top level."""

    resource = SimpleNamespace(read_text=lambda **_arguments: "[]")
    package = SimpleNamespace(joinpath=lambda _resource_name: resource)
    monkeypatch.setattr("config_template_transformer.validation.files", lambda _name: package)
    with pytest.raises(TransformerError, match="not an object"):
        load_packaged_schema("invalid.json")


def test_atomic_write_cleans_up_after_temp_creation_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Propagate temp-file failures without attempting to remove an unset path."""

    def fail_to_create(**_arguments: object) -> None:
        """Simulate failure before an atomic write receives a temporary path."""

        raise OSError("simulated failure")

    monkeypatch.setattr(
        "config_template_transformer.files.tempfile.NamedTemporaryFile", fail_to_create
    )
    with pytest.raises(OSError, match="simulated failure"):
        write_bytes_atomically(tmp_path / "output", b"value")
