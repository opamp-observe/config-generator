# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Immutable records used by the semantic payload-mapping stage."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SemanticMapping:
    """Describe how one source format becomes an OpenTelemetry log payload.

    Attributes:
        name: Stable mapping identity.
        version: Mapping semantic version.
        detector_name: Detector whose plugins can use the mapping.
        detector_version_constraint: Compatible detector versions.
        source_formats: Input format hints accepted by the mapping.
        path_regex: Optional plugin-path discriminator.
        priority: Selection priority when multiple mappings match.
        semantic_conventions_version: OpenTelemetry semantic-conventions version.
        parse: Agent-neutral parser specification.
        body_from: Parsed field promoted to the log body.
        field_mappings: Parsed fields mapped to semantic attribute names.
        resource_attributes: Static OpenTelemetry resource attributes.
        record_attributes: Static OpenTelemetry log-record attributes.
        source_path: Mapping file retained for audit output.
    """

    name: str
    version: str
    detector_name: str
    detector_version_constraint: str
    source_formats: tuple[str, ...]
    path_regex: str | None
    priority: int
    semantic_conventions_version: str
    parse: dict[str, Any]
    body_from: str
    field_mappings: dict[str, str]
    resource_attributes: dict[str, Any]
    record_attributes: dict[str, Any]
    source_path: Path


@dataclass(frozen=True)
class SemanticPlugin:
    """Combine verified first-stage provenance with its selected semantic mapping.

    Attributes:
        detector_name: Detector identity copied from the artifact record.
        detector_version: Exact detector version observed in the first stage.
        plugin: Per-plugin provenance and configuration mapping.
        mapping: Selected semantic payload mapping.
    """

    detector_name: str
    detector_version: str
    plugin: dict[str, Any]
    mapping: SemanticMapping


@dataclass(frozen=True)
class GeneratedSemanticArtifact:
    """Hold one generated semantic configuration artifact before persistence.

    Attributes:
        path: Safe path relative to the requested output root.
        media_type: Content media type recorded in the stage manifest.
        content: Exact bytes to write and checksum.
    """

    path: Path
    media_type: str
    content: bytes
