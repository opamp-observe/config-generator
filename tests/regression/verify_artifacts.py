# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Validate detector and transformer artifacts produced by the regression image."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

ARTIFACTS_KEY = "artifacts"
DETECTED_KEY = "detected"
DETECTOR_NAME_KEY = "detector_name"
DETECTORS_KEY = "detectors"
ERRORS_KEY = "errors"
INCLUDE_KEY = "include"
INCLUDES_KEY = "includes"
INPUTS_KEY = "inputs"
LOG_LOCATIONS_KEY = "log_locations"
PATH_KEY = "path"
PIPELINE_KEY = "pipeline"
PLUGIN_COUNT_KEY = "plugin_count"
QUERIES_KEY = "queries"
SELECTION_STATUS_KEY = "selection_status"
SHA256_KEY = "sha256"
TRANSFORM_NAME_KEY = "transform_name"

EXPECTED_DETECTORS = frozenset(("nginx_1", "postgresql_17"))
EXPECTED_TRANSFORMS = {
    "fluent-bit": frozenset(("fluent_bit_5_nginx_1", "fluent_bit_5_postgresql_17")),
    "otelcol-contrib": frozenset(
        ("otelcol_contrib_0_163_nginx_1", "otelcol_contrib_0_163_postgresql_17")
    ),
}
EXPECTED_ARTIFACT_PATHS = frozenset(
    (
        "generated/fluent-bit/nginx.inputs.yaml",
        "generated/fluent-bit/postgresql_17.inputs.yaml",
    )
)
EXPECTED_OTELCOL_ARTIFACT_PATHS = frozenset(
    (
        "generated/otelcol-contrib/nginx.yaml",
        "generated/otelcol-contrib/postgresql_17.yaml",
    )
)
EXPECTED_SEMANTIC_ARTIFACTS = {
    "fluent-bit": frozenset(
        (
            "generated/fluent-bit/semantic-normalization.yaml",
            "generated/fluent-bit/semantic-normalization.lua",
        )
    ),
    "otelcol-contrib": frozenset(
        ("generated/otelcol-contrib/semantic-normalization.yaml",)
    ),
}
RENDERED_SELECTION_STATUS = "rendered"
REPORT_ARTIFACTS_KEY = "artifacts"
REPORT_DETECTORS_KEY = "detectors"
REPORT_STATUS_KEY = "status"
REPORT_TRANSFORMS_KEY = "transforms"
REPORT_PASSED_STATUS = "passed"
UTF8_ENCODING = "utf-8"
VERIFICATION_FILE_NAME = "regression-verification.json"


class RegressionValidationError(RuntimeError):
    """Describe a missing or inconsistent regression artifact."""


def load_json_object(file_path: Path) -> dict[str, Any]:
    """Load one required JSON object.

    Args:
        file_path: Artifact path expected to contain a JSON object.

    Returns:
        Parsed JSON mapping.

    Raises:
        RegressionValidationError: The artifact is missing or malformed.
    """

    try:
        loaded_value = json.loads(file_path.read_text(encoding=UTF8_ENCODING))
    except (OSError, json.JSONDecodeError) as error:
        raise RegressionValidationError(f"Cannot load {file_path}: {error}") from error
    if not isinstance(loaded_value, dict):
        raise RegressionValidationError(f"Expected a JSON object in {file_path}")
    return loaded_value


def sha256_file(file_path: Path) -> str:
    """Return the hexadecimal SHA-256 digest of one artifact.

    Args:
        file_path: Artifact whose exact bytes must match the manifest.

    Returns:
        Lowercase hexadecimal digest.
    """

    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def validate_detector_results(detector_results: dict[str, Any]) -> None:
    """Require successful NGINX and PostgreSQL detection with log evidence.

    Args:
        detector_results: Aggregate document produced by the detector runner.

    Raises:
        RegressionValidationError: A detector is absent, false, errored, or empty.
    """

    detector_entries = detector_results.get(DETECTORS_KEY)
    if not isinstance(detector_entries, list):
        raise RegressionValidationError("Detector results do not contain a detector list")
    detectors_by_name = {
        entry.get(DETECTOR_NAME_KEY): entry
        for entry in detector_entries
        if isinstance(entry, dict)
    }
    if set(detectors_by_name) != EXPECTED_DETECTORS:
        raise RegressionValidationError("Detector results do not contain the expected products")
    for detector_name in sorted(EXPECTED_DETECTORS):
        detector = detectors_by_name[detector_name]
        if detector.get(DETECTED_KEY) is not True:
            raise RegressionValidationError(f"Detector did not match: {detector_name}")
        if detector.get(ERRORS_KEY):
            raise RegressionValidationError(f"Detector reported errors: {detector_name}")
        queries = detector.get(QUERIES_KEY)
        if not isinstance(queries, dict) or not queries.get(LOG_LOCATIONS_KEY):
            raise RegressionValidationError(f"Detector has no log evidence: {detector_name}")


def validate_orchestration(
    artifact_root: Path,
    manifest: dict[str, Any],
    expected_artifact_paths: frozenset[str],
    target_tool: str,
) -> None:
    """Require rendered, checksummed artifacts for both product transforms.

    Args:
        artifact_root: Directory containing the generated artifact tree.
        manifest: Orchestration JSON emitted by the transformer.
        expected_artifact_paths: Exact target-specific first-stage paths.
        target_tool: Agent whose transform identities are expected.

    Raises:
        RegressionValidationError: A fragment or manifest record is inconsistent.
    """

    artifact_entries = manifest.get(ARTIFACTS_KEY)
    if not isinstance(artifact_entries, list):
        raise RegressionValidationError("Manifest does not contain an artifact list")
    transform_names = {
        artifact.get(TRANSFORM_NAME_KEY)
        for artifact in artifact_entries
        if isinstance(artifact, dict)
    }
    if transform_names != EXPECTED_TRANSFORMS[target_tool]:
        raise RegressionValidationError("Manifest does not contain both transforms")

    yaml_parser = YAML(typ="safe")
    generated_paths: set[str] = set()
    for artifact in artifact_entries:
        artifact_path_value = artifact[PATH_KEY]
        generated_paths.add(artifact_path_value)
        artifact_path = artifact_root / artifact_path_value
        if not artifact_path.is_file():
            raise RegressionValidationError(f"Generated artifact is missing: {artifact_path}")
        if sha256_file(artifact_path) != artifact[SHA256_KEY]:
            raise RegressionValidationError(f"Generated artifact checksum changed: {artifact_path}")
        if artifact[SELECTION_STATUS_KEY] != RENDERED_SELECTION_STATUS:
            raise RegressionValidationError(f"Transform was not rendered: {artifact_path_value}")
        if artifact[PLUGIN_COUNT_KEY] < 1:
            raise RegressionValidationError(f"Transform emitted no plugins: {artifact_path_value}")
        fragment = yaml_parser.load(artifact_path.read_text(encoding=UTF8_ENCODING))
        if PIPELINE_KEY in fragment and not fragment[PIPELINE_KEY][INPUTS_KEY]:
            raise RegressionValidationError(f"Fragment contains no inputs: {artifact_path_value}")
        plugin_records = artifact.get("plugins")
        if not isinstance(plugin_records, list) or not plugin_records:
            raise RegressionValidationError(
                f"Artifact has no plugin provenance: {artifact_path_value}"
            )
        for plugin_record in plugin_records:
            if not plugin_record.get("human_link") or not str(
                plugin_record.get("detector_link", "")
            ).startswith("detector://"):
                raise RegressionValidationError("Plugin provenance is not human/machine linked")
    if generated_paths != expected_artifact_paths:
        raise RegressionValidationError("Unexpected generated fragment paths")


def validate_parent(artifact_root: Path, manifest: dict[str, Any]) -> None:
    """Require the assembled parent to include every manifest fragment.

    Args:
        artifact_root: Directory containing the assembled Fluent Bit parent.
        manifest: Orchestration manifest containing literal include paths.

    Raises:
        RegressionValidationError: The parent omits a generated fragment.
    """

    parent_path = artifact_root / "fluent-bit-source.yaml"
    yaml_parser = YAML(typ="safe")
    parent = yaml_parser.load(parent_path.read_text(encoding=UTF8_ENCODING))
    expected_includes = {
        artifact[INCLUDE_KEY][PATH_KEY] for artifact in manifest[ARTIFACTS_KEY]
    }
    if set(parent.get(INCLUDES_KEY, [])) != expected_includes:
        raise RegressionValidationError("Assembled parent does not include both fragments")


def validate_semantic_manifest(
    artifact_root: Path,
    manifest: dict[str, Any],
    target_tool: str,
) -> None:
    """Require checksummed second-stage artifacts for every mapped log input.

    Args:
        artifact_root: Directory containing generated semantic artifacts.
        manifest: Semantic-stage manifest to verify.
        target_tool: Expected agent implementation name.

    Raises:
        RegressionValidationError: Mapping records or generated files are inconsistent.
    """

    if manifest.get("target", {}).get("tool") != target_tool:
        raise RegressionValidationError(f"Unexpected semantic target: {target_tool}")
    if manifest.get("target", {}).get("plugin_count", 0) < 3:
        raise RegressionValidationError(f"Semantic stage mapped too few {target_tool} inputs")
    mapping_names = {
        mapping.get("mapping_name") for mapping in manifest.get("mappings", [])
    }
    required_mapping_names = {
        "nginx_access_combined",
        "nginx_error",
        "postgresql_stderr",
    }
    if not required_mapping_names.issubset(mapping_names):
        raise RegressionValidationError(f"Semantic mappings are incomplete for {target_tool}")
    artifact_paths: set[str] = set()
    for artifact in manifest.get(ARTIFACTS_KEY, []):
        artifact_path_value = artifact[PATH_KEY]
        artifact_paths.add(artifact_path_value)
        artifact_path = artifact_root / artifact_path_value
        if not artifact_path.is_file() or sha256_file(artifact_path) != artifact[SHA256_KEY]:
            raise RegressionValidationError(
                f"Semantic artifact is missing or changed: {artifact_path_value}"
            )
    if artifact_paths != EXPECTED_SEMANTIC_ARTIFACTS[target_tool]:
        raise RegressionValidationError(f"Unexpected semantic artifacts for {target_tool}")


def write_verification_report(artifact_root: Path) -> None:
    """Write a compact success report after every artifact check passes.

    Args:
        artifact_root: Directory that receives the verification report.
    """

    report = {
        REPORT_STATUS_KEY: REPORT_PASSED_STATUS,
        REPORT_DETECTORS_KEY: sorted(EXPECTED_DETECTORS),
        REPORT_TRANSFORMS_KEY: sorted(set().union(*EXPECTED_TRANSFORMS.values())),
        REPORT_ARTIFACTS_KEY: sorted(
            EXPECTED_ARTIFACT_PATHS
            | EXPECTED_OTELCOL_ARTIFACT_PATHS
            | set().union(*EXPECTED_SEMANTIC_ARTIFACTS.values())
        ),
    }
    report_path = artifact_root / VERIFICATION_FILE_NAME
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding=UTF8_ENCODING)


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the regression artifact validator argument parser.

    Returns:
        Parser requiring the mounted artifact root.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-root", type=Path, required=True)
    return parser


def main(arguments: list[str] | None = None) -> int:
    """Validate every regression artifact and write a success report.

    Args:
        arguments: Optional command-line arguments without the program name.

    Returns:
        Zero after every assertion succeeds.
    """

    parsed_arguments = build_argument_parser().parse_args(arguments)
    artifact_root = parsed_arguments.artifact_root
    detector_results = load_json_object(artifact_root / "detector-results.json")
    fluent_bit_manifest = load_json_object(
        artifact_root / "orchestration-fluent-bit.json"
    )
    otelcol_manifest = load_json_object(artifact_root / "orchestration-otelcol.json")
    fluent_bit_semantic_manifest = load_json_object(
        artifact_root / "semantic-manifest-fluent-bit.json"
    )
    otelcol_semantic_manifest = load_json_object(
        artifact_root / "semantic-manifest-otelcol.json"
    )
    validate_detector_results(detector_results)
    validate_orchestration(
        artifact_root,
        fluent_bit_manifest,
        EXPECTED_ARTIFACT_PATHS,
        "fluent-bit",
    )
    validate_orchestration(
        artifact_root,
        otelcol_manifest,
        EXPECTED_OTELCOL_ARTIFACT_PATHS,
        "otelcol-contrib",
    )
    validate_parent(artifact_root, fluent_bit_manifest)
    validate_semantic_manifest(
        artifact_root,
        fluent_bit_semantic_manifest,
        "fluent-bit",
    )
    validate_semantic_manifest(
        artifact_root,
        otelcol_semantic_manifest,
        "otelcol-contrib",
    )
    write_verification_report(artifact_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
