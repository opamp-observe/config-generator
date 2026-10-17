# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Run every applicable osquery detector and aggregate its results."""

from __future__ import annotations

import argparse
import datetime as datetime_module
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger("detector_runner")
SCHEMA_VERSION = "1.0"
MANIFEST_FILE_NAME = "detector.json"
DETECTORS_DIRECTORY_NAME = "detectors"
DEFAULT_OUTPUT_FILE_NAME = "detector-results.json"
LINUX_PLATFORM_NAME = "linux"
WINDOWS_PLATFORM_NAME = "windows"
OSQUERY_EXECUTABLE_NAMES = ("osqueryi", "osqueryi.exe")


class DetectorRunnerError(RuntimeError):
    """Describe a detector runner failure that should be shown to the caller."""


def configure_logging() -> None:
    """Configure debug logging for detector selection and osquery execution."""

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def resolve_platform_name() -> str:
    """Return the detector platform name for the current operating system."""

    if os.name == "nt":
        return WINDOWS_PLATFORM_NAME
    if sys.platform.startswith(LINUX_PLATFORM_NAME):
        return LINUX_PLATFORM_NAME
    raise DetectorRunnerError(f"Unsupported operating system: {platform.system()}")


def resolve_osquery_executable(explicit_path: str | None) -> str:
    """Find osqueryi, preferring the path supplied by the caller."""

    if explicit_path:
        explicit_candidate = Path(explicit_path).expanduser()
        if explicit_candidate.is_file():
            # Preserve an osqueryi symlink. The shared osquery binary selects
            # interactive versus daemon behavior from argv[0].
            return str(explicit_candidate.absolute())
        resolved_explicit = shutil.which(explicit_path)
        if resolved_explicit:
            return resolved_explicit
        raise DetectorRunnerError(f"osqueryi was not found at: {explicit_path}")

    for executable_name in OSQUERY_EXECUTABLE_NAMES:
        resolved_candidate = shutil.which(executable_name)
        if resolved_candidate:
            return resolved_candidate

    raise DetectorRunnerError(
        "osqueryi was not found on PATH; install osquery or pass --osquery."
    )


def load_json_file(file_path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object from the specified file."""

    try:
        loaded_value = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DetectorRunnerError(f"Cannot read JSON file {file_path}: {error}") from error
    if not isinstance(loaded_value, dict):
        raise DetectorRunnerError(f"Expected a JSON object in {file_path}")
    return loaded_value


def find_detector_manifests(detectors_root: Path) -> list[Path]:
    """Return detector manifests in deterministic detector-name order."""

    return sorted(detectors_root.glob(f"*/*/{MANIFEST_FILE_NAME}"))


def run_osquery_query(
    osquery_executable: str,
    query: str,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    """Execute one SQL query with osqueryi and return its JSON rows."""

    LOGGER.debug("Running osquery SQL: %s", query)
    completed_process = subprocess.run(
        [osquery_executable, "--json", query],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    if completed_process.returncode != 0:
        diagnostic = completed_process.stderr.strip() or completed_process.stdout.strip()
        raise DetectorRunnerError(
            f"osquery exited with {completed_process.returncode}: {diagnostic}"
        )
    try:
        rows = json.loads(completed_process.stdout or "[]")
    except json.JSONDecodeError as error:
        raise DetectorRunnerError(f"osquery returned invalid JSON: {error}") from error
    if not isinstance(rows, list):
        raise DetectorRunnerError("osquery returned JSON that was not a row array")
    return rows


def run_discovery_queries(
    osquery_executable: str,
    discovery_queries: list[str],
    timeout_seconds: int,
) -> tuple[bool, list[dict[str, Any]], list[str]]:
    """Run pack discovery queries and require every query to return a row."""

    evidence: list[dict[str, Any]] = []
    errors: list[str] = []
    for discovery_query in discovery_queries:
        try:
            rows = run_osquery_query(
                osquery_executable,
                discovery_query,
                timeout_seconds,
            )
            evidence.append({"query": discovery_query, "rows": rows})
            if not rows:
                return False, evidence, errors
        except DetectorRunnerError as error:
            errors.append(str(error))
            return False, evidence, errors
    return True, evidence, errors


def run_detector(
    manifest_path: Path,
    current_platform: str,
    osquery_executable: str,
    timeout_seconds: int,
    include_undetected: bool,
) -> dict[str, Any]:
    """Run one detector manifest and return its self-identifying result object."""

    manifest = load_json_file(manifest_path)
    detector_metadata = manifest["detector"]
    product_metadata = manifest["product"]
    pack_relative_path = manifest["packs"].get(current_platform)
    result: dict[str, Any] = {
        "detector_name": detector_metadata["name"],
        "detector_version": detector_metadata["version"],
        "product": product_metadata["name"],
        "product_version": product_metadata["version"],
        "release_status": product_metadata.get("release_status", "stable"),
        "platform": current_platform,
        "detected": False,
        "discovery_evidence": [],
        "queries": {},
        "errors": [],
    }
    if not pack_relative_path:
        result["errors"].append(f"No {current_platform} pack is configured")
        return result

    pack_path = manifest_path.parent / pack_relative_path
    pack = load_json_file(pack_path)
    discovery_queries = pack.get("discovery", [])
    detected, evidence, discovery_errors = run_discovery_queries(
        osquery_executable,
        discovery_queries,
        timeout_seconds,
    )
    result["detected"] = detected
    result["discovery_evidence"] = evidence
    result["errors"].extend(discovery_errors)

    if not detected and not include_undetected:
        return result

    for query_name, query_specification in pack.get("queries", {}).items():
        try:
            result["queries"][query_name] = run_osquery_query(
                osquery_executable,
                query_specification["query"],
                timeout_seconds,
            )
        except DetectorRunnerError as error:
            result["errors"].append(f"{query_name}: {error}")
            result["queries"][query_name] = []

    return result


def select_manifest_paths(
    manifest_paths: list[Path],
    requested_detector_names: set[str],
) -> list[Path]:
    """Filter manifests by detector name and reject unknown requested names."""

    if not requested_detector_names:
        return manifest_paths

    selected_paths: list[Path] = []
    found_names: set[str] = set()
    for manifest_path in manifest_paths:
        manifest = load_json_file(manifest_path)
        detector_name = manifest["detector"]["name"]
        if detector_name in requested_detector_names:
            selected_paths.append(manifest_path)
            found_names.add(detector_name)

    missing_names = requested_detector_names - found_names
    if missing_names:
        raise DetectorRunnerError(
            "Unknown detector name(s): " + ", ".join(sorted(missing_names))
        )
    return selected_paths


def build_argument_parser() -> argparse.ArgumentParser:
    """Create the command-line parser for the detector runner."""

    parser = argparse.ArgumentParser(
        description="Run osquery technology detectors and aggregate JSON results."
    )
    parser.add_argument(
        "--detectors-root",
        type=Path,
        default=Path(__file__).resolve().parent / DETECTORS_DIRECTORY_NAME,
        help="Base detectors directory.",
    )
    parser.add_argument(
        "--detector",
        action="append",
        default=[],
        help="Run only this detector name; repeat to select multiple detectors.",
    )
    parser.add_argument(
        "--include-undetected",
        action="store_true",
        help="Run detail queries even when exact version discovery has no evidence.",
    )
    parser.add_argument(
        "--osquery",
        help="Path or command name for osqueryi.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT_FILE_NAME),
        help="Aggregate JSON output path.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="Maximum runtime for each osquery query.",
    )
    return parser


def main(arguments: list[str] | None = None) -> int:
    """Run selected detectors, write aggregate JSON, and return a process status."""

    configure_logging()
    parsed_arguments = build_argument_parser().parse_args(arguments)
    try:
        current_platform = resolve_platform_name()
        osquery_executable = resolve_osquery_executable(parsed_arguments.osquery)
        manifest_paths = find_detector_manifests(parsed_arguments.detectors_root)
        selected_paths = select_manifest_paths(
            manifest_paths,
            set(parsed_arguments.detector),
        )
        if not selected_paths:
            raise DetectorRunnerError(
                f"No detector manifests found below {parsed_arguments.detectors_root}"
            )

        detector_results = [
            run_detector(
                manifest_path,
                current_platform,
                osquery_executable,
                parsed_arguments.timeout_seconds,
                parsed_arguments.include_undetected,
            )
            for manifest_path in selected_paths
        ]
        output_document = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime_module.datetime.now(
                datetime_module.timezone.utc
            ).isoformat(),
            "host": {
                "hostname": platform.node(),
                "operating_system": platform.system(),
                "platform": current_platform,
            },
            "detectors": detector_results,
        }
        parsed_arguments.output.parent.mkdir(parents=True, exist_ok=True)
        parsed_arguments.output.write_text(
            json.dumps(output_document, indent=2) + "\n",
            encoding="utf-8",
        )
        LOGGER.info("Wrote %s detector results to %s", len(detector_results), parsed_arguments.output)
        return 0
    except (DetectorRunnerError, OSError, subprocess.TimeoutExpired) as error:
        LOGGER.error("%s", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

