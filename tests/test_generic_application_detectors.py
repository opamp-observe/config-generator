# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Contract tests for generic web, runtime, and embedded-database detectors."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DETECTORS_ROOT = REPOSITORY_ROOT / "detectors"
DETECTOR_FILE_NAME = "detector.json"
LINUX_PLATFORM_NAME = "linux"
WINDOWS_PLATFORM_NAME = "windows"
PACKS_KEY = "packs"
OUTPUT_CONTRACT_KEY = "output_contract"
REQUIRED_QUERIES_KEY = "required_queries"
QUERIES_KEY = "queries"
QUERY_KEY = "query"
DESCRIPTION_KEY = "description"
DOCUMENTATION_KEY = "documentation"
METRICS_OUTPUTS_QUERY_NAME = "metrics_outputs"
SERVICE_STATE_QUERY_NAME = "service_state"
GENERIC_DETECTOR_PATHS = (
    Path("apache_http_server/1"),
    Path("java_app/1"),
    Path("nginx/1"),
    Path("nodejs_app/1"),
    Path("python_app/1"),
    Path("sqlite/1"),
)
OBSERVABILITY_QUERY_NAMES = {
    "configuration_files",
    "log_locations",
    "metrics_outputs",
    "network_ports",
    "runtime",
    "service_state",
    "unique_identifiers",
    "version_evidence",
}
REQUIRED_DOCUMENTATION_PREFIX = "https://"
METRICS_STATUS_MARKERS = ("candidate", "observed", "none_native", "review")


def load_json_object(file_path: Path) -> dict[str, Any]:
    """Load one manifest or pack and require a top-level JSON object.

    Args:
        file_path: Repository file containing the JSON document to load.
    """

    loaded_value = json.loads(file_path.read_text(encoding="utf-8"))
    assert isinstance(loaded_value, dict)
    return loaded_value


def test_generic_detectors_publish_complete_observability_contracts() -> None:
    """Require both platform packs to publish the requested evidence queries."""

    for detector_path in GENERIC_DETECTOR_PATHS:
        detector_directory = DETECTORS_ROOT / detector_path
        manifest = load_json_object(detector_directory / DETECTOR_FILE_NAME)
        required_query_names = set(
            manifest[OUTPUT_CONTRACT_KEY][REQUIRED_QUERIES_KEY]
        )
        assert required_query_names == OBSERVABILITY_QUERY_NAMES
        assert all(
            source.startswith(REQUIRED_DOCUMENTATION_PREFIX)
            for source in manifest[DOCUMENTATION_KEY]
        )

        for platform_name in (LINUX_PLATFORM_NAME, WINDOWS_PLATFORM_NAME):
            pack_path = detector_directory / manifest[PACKS_KEY][platform_name]
            pack = load_json_object(pack_path)
            query_names = set(pack[QUERIES_KEY])
            assert query_names == OBSERVABILITY_QUERY_NAMES
            metrics_query = pack[QUERIES_KEY][METRICS_OUTPUTS_QUERY_NAME]
            metrics_text = (
                metrics_query[QUERY_KEY] + " " + metrics_query[DESCRIPTION_KEY]
            ).lower()
            assert any(marker in metrics_text for marker in METRICS_STATUS_MARKERS)


def test_sqlite_detector_does_not_invent_native_service_or_metrics() -> None:
    """Keep SQLite modelled as an embedded library instead of a fake daemon."""

    detector_directory = DETECTORS_ROOT / Path("sqlite/1")
    manifest = load_json_object(detector_directory / DETECTOR_FILE_NAME)
    for platform_name in (LINUX_PLATFORM_NAME, WINDOWS_PLATFORM_NAME):
        pack_path = detector_directory / manifest[PACKS_KEY][platform_name]
        pack = load_json_object(pack_path)
        service_query = pack[QUERIES_KEY][SERVICE_STATE_QUERY_NAME][QUERY_KEY]
        metrics_query = pack[QUERIES_KEY][METRICS_OUTPUTS_QUERY_NAME][QUERY_KEY]
        assert "owning_application" in service_query
        assert "none_native" in metrics_query
