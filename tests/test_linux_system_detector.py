# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Contract tests for the Linux system capabilities detector."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import validate_detectors

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DETECTOR_DIRECTORY = REPOSITORY_ROOT / "detectors" / "linux_system" / "1"
MANIFEST_PATH = DETECTOR_DIRECTORY / "detector.json"
LINUX_PACK_PATH = DETECTOR_DIRECTORY / "packs" / "linux.conf"
DETECTOR_KEY = "detector"
DETECTOR_NAME_KEY = "name"
DOCUMENTATION_KEY = "documentation"
OUTPUT_CONTRACT_KEY = "output_contract"
PACKS_KEY = "packs"
PLATFORM_KEY = "platform"
QUERIES_KEY = "queries"
QUERY_KEY = "query"
REQUIRED_QUERIES_KEY = "required_queries"
SUPPORTED_PLATFORMS_KEY = "supported_platforms"
TEMPORARY_MANIFEST_FILE_NAME = "detector.json"
UNSUPPORTED_PACK_PATH = "packs/plan9.conf"
UNSUPPORTED_PLATFORM_NAME = "plan9"
LINUX_PLATFORM_NAME = "linux"
LINUX_SYSTEM_DETECTOR_NAME = "linux_system_1"
KERNEL_LOG_ACCESS_QUERY_NAME = "kernel_log_access"
SYSLOG_AVAILABILITY_QUERY_NAME = "syslog_availability"
EXPECTED_QUERY_NAMES = {
    "dns_resolvers",
    "kernel_information",
    "kernel_log_access",
    "listening_sockets",
    "network_interfaces",
    "network_protocols",
    "network_routes",
    "syslog_availability",
}
NETWORK_TABLE_NAMES = {
    "dns_resolvers",
    "interface_addresses",
    "interface_details",
    "listening_ports",
    "routes",
}
KERNEL_LOG_SOURCE_PATHS = {
    "/dev/kmsg",
    "/proc/kmsg",
    "/run/log/journal",
    "/var/log/journal",
    "/var/log/kern.log",
    "/var/log/messages",
}
SYSLOG_PROVIDER_NAMES = {"rsyslogd", "syslog-ng", "syslogd", "systemd-journald"}


def load_json_object(file_path: Path) -> dict[str, object]:
    """Load a checked-in detector JSON object.

    Args:
        file_path: Detector manifest or pack path to decode.
    """

    loaded_value = json.loads(file_path.read_text(encoding="utf-8"))
    assert isinstance(loaded_value, dict)
    return loaded_value


def test_linux_detector_is_separate_and_linux_only() -> None:
    """Keep the detailed Linux contract separate from portable host inventory."""

    manifest = load_json_object(MANIFEST_PATH)
    assert manifest[DETECTOR_KEY][DETECTOR_NAME_KEY] == LINUX_SYSTEM_DETECTOR_NAME
    assert manifest[SUPPORTED_PLATFORMS_KEY] == [LINUX_PLATFORM_NAME]
    assert set(manifest[PACKS_KEY]) == {LINUX_PLATFORM_NAME}
    assert set(manifest[OUTPUT_CONTRACT_KEY][REQUIRED_QUERIES_KEY]) == (
        EXPECTED_QUERY_NAMES
    )
    assert manifest[DOCUMENTATION_KEY]
    validate_detectors.validate_manifest(MANIFEST_PATH, set())


def test_manifest_validation_rejects_inconsistent_platform_declarations(
    tmp_path: Path,
) -> None:
    """Reject empty, unsupported, and pack-mismatched platform declarations.

    Args:
        tmp_path: Isolated pytest directory used for invalid manifest variants.
    """

    invalid_platform_configurations = (
        ([], {}),
        (
            [UNSUPPORTED_PLATFORM_NAME],
            {UNSUPPORTED_PLATFORM_NAME: UNSUPPORTED_PACK_PATH},
        ),
        ([LINUX_PLATFORM_NAME], {}),
    )
    for supported_platforms, packs in invalid_platform_configurations:
        manifest = load_json_object(MANIFEST_PATH)
        manifest[SUPPORTED_PLATFORMS_KEY] = supported_platforms
        manifest[PACKS_KEY] = packs
        temporary_manifest_path = tmp_path / TEMPORARY_MANIFEST_FILE_NAME
        temporary_manifest_path.write_text(
            json.dumps(manifest),
            encoding="utf-8",
        )
        with pytest.raises(AssertionError):
            validate_detectors.validate_manifest(temporary_manifest_path, set())


def test_linux_pack_covers_network_and_logging_capabilities() -> None:
    """Require complete visible networking plus kernel-log and syslog checks."""

    pack = load_json_object(LINUX_PACK_PATH)
    assert pack[PLATFORM_KEY] == LINUX_PLATFORM_NAME
    assert set(pack[QUERIES_KEY]) == EXPECTED_QUERY_NAMES

    query_text = " ".join(
        specification[QUERY_KEY]
        for specification in pack[QUERIES_KEY].values()
    )
    for table_name in NETWORK_TABLE_NAMES:
        assert table_name in query_text
    for source_path in KERNEL_LOG_SOURCE_PATHS:
        assert source_path in query_text
    for provider_name in SYSLOG_PROVIDER_NAMES:
        assert provider_name in query_text

    kernel_access_query = pack[QUERIES_KEY][KERNEL_LOG_ACCESS_QUERY_NAME][QUERY_KEY]
    assert "access_available" in kernel_access_query
    assert "direct_device_probe_required" in kernel_access_query
    assert "posix_mode_estimate" in kernel_access_query
    syslog_query = pack[QUERIES_KEY][SYSLOG_AVAILABILITY_QUERY_NAME][QUERY_KEY]
    assert "available" in syslog_query
