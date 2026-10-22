# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""End-to-end tests for provenance and semantic configuration generation."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from config_template_transformer.cli import main
from config_template_transformer.constants import COMMAND_SEMANTIC_MAP
from config_template_transformer.errors import TransformerError
from config_template_transformer.orchestrator import TransformationOrchestrator
from config_template_transformer.semantic_adapters import (
    FluentBitSemanticAdapter,
    OpenTelemetryCollectorSemanticAdapter,
    SemanticConfigurationAdapter,
    get_semantic_adapter,
)
from config_template_transformer.semantic_mappings import (
    load_semantic_mapping,
    load_semantic_mapping_catalogue,
    select_semantic_mapping,
)
from config_template_transformer.semantic_models import SemanticPlugin
from config_template_transformer.semantic_orchestrator import SemanticMappingOrchestrator
from conftest import read_json, write_text

PACKAGE_ROOT = Path(__file__).parents[1]
SOURCE_ROOT = PACKAGE_ROOT / "src" / "config_template_transformer"
TEMPLATE_ROOT = SOURCE_ROOT / "templates"
AGENT_MAPPING_ROOT = PACKAGE_ROOT / "mappings"
SEMANTIC_MAPPING_ROOT = PACKAGE_ROOT / "semantic-mappings"
NGINX_ACCESS_MAPPING_PATH = SEMANTIC_MAPPING_ROOT / "nginx_access_combined.json"
POSTGRESQL_CSV_MAPPING_PATH = SEMANTIC_MAPPING_ROOT / "postgresql_csvlog.json"


def _detector_result(
    detector_name: str,
    queries: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    """Build one minimal detected result accepted by the transformer.

    Args:
        detector_name: Stable detector identity.
        queries: Product query rows consumed by catalogue mappings.

    Returns:
        Detector result mapping with successful selection state.
    """

    return {
        "detector_name": detector_name,
        "detector_version": "1.0.0",
        "detected": True,
        "queries": queries,
        "errors": [],
    }


def _render_first_stage(tmp_path: Path, target_tool: str, target_version: str) -> tuple[Path, Path]:
    """Render NGINX and PostgreSQL source configurations and provenance.

    Args:
        tmp_path: Isolated test directory.
        target_tool: Agent mapping catalogue target.
        target_version: Compatible target version.

    Returns:
        Detector result and orchestration manifest paths.
    """

    detector_document = {
        "detectors": [
            _detector_result(
                "nginx_1",
                {
                    "log_locations": [
                        {"path_or_destination": "/var/log/nginx/access.log"},
                        {"path_or_destination": "/var/log/nginx/error.log"},
                    ],
                    "metrics_outputs": [
                        {"endpoint_host": "localhost", "port": "8080"}
                    ],
                },
            ),
            _detector_result(
                "postgresql_17",
                {
                    "log_locations": [
                        {"log_directory_candidate": "/var/lib/postgresql/17/log"}
                    ]
                },
            ),
        ]
    }
    detector_path = write_text(
        tmp_path / "detector-results.json",
        json.dumps(detector_document),
    )
    manifest_path = tmp_path / "orchestration.json"
    TransformationOrchestrator(TEMPLATE_ROOT).render(
        detector_results_path=detector_path,
        definition_paths=[],
        output_root=tmp_path,
        manifest_output=manifest_path,
        target_version=target_version,
        mapping_root=AGENT_MAPPING_ROOT,
        target_tool=target_tool,
    )
    return detector_path, manifest_path


@pytest.mark.parametrize(
    ("target_tool", "target_version", "expected_artifacts"),
    [
        (
            "fluent-bit",
            "5.1.0",
            {
                "generated/fluent-bit/semantic-normalization.yaml",
                "generated/fluent-bit/semantic-normalization.lua",
            },
        ),
        (
            "otelcol-contrib",
            "0.163.0",
            {"generated/otelcol-contrib/semantic-normalization.yaml"},
        ),
    ],
)
def test_semantic_stage_generates_agent_configurations(
    tmp_path: Path,
    target_tool: str,
    target_version: str,
    expected_artifacts: set[str],
) -> None:
    """Generate semantic configurations for both initial agent implementations."""

    detector_path, manifest_path = _render_first_stage(
        tmp_path,
        target_tool,
        target_version,
    )
    first_stage_manifest = read_json(manifest_path)
    linked_plugins = [
        plugin
        for artifact in first_stage_manifest["artifacts"]
        for plugin in artifact["plugins"]
    ]
    assert all(plugin["human_link"] for plugin in linked_plugins)
    assert all(plugin["detector_link"].startswith("detector://") for plugin in linked_plugins)
    assert any(plugin["source_format"] == "unstructured" for plugin in linked_plugins)

    semantic_manifest_path = tmp_path / "semantic-manifest.json"
    semantic_manifest = SemanticMappingOrchestrator().generate(
        orchestration_manifest_path=manifest_path,
        detector_results_path=detector_path,
        output_root=tmp_path,
        semantic_manifest_output=semantic_manifest_path,
        mapping_root=SEMANTIC_MAPPING_ROOT,
    )
    assert semantic_manifest["target"]["plugin_count"] == 3
    assert {artifact["path"] for artifact in semantic_manifest["artifacts"]} == (
        expected_artifacts
    )
    assert {mapping["mapping_name"] for mapping in semantic_manifest["mappings"]} == {
        "nginx_access_combined",
        "nginx_error",
        "postgresql_stderr",
    }

    yaml_artifact = next(
        tmp_path / artifact_path
        for artifact_path in expected_artifacts
        if artifact_path.endswith(".yaml")
    )
    configuration = YAML(typ="safe").load(yaml_artifact.read_text(encoding="utf-8"))
    if target_tool == "fluent-bit":
        assert len(configuration["pipeline"]["inputs"]) == 3
        assert len(configuration["pipeline"]["filters"]) == 3
        lua_text = (tmp_path / "generated/fluent-bit/semantic-normalization.lua").read_text(
            encoding="utf-8"
        )
        assert "http.request.method" in lua_text
        assert "db.namespace" in lua_text
    else:
        assert len(configuration["receivers"]) == 3
        assert configuration["service"]["pipelines"]["logs"]["receivers"]


def test_explicit_mapping_supports_manual_postgresql_csv_selection(tmp_path: Path) -> None:
    """Allow an operator-owned mapping to override an uninferable PostgreSQL format."""

    detector_path, manifest_path = _render_first_stage(tmp_path, "fluent-bit", "5.1.0")
    mapping_document = json.loads(POSTGRESQL_CSV_MAPPING_PATH.read_text(encoding="utf-8"))
    mapping_document["metadata"]["name"] = "manual_postgresql_csvlog"
    mapping_document["spec"]["source"].pop("path_regex")
    mapping_document["spec"]["source"]["formats"].append("postgresql.stderr")
    manual_mapping_path = write_text(
        tmp_path / "manual_postgresql_csvlog.json",
        json.dumps(mapping_document),
    )
    with pytest.raises(TransformerError, match="No semantic mapping matches plugin"):
        SemanticMappingOrchestrator().generate(
            orchestration_manifest_path=manifest_path,
            detector_results_path=detector_path,
            output_root=tmp_path,
            semantic_manifest_output=tmp_path / "semantic-manifest.json",
            mapping_paths=[manual_mapping_path],
        )

    nginx_mapping_paths = [
        SEMANTIC_MAPPING_ROOT / "nginx_access_combined.json",
        SEMANTIC_MAPPING_ROOT / "nginx_error.json",
    ]
    semantic_manifest = SemanticMappingOrchestrator().generate(
        orchestration_manifest_path=manifest_path,
        detector_results_path=detector_path,
        output_root=tmp_path,
        semantic_manifest_output=tmp_path / "semantic-manifest.json",
        mapping_paths=[*nginx_mapping_paths, manual_mapping_path],
    )
    assert "manual_postgresql_csvlog" in {
        mapping["mapping_name"] for mapping in semantic_manifest["mappings"]
    }


def test_semantic_selection_and_adapter_errors(tmp_path: Path) -> None:
    """Reject ambiguous mappings, changed evidence, and unsupported agents."""

    mapping = load_semantic_mapping(NGINX_ACCESS_MAPPING_PATH)
    plugin = {
        "plugin_id": "nginx.logs-000000000000",
        "source_format": "nginx.auto",
        "properties": {"path": "/var/log/nginx/access.log"},
    }
    with pytest.raises(TransformerError, match="ambiguous"):
        select_semantic_mapping([mapping, mapping], "nginx_1", "1.0.0", plugin)
    with pytest.raises(TransformerError, match="Unsupported semantic target"):
        get_semantic_adapter("unknown-agent")
    assert isinstance(FluentBitSemanticAdapter(), SemanticConfigurationAdapter)
    assert isinstance(OpenTelemetryCollectorSemanticAdapter(), SemanticConfigurationAdapter)

    detector_path, manifest_path = _render_first_stage(tmp_path, "fluent-bit", "5.1.0")
    manifest = read_json(manifest_path)
    formatted_plugin = next(
        plugin
        for artifact in manifest["artifacts"]
        for plugin in artifact["plugins"]
        if plugin["source_format"] != "unstructured"
    )
    formatted_plugin["properties"]["path"] = "/tampered.log"
    tampered_manifest_path = write_text(
        tmp_path / "tampered-manifest.json",
        json.dumps(manifest),
    )
    with pytest.raises(TransformerError, match="Plugin provenance digest changed"):
        SemanticMappingOrchestrator().generate(
            orchestration_manifest_path=tampered_manifest_path,
            detector_results_path=detector_path,
            output_root=tmp_path,
            semantic_manifest_output=tmp_path / "semantic-manifest.json",
            mapping_root=SEMANTIC_MAPPING_ROOT,
        )

    unstructured_manifest = read_json(manifest_path)
    for artifact in unstructured_manifest["artifacts"]:
        for plugin in artifact["plugins"]:
            plugin["source_format"] = "unstructured"
    unstructured_manifest_path = write_text(
        tmp_path / "unstructured-manifest.json",
        json.dumps(unstructured_manifest),
    )
    with pytest.raises(TransformerError, match="no mappable log plugins"):
        SemanticMappingOrchestrator().generate(
            orchestration_manifest_path=unstructured_manifest_path,
            detector_results_path=detector_path,
            output_root=tmp_path,
            semantic_manifest_output=tmp_path / "semantic-manifest.json",
            mapping_root=SEMANTIC_MAPPING_ROOT,
        )

    detector_path.write_text("{}", encoding="utf-8")
    with pytest.raises(TransformerError, match="Detector results do not match"):
        SemanticMappingOrchestrator().generate(
            orchestration_manifest_path=manifest_path,
            detector_results_path=detector_path,
            output_root=tmp_path,
            semantic_manifest_output=tmp_path / "semantic-manifest.json",
            mapping_root=SEMANTIC_MAPPING_ROOT,
        )


@pytest.mark.parametrize(
    ("mapping_file_name", "sample_record", "expected_fields"),
    [
        (
            "nginx_access_combined.json",
            (
                '192.0.2.1 - - [20/Oct/2026:21:15:30 +0000] '
                '"GET /orders?id=7 HTTP/1.1" 200 321 "https://example.test/" '
                '"Mozilla/5.0"'
            ),
            {
                "client_address": "192.0.2.1",
                "http_request_method": "GET",
                "http_response_status_code": "200",
            },
        ),
        (
            "nginx_error.json",
            (
                "2026/10/20 21:16:01 [error] 42#43: *7 upstream timed out "
                "while reading response header"
            ),
            {"severity": "error", "process_id": "42", "connection_id": "7"},
        ),
        (
            "postgresql_stderr.json",
            "2026-10-20 21:17:02.123 UTC [84] app@orders ERROR:  duplicate key value",
            {
                "process_id": "84",
                "db_namespace": "orders",
                "severity": "ERROR",
            },
        ),
    ],
)
def test_regex_mappings_parse_representative_source_records(
    mapping_file_name: str,
    sample_record: str,
    expected_fields: dict[str, str],
) -> None:
    """Prove maintained regex mappings extract representative source fields.

    Args:
        mapping_file_name: Maintained semantic mapping resource.
        sample_record: Representative source log line.
        expected_fields: Parsed values required from the sample.
    """

    mapping = load_semantic_mapping(SEMANTIC_MAPPING_ROOT / mapping_file_name)
    parsed_match = re.match(mapping.parse["expression"], sample_record)
    assert parsed_match is not None
    for field_name, expected_value in expected_fields.items():
        assert parsed_match.group(field_name) == expected_value


def test_semantic_map_cli_dispatches_optional_stage(tmp_path: Path) -> None:
    """Expose semantic generation through the installed command-line interface."""

    detector_path, manifest_path = _render_first_stage(tmp_path, "fluent-bit", "5.1.0")
    semantic_manifest_path = tmp_path / "semantic-manifest.json"
    status = main(
        [
            COMMAND_SEMANTIC_MAP,
            "--manifest",
            str(manifest_path),
            "--detector-results",
            str(detector_path),
            "--mapping-root",
            str(SEMANTIC_MAPPING_ROOT),
            "--output-root",
            str(tmp_path),
            "--semantic-manifest-output",
            str(semantic_manifest_path),
        ]
    )
    assert status == 0
    assert semantic_manifest_path.is_file()


def test_semantic_mapping_loader_rejects_invalid_catalogue_data(tmp_path: Path) -> None:
    """Reject invalid mapping versions, constraints, regexes, and catalogue sources."""

    source_document = json.loads(NGINX_ACCESS_MAPPING_PATH.read_text(encoding="utf-8"))
    invalid_cases = [
        ("version", ("metadata", "version"), "invalid", "Invalid mapping version"),
        (
            "constraint",
            ("spec", "detector", "version_constraint"),
            "invalid",
            "Invalid detector version constraint",
        ),
        (
            "regex",
            ("spec", "source", "path_regex"),
            "[invalid",
            "Invalid path regular expression",
        ),
    ]
    for case_name, key_path, invalid_value, expected_message in invalid_cases:
        invalid_document = json.loads(json.dumps(source_document))
        destination: dict[str, Any] = invalid_document
        for path_segment in key_path[:-1]:
            destination = destination[path_segment]
        destination[key_path[-1]] = invalid_value
        invalid_path = write_text(
            tmp_path / f"{case_name}.json",
            json.dumps(invalid_document),
        )
        with pytest.raises(TransformerError, match=expected_message):
            load_semantic_mapping(invalid_path)

    with pytest.raises(TransformerError, match="not both"):
        load_semantic_mapping_catalogue(tmp_path, [NGINX_ACCESS_MAPPING_PATH])
    with pytest.raises(TransformerError, match="not a directory"):
        load_semantic_mapping_catalogue(tmp_path / "missing", [])
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    with pytest.raises(TransformerError, match="At least one"):
        load_semantic_mapping_catalogue(empty_root, [])

    mapping = load_semantic_mapping(NGINX_ACCESS_MAPPING_PATH)
    plugin = {
        "plugin_id": "nginx.logs-000000000000",
        "source_format": "nginx.auto",
        "properties": {"path": "/var/log/nginx/unknown.log"},
    }
    with pytest.raises(TransformerError, match="No semantic mapping"):
        select_semantic_mapping([mapping], "nginx_1", "1.0.0", plugin)
    with pytest.raises(TransformerError, match="Invalid detector version"):
        select_semantic_mapping([mapping], "nginx_1", "invalid", plugin)


def test_csv_mapping_generates_both_agent_formats() -> None:
    """Cover CSV parsing, pathless plugins, and scalar Lua attribute values."""

    mapping = load_semantic_mapping(POSTGRESQL_CSV_MAPPING_PATH)
    mapping = replace(
        mapping,
        record_attributes={
            **mapping.record_attributes,
            "test.boolean": False,
            "test.number": 3,
        },
    )
    semantic_plugin = SemanticPlugin(
        detector_name="postgresql_17",
        detector_version="1.0.0",
        plugin={
            "plugin_id": "postgresql.csv-000000000000",
            "detector_link": "detector://postgresql_17/1.0.0/logs/0",
            "properties": {"name": "tail", "start_at": "beginning"},
        },
        mapping=mapping,
    )
    fluent_artifacts = FluentBitSemanticAdapter().generate([semantic_plugin])
    collector_artifacts = OpenTelemetryCollectorSemanticAdapter().generate(
        [semantic_plugin]
    )
    assert b"format: csv" in fluent_artifacts[0].content
    assert b"test.boolean" in fluent_artifacts[1].content
    assert b"csv_parser" in collector_artifacts[0].content

    no_timestamp_plugin = replace(
        semantic_plugin,
        mapping=replace(
            mapping,
            parse={
                "type": "regex",
                "expression": "^(?P<count>\\d+)$",
                "types": {"count": "integer"},
            },
        ),
    )
    assert FluentBitSemanticAdapter().generate([no_timestamp_plugin])
    assert OpenTelemetryCollectorSemanticAdapter().generate([no_timestamp_plugin])
