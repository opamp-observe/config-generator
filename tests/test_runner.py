# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for detector aggregation behavior."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import runner

EXPECTED_DETECTOR_COUNT = 16
HOST_INVENTORY_DIRECTORY_NAME = "host_inventory"
LINUX_SYSTEM_DIRECTORY_NAME = "linux_system"


class DetectorRunnerTests(unittest.TestCase):
    """Verify manifest selection, discovery, and osquery result parsing."""

    def test_find_detector_manifests_returns_all_detectors(self) -> None:
        """The checked-in suite should expose product and host detectors."""

        manifests = runner.find_detector_manifests(
            Path(__file__).resolve().parents[1] / "detectors"
        )
        self.assertEqual(EXPECTED_DETECTOR_COUNT, len(manifests))
        self.assertTrue(
            any(
                path.parent.parent.name == HOST_INVENTORY_DIRECTORY_NAME
                for path in manifests
            )
        )
        self.assertTrue(
            any(
                path.parent.parent.name == LINUX_SYSTEM_DIRECTORY_NAME
                for path in manifests
            )
        )

    def test_run_osquery_query_parses_json_rows(self) -> None:
        """The osquery adapter should return decoded row objects."""

        completed_process = mock.Mock(returncode=0, stdout='[{"pid":"42"}]', stderr="")
        with mock.patch("runner.subprocess.run", return_value=completed_process):
            rows = runner.run_osquery_query("osqueryi", "SELECT 1;", 30)
        self.assertEqual([{"pid": "42"}], rows)

    def test_resolve_osquery_preserves_explicit_launcher_path(self) -> None:
        """An explicit osqueryi symlink name must not resolve to osqueryd."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            executable_path = Path(temporary_directory) / "osqueryi"
            executable_path.write_text("", encoding="utf-8")
            resolved_path = runner.resolve_osquery_executable(str(executable_path))
        self.assertTrue(resolved_path.endswith("osqueryi"))

    def test_run_discovery_requires_every_query_to_match(self) -> None:
        """A detector should remain false when any discovery query has no rows."""

        with mock.patch(
            "runner.run_osquery_query",
            side_effect=[[{"matched": "1"}], []],
        ):
            detected, evidence, errors = runner.run_discovery_queries(
                "osqueryi",
                ["SELECT 1;", "SELECT 2;"],
                30,
            )
        self.assertFalse(detected)
        self.assertEqual(2, len(evidence))
        self.assertEqual([], errors)

    def test_select_manifest_paths_rejects_unknown_name(self) -> None:
        """An explicit unknown detector should produce a useful error."""

        with tempfile.TemporaryDirectory() as temporary_directory:
            manifest_path = Path(temporary_directory) / "detector.json"
            manifest_path.write_text(
                json.dumps({"detector": {"name": "known"}}),
                encoding="utf-8",
            )
            with self.assertRaises(runner.DetectorRunnerError):
                runner.select_manifest_paths([manifest_path], {"missing"})


if __name__ == "__main__":
    unittest.main()
