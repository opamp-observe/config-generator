# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for orchestration selection and manifest verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config_template_transformer.constants import (
    ARTIFACTS_KEY,
    INCLUDE_KEY,
    PATH_KEY,
    PLUGIN_COUNT_KEY,
    SELECTION_DETECTOR_ERRORS,
    SELECTION_DETECTOR_NOT_DETECTED,
    SELECTION_DETECTOR_NOT_FOUND,
    SELECTION_STATUS_KEY,
    SHA256_KEY,
    STRATEGY_KEY,
    UTF8_ENCODING,
)
from config_template_transformer.errors import TransformerError
from config_template_transformer.orchestrator import (
    TransformationOrchestrator,
    inject_manifest_includes,
)
from conftest import (
    DETECTOR_RESULTS_TEXT,
    FIXTURE_DEFINITION_KEY,
    FIXTURE_DETECTOR_KEY,
    FIXTURE_MANIFEST_KEY,
    FIXTURE_OUTPUT_ROOT_KEY,
    FIXTURE_TEMPLATE_ROOT_KEY,
    TRANSFORM_TEXT,
    read_json,
    write_text,
)
from test_template_metadata import TEMPLATE_METADATA_TEXT


def render_fixture(
    component_paths: dict[str, Path],
    detector_text: str = DETECTOR_RESULTS_TEXT,
    definition_text: str = TRANSFORM_TEXT,
    target_version: str = "4.2.0",
) -> dict[str, object]:
    """Render a modified fixture and return its JSON-compatible manifest.

    Args:
        component_paths: Common isolated component paths.
        detector_text: Aggregate detector JSON fixture.
        definition_text: YAML transform definition fixture.
        target_version: Target version passed to compatibility checking.

    Returns:
        Parsed orchestration manifest mapping.
    """

    write_text(component_paths[FIXTURE_DETECTOR_KEY], detector_text)
    write_text(component_paths[FIXTURE_DEFINITION_KEY], definition_text)
    orchestrator = TransformationOrchestrator(component_paths[FIXTURE_TEMPLATE_ROOT_KEY])
    orchestrator.render(
        detector_results_path=component_paths[FIXTURE_DETECTOR_KEY],
        definition_paths=[component_paths[FIXTURE_DEFINITION_KEY]],
        output_root=component_paths[FIXTURE_OUTPUT_ROOT_KEY],
        manifest_output=component_paths[FIXTURE_MANIFEST_KEY],
        target_version=target_version,
    )
    return read_json(component_paths[FIXTURE_MANIFEST_KEY])


@pytest.mark.parametrize(
    ("detector_text", "expected_status"),
    [
        ('{"detectors": []}', SELECTION_DETECTOR_NOT_FOUND),
        (
            DETECTOR_RESULTS_TEXT.replace('"detected": true', '"detected": false'),
            SELECTION_DETECTOR_NOT_DETECTED,
        ),
        (
            DETECTOR_RESULTS_TEXT.replace('"errors": []', '"errors": ["query failed"]'),
            SELECTION_DETECTOR_ERRORS,
        ),
    ],
)
def test_orchestrator_writes_stable_empty_fragments(
    component_paths: dict[str, Path],
    detector_text: str,
    expected_status: str,
) -> None:
    """Always replace declared artifacts when detector data is unusable."""

    manifest = render_fixture(component_paths, detector_text=detector_text)
    artifact = manifest[ARTIFACTS_KEY][0]
    assert artifact[SELECTION_STATUS_KEY] == expected_status
    assert artifact[PLUGIN_COUNT_KEY] == 0


@pytest.mark.parametrize(
    ("detector_text", "definition_text", "target_version", "expected_message"),
    [
        ("{}", TRANSFORM_TEXT, "4.2.0", "detectors array"),
        ('{"detectors": []}', TRANSFORM_TEXT, "invalid", "Invalid target version"),
        ('{"detectors": []}', TRANSFORM_TEXT, "2.0.0", "does not satisfy"),
        (
            DETECTOR_RESULTS_TEXT.replace('"1.0.0"', '"invalid"', 1),
            TRANSFORM_TEXT,
            "4.2.0",
            "Invalid detector version",
        ),
        (
            DETECTOR_RESULTS_TEXT.replace('"1.0.0"', '"2.0.0"', 1),
            TRANSFORM_TEXT,
            "4.2.0",
            "does not satisfy",
        ),
        (
            DETECTOR_RESULTS_TEXT.replace("}]", '}, {"detector_name":"nginx_1"}]', 1),
            TRANSFORM_TEXT,
            "4.2.0",
            "Multiple detector",
        ),
        (
            DETECTOR_RESULTS_TEXT,
            TRANSFORM_TEXT.replace("fluent-bit", "vector"),
            "4.2.0",
            "Unsupported target tool",
        ),
        (
            DETECTOR_RESULTS_TEXT,
            TRANSFORM_TEXT.replace("$.queries.log_locations[*]", "$["),
            "4.2.0",
            "JSONPath evaluation failed",
        ),
    ],
)
def test_orchestrator_rejects_invalid_inputs(
    component_paths: dict[str, Path],
    detector_text: str,
    definition_text: str,
    target_version: str,
    expected_message: str,
) -> None:
    """Reject invalid versions, detector ambiguity, tools, and JSONPath."""

    with pytest.raises(TransformerError, match=expected_message):
        render_fixture(component_paths, detector_text, definition_text, target_version)


def test_orchestrator_requires_definitions_and_one_target(component_paths: dict[str, Path]) -> None:
    """Require at least one definition and prevent mixed-target manifests."""

    orchestrator = TransformationOrchestrator(component_paths[FIXTURE_TEMPLATE_ROOT_KEY])
    with pytest.raises(TransformerError, match="At least one"):
        orchestrator.render(
            component_paths[FIXTURE_DETECTOR_KEY],
            [],
            component_paths[FIXTURE_OUTPUT_ROOT_KEY],
            component_paths[FIXTURE_MANIFEST_KEY],
            "4.2.0",
        )

    mapping_root = component_paths[FIXTURE_DEFINITION_KEY].parent
    with pytest.raises(TransformerError, match="not both"):
        orchestrator.render(
            component_paths[FIXTURE_DETECTOR_KEY],
            [component_paths[FIXTURE_DEFINITION_KEY]],
            component_paths[FIXTURE_OUTPUT_ROOT_KEY],
            component_paths[FIXTURE_MANIFEST_KEY],
            "4.2.0",
            mapping_root=mapping_root,
            target_tool="fluent-bit",
        )
    with pytest.raises(TransformerError, match="Target tool is required"):
        orchestrator.render(
            component_paths[FIXTURE_DETECTOR_KEY],
            [],
            component_paths[FIXTURE_OUTPUT_ROOT_KEY],
            component_paths[FIXTURE_MANIFEST_KEY],
            "4.2.0",
            mapping_root=mapping_root,
        )

    other_definition = write_text(
        component_paths[FIXTURE_DEFINITION_KEY].parent / "other.yaml",
        TRANSFORM_TEXT.replace("name: nginx_1_logs", "name: other", 1).replace(
            "tool: fluent-bit", "tool: vector"
        ),
    )
    with pytest.raises(TransformerError, match="cannot mix target tools"):
        orchestrator.render(
            component_paths[FIXTURE_DETECTOR_KEY],
            [component_paths[FIXTURE_DEFINITION_KEY], other_definition],
            component_paths[FIXTURE_OUTPUT_ROOT_KEY],
            component_paths[FIXTURE_MANIFEST_KEY],
            "4.2.0",
        )


def test_orchestrator_enforces_plugin_limit(component_paths: dict[str, Path]) -> None:
    """Stop a transform before an unbounded result can be rendered."""

    orchestrator = TransformationOrchestrator(
        component_paths[FIXTURE_TEMPLATE_ROOT_KEY], max_plugin_count=1
    )
    with pytest.raises(TransformerError, match="exceeds plugin limit"):
        orchestrator.render(
            component_paths[FIXTURE_DETECTOR_KEY],
            [component_paths[FIXTURE_DEFINITION_KEY]],
            component_paths[FIXTURE_OUTPUT_ROOT_KEY],
            component_paths[FIXTURE_MANIFEST_KEY],
            "4.2.0",
        )


def test_orchestrator_skips_missing_dynamic_fields(component_paths: dict[str, Path]) -> None:
    """Skip a source row when an optional mapped detector field is absent."""

    definition_text = TRANSFORM_TEXT.replace(
        "      path_from: $.path_or_destination\n",
        "      fields_from:\n        endpoint: $.missing_endpoint\n",
    )
    manifest = render_fixture(component_paths, definition_text=definition_text)
    assert manifest[ARTIFACTS_KEY][0][PLUGIN_COUNT_KEY] == 0


def test_orchestrator_rejects_ambiguous_dynamic_fields(
    component_paths: dict[str, Path],
) -> None:
    """Reject a field selector that cannot map one source row to one value."""

    definition_text = TRANSFORM_TEXT.replace(
        "      path_from: $.path_or_destination\n",
        "      fields_from:\n        endpoint: $.*\n",
    )
    detector_text = DETECTOR_RESULTS_TEXT.replace(
        '"path_or_destination": "/var/log/nginx/access.log"',
        '"path_or_destination": "/var/log/nginx/access.log", "secondary": "value"',
        1,
    )
    with pytest.raises(TransformerError, match="selected multiple values"):
        render_fixture(
            component_paths,
            detector_text=detector_text,
            definition_text=definition_text,
        )


@pytest.mark.parametrize(
    ("metadata_text", "expected_message"),
    [
        (
            TEMPLATE_METADATA_TEXT.replace("fluent_bit_inputs.yaml.j2", "other_inputs.yaml.j2"),
            "template path",
        ),
        (
            TEMPLATE_METADATA_TEXT.replace("version: 1.0.0", "version: 1.1.0"),
            "template version",
        ),
        (
            TEMPLATE_METADATA_TEXT.replace(
                'template_api_version: "1.0"', 'template_api_version: "2.0"'
            ),
            "template API version",
        ),
        (
            TEMPLATE_METADATA_TEXT.replace("tool: fluent-bit", "tool: vector"),
            "target tool",
        ),
        (
            TEMPLATE_METADATA_TEXT.replace('">=3.2,<5.0"', '">=3.2,<4.0"'),
            "does not support",
        ),
    ],
)
def test_orchestrator_enforces_template_metadata_compatibility(
    component_paths: dict[str, Path],
    metadata_text: str,
    expected_message: str,
) -> None:
    """Reject transforms that conflict with independently owned metadata."""

    template_root = component_paths[FIXTURE_DEFINITION_KEY].parent / "templates"
    package_template_root = component_paths[FIXTURE_TEMPLATE_ROOT_KEY]
    write_text(
        template_root / "fluent_bit_inputs.yaml.j2",
        (package_template_root / "fluent_bit_inputs.yaml.j2").read_text(encoding=UTF8_ENCODING),
    )
    write_text(template_root / "fluent_bit_inputs.metadata.yaml", metadata_text)
    orchestrator = TransformationOrchestrator(template_root)
    with pytest.raises(TransformerError, match=expected_message):
        orchestrator.render(
            component_paths[FIXTURE_DETECTOR_KEY],
            [component_paths[FIXTURE_DEFINITION_KEY]],
            component_paths[FIXTURE_OUTPUT_ROOT_KEY],
            component_paths[FIXTURE_MANIFEST_KEY],
            "4.2.0",
        )


@pytest.mark.parametrize("mutation", ["hash", "strategy", "artifact"])
def test_injection_rejects_untrusted_manifest_state(
    component_paths: dict[str, Path],
    mutation: str,
) -> None:
    """Reject changed artifacts and incompatible manifest include instructions."""

    manifest = render_fixture(component_paths)
    artifact = manifest[ARTIFACTS_KEY][0]
    if mutation == "hash":
        artifact[SHA256_KEY] = "0" * 64
    elif mutation == "strategy":
        artifact[INCLUDE_KEY][STRATEGY_KEY] = "other"
    else:
        artifact_path = component_paths[FIXTURE_OUTPUT_ROOT_KEY] / artifact[PATH_KEY]
        artifact_path.unlink()
    component_paths[FIXTURE_MANIFEST_KEY].write_text(
        json.dumps(manifest),
        encoding=UTF8_ENCODING,
    )
    parent_path = write_text(
        component_paths[FIXTURE_OUTPUT_ROOT_KEY] / "parent.yaml", "service: {}\n"
    )
    with pytest.raises(TransformerError):
        inject_manifest_includes(
            component_paths[FIXTURE_MANIFEST_KEY],
            parent_path,
            component_paths[FIXTURE_OUTPUT_ROOT_KEY] / "assembled.yaml",
            component_paths[FIXTURE_OUTPUT_ROOT_KEY],
        )
