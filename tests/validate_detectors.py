# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Validate detector manifests, osquery packs, and current-platform SQL."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DETECTORS_ROOT = REPOSITORY_ROOT / "detectors"
SCHEMAS_ROOT = REPOSITORY_ROOT / "schemas"
MASTER_SCHEMA_PATH = SCHEMAS_ROOT / "detector_results.schema.json"
JSON_SCHEMA_DRAFT_URI = "https://json-schema.org/draft/2020-12/schema"
RESULT_SCHEMA_KEY = "result_schema"
SCHEMA_PROPERTIES_KEY = "properties"
SCHEMA_CONST_KEY = "const"
SCHEMA_REFERENCE_KEY = "$ref"
HOST_LEVEL_DETECTOR_NAMES = {"host_inventory_1", "linux_system_1"}
WEBLOGIC_DETECTOR_PREFIX = "weblogic_"
PRODUCT_REQUIRED_QUERY_NAMES = {
    "runtime",
    "network_ports",
    "configuration_files",
    "log_locations",
}
WEBLOGIC_REQUIRED_QUERY_NAMES = {
    "observability_urls",
    "jvm_runtime",
    "java_monitoring_endpoints",
}
OBSERVABILITY_REQUIRED_QUERY_NAMES = {
    "log_locations",
    "metrics_outputs",
    "service_state",
    "unique_identifiers",
}
OBSERVABILITY_DETECTOR_NAMES = {
    "apache_http_server_1",
    "java_app_1",
    "nginx_1",
    "nodejs_app_1",
    "python_app_1",
    "sqlite_1",
}
SUPPORTED_PLATFORMS = {"linux", "windows"}


def load_object(file_path: Path) -> dict[str, Any]:
    """Load a JSON object used by the detector validation suite."""

    loaded_value = json.loads(file_path.read_text(encoding="utf-8"))
    if not isinstance(loaded_value, dict):
        raise TypeError(f"{file_path} does not contain a JSON object")
    return loaded_value


def current_platform_name() -> str:
    """Return the detector platform name used for SQL validation."""

    return "windows" if os.name == "nt" else "linux"


def validate_manifest(manifest_path: Path, seen_names: set[str]) -> dict[str, Any]:
    """Validate one detector manifest and return its parsed object."""

    manifest = load_object(manifest_path)
    detector = manifest["detector"]
    product = manifest["product"]
    detector_name = detector["name"]
    assert detector_name not in seen_names, f"Duplicate detector name: {detector_name}"
    seen_names.add(detector_name)
    assert detector["version"], f"Missing detector version in {manifest_path}"
    assert product["name"], f"Missing product name in {manifest_path}"
    assert product["version"], f"Missing product version in {manifest_path}"
    declared_platforms = set(manifest["supported_platforms"])
    configured_platforms = set(manifest["packs"])
    assert declared_platforms, f"No supported platforms in {manifest_path}"
    assert declared_platforms.issubset(SUPPORTED_PLATFORMS), (
        f"Unsupported platform in {manifest_path}: "
        f"{sorted(declared_platforms - SUPPORTED_PLATFORMS)}"
    )
    assert configured_platforms == declared_platforms, (
        f"Pack platforms do not match supported platforms in {manifest_path}"
    )
    assert manifest.get(RESULT_SCHEMA_KEY), (
        f"Missing detector result schema reference in {manifest_path}"
    )
    assert manifest["documentation"], f"Missing documentation sources in {manifest_path}"
    required_query_names = set(manifest["output_contract"]["required_queries"])
    assert required_query_names, f"Empty output contract in {manifest_path}"
    if detector_name not in HOST_LEVEL_DETECTOR_NAMES:
        assert PRODUCT_REQUIRED_QUERY_NAMES.issubset(required_query_names), (
            f"Unexpected product-detector output contract in {manifest_path}"
        )
    if detector_name.startswith(WEBLOGIC_DETECTOR_PREFIX):
        assert WEBLOGIC_REQUIRED_QUERY_NAMES.issubset(required_query_names), (
            f"WebLogic observability queries missing from {manifest_path}"
        )
    if detector_name in OBSERVABILITY_DETECTOR_NAMES:
        assert OBSERVABILITY_REQUIRED_QUERY_NAMES.issubset(required_query_names), (
            f"Observability queries missing from {manifest_path}"
        )
    return manifest


def run_config_check(osquery_executable: str, pack_path: Path) -> None:
    """Ask osquery's config parser to validate one pack reference."""

    config_document = {
        "options": {"disable_events": "true"},
        "packs": {"detector_validation": str(pack_path.resolve())},
    }
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".conf",
        delete=False,
    ) as temporary_config:
        json.dump(config_document, temporary_config)
        temporary_path = Path(temporary_config.name)
    try:
        completed_process = subprocess.run(
            [
                osquery_executable,
                "--config_path",
                str(temporary_path),
                "--config_check",
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        diagnostic = completed_process.stderr.strip() or completed_process.stdout.strip()
        assert completed_process.returncode == 0, (
            f"osquery config validation failed for {pack_path}: {diagnostic}"
        )
    finally:
        temporary_path.unlink(missing_ok=True)


def validate_current_platform_sql(
    osquery_executable: str,
    pack: dict[str, Any],
    pack_path: Path,
) -> None:
    """Execute discovery and detail SQL on the current operating system."""

    sql_entries: list[tuple[str, str]] = [
        (f"discovery_{index}", query)
        for index, query in enumerate(pack.get("discovery", []))
    ]
    sql_entries.extend(
        (query_name, specification["query"])
        for query_name, specification in pack["queries"].items()
    )
    for query_name, query in sql_entries:
        completed_process = subprocess.run(
            [osquery_executable, "--json", query],
            capture_output=True,
            check=False,
            text=True,
        )
        diagnostic = completed_process.stderr.strip() or completed_process.stdout.strip()
        assert completed_process.returncode == 0, (
            f"SQL validation failed for {pack_path}:{query_name}: {diagnostic}"
        )
        json.loads(completed_process.stdout or "[]")


def validate_pack(
    osquery_executable: str,
    pack_path: Path,
    execute_sql: bool,
    required_query_names: set[str],
) -> set[str]:
    """Validate one pack and return the query names exposed by its result."""

    pack = load_object(pack_path)
    assert pack["platform"] in SUPPORTED_PLATFORMS
    assert pack.get("discovery"), f"No discovery query in {pack_path}"
    assert required_query_names.issubset(pack["queries"]), (
        f"Required queries missing from {pack_path}"
    )
    assert "configuration_and_logs" not in pack["queries"], (
        f"Legacy combined configuration/log query remains in {pack_path}"
    )
    for query_name, specification in pack["queries"].items():
        assert specification["query"].strip().endswith(";"), (
            f"{pack_path}:{query_name} must end with a semicolon"
        )
        assert int(specification["interval"]) >= 60
        assert specification["description"]
    run_config_check(osquery_executable, pack_path)
    if execute_sql:
        validate_current_platform_sql(osquery_executable, pack, pack_path)
    return set(pack["queries"])


def validate_detector_schema(
    manifest_path: Path,
    manifest: dict[str, Any],
    pack_query_names: set[str],
) -> str:
    """Validate one declared result schema against its manifest and pack queries."""

    schema_path = (manifest_path.parent / manifest[RESULT_SCHEMA_KEY]).resolve()
    assert schema_path.is_relative_to(SCHEMAS_ROOT.resolve()), (
        f"Detector schema must be below {SCHEMAS_ROOT}: {schema_path}"
    )
    assert schema_path.is_file(), f"Detector schema not found: {schema_path}"
    schema = load_object(schema_path)
    assert schema.get("$schema") == JSON_SCHEMA_DRAFT_URI, (
        f"Unexpected JSON Schema draft in {schema_path}"
    )

    detector_metadata = manifest["detector"]
    product_metadata = manifest["product"]
    schema_properties = schema[SCHEMA_PROPERTIES_KEY]
    expected_constants = {
        "detector_name": detector_metadata["name"],
        "detector_version": detector_metadata["version"],
        "product": product_metadata["name"],
        "product_version": product_metadata["version"],
        "release_status": product_metadata["release_status"],
    }
    for property_name, expected_value in expected_constants.items():
        actual_value = schema_properties[property_name][SCHEMA_CONST_KEY]
        assert actual_value == expected_value, (
            f"Schema identity mismatch for {schema_path}:{property_name}"
        )

    schema_query_names = set(
        schema_properties["queries"][SCHEMA_PROPERTIES_KEY]
    )
    assert schema_query_names == pack_query_names, (
        f"Schema query properties do not match packs for {schema_path}"
    )
    detected_query_names = set(
        schema["allOf"][0]["then"][SCHEMA_PROPERTIES_KEY]["queries"]["required"]
    )
    assert detected_query_names == pack_query_names, (
        f"Detected-result query requirements do not match packs for {schema_path}"
    )
    return schema_path.relative_to(SCHEMAS_ROOT).as_posix()


def validate_master_schema(detector_schema_references: set[str]) -> None:
    """Validate that the aggregate schema references every detector schema once."""

    master_schema = load_object(MASTER_SCHEMA_PATH)
    assert master_schema.get("$schema") == JSON_SCHEMA_DRAFT_URI, (
        f"Unexpected JSON Schema draft in {MASTER_SCHEMA_PATH}"
    )
    detector_items = master_schema[SCHEMA_PROPERTIES_KEY]["detectors"]["items"]
    master_references = {
        reference[SCHEMA_REFERENCE_KEY] for reference in detector_items["oneOf"]
    }
    assert len(master_references) == len(detector_items["oneOf"]), (
        f"Duplicate detector schema reference in {MASTER_SCHEMA_PATH}"
    )
    assert master_references == detector_schema_references, (
        f"Master schema references do not match detector schemas in {MASTER_SCHEMA_PATH}"
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Create command-line arguments for detector validation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--osquery", default="osqueryi")
    parser.add_argument(
        "--config-only",
        action="store_true",
        help="Skip live SQL execution and only run osquery config checks.",
    )
    return parser


def main(arguments: list[str] | None = None) -> int:
    """Validate every detector and return a process status."""

    parsed_arguments = build_argument_parser().parse_args(arguments)
    osquery_executable = shutil.which(parsed_arguments.osquery)
    if not osquery_executable:
        print(f"osquery executable not found: {parsed_arguments.osquery}", file=sys.stderr)
        return 1

    manifest_paths = sorted(DETECTORS_ROOT.glob("*/*/detector.json"))
    if not manifest_paths:
        print("No detector manifests found.", file=sys.stderr)
        return 1

    seen_names: set[str] = set()
    detector_schema_references: set[str] = set()
    current_platform = current_platform_name()
    for manifest_path in manifest_paths:
        manifest = validate_manifest(manifest_path, seen_names)
        platform_query_names: dict[str, set[str]] = {}
        for platform_name, relative_pack_path in manifest["packs"].items():
            pack_path = manifest_path.parent / relative_pack_path
            platform_query_names[platform_name] = validate_pack(
                osquery_executable,
                pack_path,
                execute_sql=(
                    platform_name == current_platform and not parsed_arguments.config_only
                ),
                required_query_names=set(
                    manifest["output_contract"]["required_queries"]
                ),
            )
        unique_query_sets = {frozenset(names) for names in platform_query_names.values()}
        assert len(unique_query_sets) == 1, (
            f"Platform query names differ in {manifest_path}"
        )
        schema_reference = validate_detector_schema(
            manifest_path,
            manifest,
            set(next(iter(unique_query_sets))),
        )
        assert schema_reference not in detector_schema_references, (
            f"Detector schema is declared more than once: {schema_reference}"
        )
        detector_schema_references.add(schema_reference)

    validate_master_schema(detector_schema_references)

    print(
        f"Validated {len(manifest_paths)} detectors and result schemas "
        f"with {osquery_executable}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
