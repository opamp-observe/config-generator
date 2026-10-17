# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Safe file loading, hashing, and atomic output helpers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from config_template_transformer.constants import (
    FILE_DIGEST_BLOCK_SIZE,
    JSON_INDENT_SPACES,
    UTF8_ENCODING,
)
from config_template_transformer.errors import TransformerError


def load_json_object(file_path: Path) -> dict[str, Any]:
    """Load a UTF-8 JSON object from disk.

    Args:
        file_path: JSON document to decode.

    Returns:
        The decoded top-level mapping.

    Raises:
        TransformerError: The document is unreadable, invalid, or not an object.
    """

    try:
        loaded_value = json.loads(file_path.read_text(encoding=UTF8_ENCODING))
    except (OSError, json.JSONDecodeError) as error:
        raise TransformerError(f"Unable to load JSON object {file_path}: {error}") from error
    if not isinstance(loaded_value, dict):
        raise TransformerError(f"JSON document must contain an object: {file_path}")
    return loaded_value


def sha256_file(file_path: Path) -> str:
    """Calculate the SHA-256 digest of a file without loading it all at once.

    Args:
        file_path: File whose exact bytes should be identified.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """

    digest = hashlib.sha256()
    with file_path.open("rb") as input_file:
        for data_block in iter(lambda: input_file.read(FILE_DIGEST_BLOCK_SIZE), b""):
            digest.update(data_block)
    return digest.hexdigest()


def sha256_bytes(content: bytes) -> str:
    """Calculate the SHA-256 digest of rendered bytes.

    Args:
        content: Exact artifact bytes that will be written.

    Returns:
        Lowercase hexadecimal SHA-256 digest.
    """

    return hashlib.sha256(content).hexdigest()


def resolve_output_path(output_root: Path, relative_path: Path) -> Path:
    """Resolve an artifact path and keep it inside the configured output root.

    Args:
        output_root: Directory authorized to receive generated artifacts.
        relative_path: Definition-owned path below the output root.

    Returns:
        Resolved absolute destination path.

    Raises:
        TransformerError: The path is absolute or escapes the output root.
    """

    if relative_path.is_absolute():
        raise TransformerError(f"Artifact path must be relative: {relative_path}")
    resolved_root = output_root.resolve()
    resolved_path = (resolved_root / relative_path).resolve()
    if not resolved_path.is_relative_to(resolved_root):
        raise TransformerError(f"Artifact path escapes output root: {relative_path}")
    return resolved_path


def write_bytes_atomically(destination: Path, content: bytes) -> None:
    """Replace one output file atomically after writing it in the same directory.

    Args:
        destination: Exact file path that should contain the completed content.
        content: Bytes to persist.
    """

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
            temporary_path = Path(temporary_file.name)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def write_json_atomically(destination: Path, document: dict[str, Any]) -> None:
    """Serialize a deterministic JSON object and replace its destination atomically.

    Args:
        destination: Exact JSON output path.
        document: JSON-compatible mapping to serialize.
    """

    serialized = json.dumps(
        document,
        indent=JSON_INDENT_SPACES,
        sort_keys=True,
    )
    write_bytes_atomically(destination, (serialized + "\n").encode(UTF8_ENCODING))
