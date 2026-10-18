# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Unit and integration tests for agent-specific mapping catalogues."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from packaging.version import Version
from ruamel.yaml import YAML

from config_template_transformer.agent_mappings import (
    load_agent_mapping,
    select_agent_mapping_definitions,
)
from config_template_transformer.constants import (
    AGENT_KEY,
    ARTIFACTS_KEY,
    INPUTS_KEY,
    MINIMUM_VERSION_KEY,
    NAME_KEY,
    PATH_KEY,
    PIPELINE_KEY,
    PIPELINES_KEY,
    RECEIVERS_KEY,
    SERVICE_KEY,
    SPEC_KEY,
    UTF8_ENCODING,
)
from config_template_transformer.errors import TransformerError
from config_template_transformer.orchestrator import TransformationOrchestrator
from conftest import write_text

COMPONENT_ROOT = Path(__file__).parents[1]
MAPPING_ROOT = COMPONENT_ROOT / "mappings"
TEMPLATE_ROOT = COMPONENT_ROOT / "src" / "config_template_transformer" / "templates"
DETECTORS_KEY = "detectors"
DETECTOR_NAME_KEY = "detector_name"
DETECTOR_VERSION_KEY = "detector_version"
DETECTED_KEY = "detected"
ERRORS_KEY = "errors"
QUERIES_KEY = "queries"
LOG_LOCATIONS_KEY = "log_locations"
METRICS_OUTPUTS_KEY = "metrics_outputs"
PATH_OR_DESTINATION_KEY = "path_or_destination"
ENDPOINT_HOST_KEY = "endpoint_host"
PORT_KEY = "port"
LOG_DIRECTORY_CANDIDATE_KEY = "log_directory_candidate"
PROCESSORS_KEY = "processors"
HOST_KEY = "host"
LOGS_KEY = "logs"
METRICS_KEY = "metrics"


def _detector_result(detector_name: str, queries: dict[str, object]) -> dict[str, object]:
    """Build one detected result for catalogue integration tests.

    Args:
        detector_name: Stable detector identity expected by a mapping.
        queries: Query output rows exposed to JSONPath rules.

    Returns:
        Minimal aggregate-compatible detector result mapping.
    """

    return {
        DETECTOR_NAME_KEY: detector_name,
        DETECTOR_VERSION_KEY: "1.0.0",
        DETECTED_KEY: True,
        QUERIES_KEY: queries,
        ERRORS_KEY: [],
    }


def _render_catalogue(
    tmp_path: Path,
    detectors: list[dict[str, object]],
    target_tool: str,
    target_version: str,
) -> tuple[dict[str, object], Path]:
    """Render actual catalogue mappings into a temporary output directory.

    Args:
        tmp_path: Pytest-owned working directory.
        detectors: Aggregate detector entries to serialize.
        target_tool: Agent type whose mappings should be selected.
        target_version: Agent version used for compatibility-floor selection.

    Returns:
        Parsed manifest dictionary and output root path.
    """

    detector_path = write_text(
        tmp_path / "detectors.json",
        json.dumps({DETECTORS_KEY: detectors}),
    )
    output_root = tmp_path / "output"
    manifest_path = output_root / "orchestration.json"
    manifest = TransformationOrchestrator(TEMPLATE_ROOT).render(
        detector_results_path=detector_path,
        definition_paths=[],
        output_root=output_root,
        manifest_output=manifest_path,
        target_version=target_version,
        mapping_root=MAPPING_ROOT,
        target_tool=target_tool,
    )
    return manifest.to_dict(), output_root


def test_selector_uses_highest_compatible_agent_version_floor() -> None:
    """Select Fluent Bit 4 or 5 templates from the same detector identity."""

    fluent_bit_4 = select_agent_mapping_definitions(
        MAPPING_ROOT,
        {"nginx_1"},
        "fluent-bit",
        Version("4.9.9"),
    )
    fluent_bit_5 = select_agent_mapping_definitions(
        MAPPING_ROOT,
        {"nginx_1"},
        "fluent-bit",
        Version("5.2.0"),
    )
    assert fluent_bit_4[0].template_name == "fluent_bit_4_pipeline.yaml.j2"
    assert fluent_bit_5[0].template_name == "fluent_bit_5_pipeline.yaml.j2"


def test_selector_rejects_missing_empty_incompatible_and_ambiguous_catalogues(
    tmp_path: Path,
) -> None:
    """Report unusable catalogue roots and duplicate best version floors."""

    with pytest.raises(TransformerError, match="not a directory"):
        select_agent_mapping_definitions(
            tmp_path / "missing", {"nginx_1"}, "fluent-bit", Version("5.0")
        )
    with pytest.raises(TransformerError, match="No agent mapping JSON"):
        select_agent_mapping_definitions(tmp_path, {"nginx_1"}, "fluent-bit", Version("5.0"))
    with pytest.raises(TransformerError, match="No mappings support"):
        select_agent_mapping_definitions(
            MAPPING_ROOT, {"nginx_1"}, "fluent-bit", Version("3.9")
        )
    with pytest.raises(TransformerError, match="No mappings support"):
        select_agent_mapping_definitions(MAPPING_ROOT, {"nginx_1"}, "vector", Version("1.0"))

    source_path = MAPPING_ROOT / "fluent-bit" / "5.0" / "nginx_1.json"
    write_text(tmp_path / "first.json", source_path.read_text(encoding=UTF8_ENCODING))
    write_text(tmp_path / "nested" / "second.json", source_path.read_text(encoding=UTF8_ENCODING))
    with pytest.raises(TransformerError, match="Multiple fluent-bit mappings"):
        select_agent_mapping_definitions(
            tmp_path, {"nginx_1"}, "fluent-bit", Version("5.0")
        )


def test_mapping_loader_rejects_invalid_minimum_version(tmp_path: Path) -> None:
    """Validate semantic version floors after JSON Schema validation."""

    source_path = MAPPING_ROOT / "fluent-bit" / "5.0" / "nginx_1.json"
    document = json.loads(source_path.read_text(encoding=UTF8_ENCODING))
    document[SPEC_KEY][AGENT_KEY][MINIMUM_VERSION_KEY] = "not a version"
    invalid_path = write_text(tmp_path / "invalid.json", json.dumps(document))
    with pytest.raises(TransformerError, match="Invalid minimum agent version"):
        load_agent_mapping(invalid_path)


@pytest.mark.parametrize("target_version", ["4.2.0", "5.1.0"])
def test_catalogue_renders_fluent_bit_nginx_and_postgresql(
    tmp_path: Path,
    target_version: str,
) -> None:
    """Render NGINX log/metrics and PostgreSQL tail/Lua processor inputs."""

    nginx_result = _detector_result(
        "nginx_1",
        {
            LOG_LOCATIONS_KEY: [{PATH_OR_DESTINATION_KEY: "/var/log/nginx/access.log"}],
            METRICS_OUTPUTS_KEY: [{ENDPOINT_HOST_KEY: "127.0.0.1", PORT_KEY: "8080"}],
        },
    )
    postgresql_result = _detector_result(
        "postgresql_17",
        {LOG_LOCATIONS_KEY: [{LOG_DIRECTORY_CANDIDATE_KEY: "/var/lib/postgresql/17/log"}]},
    )
    manifest, output_root = _render_catalogue(
        tmp_path,
        [nginx_result, postgresql_result],
        "fluent-bit",
        target_version,
    )
    assert len(manifest[ARTIFACTS_KEY]) == 2

    nginx_fragment = YAML(typ="safe").load(
        (output_root / "generated/fluent-bit/nginx.inputs.yaml").read_text(
            encoding=UTF8_ENCODING
        )
    )
    nginx_inputs = nginx_fragment[PIPELINE_KEY][INPUTS_KEY]
    assert [plugin[NAME_KEY] for plugin in nginx_inputs] == ["tail", "nginx_metrics"]
    assert nginx_inputs[1][HOST_KEY] == "127.0.0.1"
    assert nginx_inputs[1][PORT_KEY] == "8080"

    postgresql_fragment = YAML(typ="safe").load(
        (output_root / "generated/fluent-bit/postgresql_17.inputs.yaml").read_text(
            encoding=UTF8_ENCODING
        )
    )
    postgresql_input = postgresql_fragment[PIPELINE_KEY][INPUTS_KEY][0]
    assert postgresql_input[PATH_KEY] == "/var/lib/postgresql/17/log/*.log"
    assert postgresql_input[PROCESSORS_KEY][LOGS_KEY][0][NAME_KEY] == "lua"


def test_catalogue_renders_latest_otelcol_contrib_nginx(tmp_path: Path) -> None:
    """Render filelog and NGINX receivers into Collector service pipelines."""

    nginx_result = _detector_result(
        "nginx_1",
        {
            LOG_LOCATIONS_KEY: [{PATH_OR_DESTINATION_KEY: "/var/log/nginx/access.log"}],
            METRICS_OUTPUTS_KEY: [{ENDPOINT_HOST_KEY: "localhost", PORT_KEY: "80"}],
        },
    )
    manifest, output_root = _render_catalogue(
        tmp_path,
        [nginx_result],
        "otelcol-contrib",
        "0.163.0",
    )
    artifact_path = output_root / manifest[ARTIFACTS_KEY][0][PATH_KEY]
    fragment = YAML(typ="safe").load(artifact_path.read_text(encoding=UTF8_ENCODING))
    assert set(fragment[RECEIVERS_KEY]) == {"filelog/nginx_1", "nginx/nginx_2"}
    pipelines = fragment[SERVICE_KEY][PIPELINES_KEY]
    assert pipelines[LOGS_KEY][RECEIVERS_KEY] == ["filelog/nginx_1"]
    assert pipelines[METRICS_KEY][RECEIVERS_KEY] == ["nginx/nginx_2"]
