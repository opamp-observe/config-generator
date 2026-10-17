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

"""Unit tests for Oracle Automatic Storage Management osquery coverage."""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ORACLE_DETECTORS_ROOT = REPOSITORY_ROOT / "detectors" / "oracle_database"
ORACLE_DATABASE_VERSIONS = ("19", "21", "26")
SUPPORTED_PLATFORMS = ("linux", "windows")
QUERIES_KEY = "queries"
QUERY_KEY = "query"
ASM_QUERY_NAME = "asm_instances"
DEPLOYMENT_FEATURES_QUERY_NAME = "deployment_features"
RAC_RESULT_ALIAS = "END AS rac_services_deployed"
ASM_RESULT_ALIAS = "END AS asm_deployed"
LINUX_ASM_PROCESS_PATTERN = "asm_pmon_+ASM%"
WINDOWS_ASM_SERVICE_PATTERN = "OracleASMService%"


class OracleAsmPackTests(unittest.TestCase):
    """Verify consistent ASM inventory and feature detection in Oracle packs."""

    def _load_pack(self, version: str, platform_name: str) -> dict[str, Any]:
        """Load one Oracle pack for the requested version and platform."""

        pack_path = (
            ORACLE_DETECTORS_ROOT / version / "packs" / f"{platform_name}.conf"
        )
        return json.loads(pack_path.read_text(encoding="utf-8"))

    def test_all_oracle_packs_expose_asm_inventory(self) -> None:
        """Every supported Oracle pack should expose platform-specific ASM rows."""

        for version in ORACLE_DATABASE_VERSIONS:
            for platform_name in SUPPORTED_PLATFORMS:
                with self.subTest(version=version, platform=platform_name):
                    pack = self._load_pack(version, platform_name)
                    asm_query = pack[QUERIES_KEY][ASM_QUERY_NAME][QUERY_KEY]
                    expected_pattern = (
                        LINUX_ASM_PROCESS_PATTERN
                        if platform_name == "linux"
                        else WINDOWS_ASM_SERVICE_PATTERN
                    )
                    self.assertIn(expected_pattern, asm_query)
                    self.assertIn("instance_name", asm_query)

    def test_asm_detection_is_independent_from_rac_detection(self) -> None:
        """Standalone ASM evidence should not be reported as proof of Oracle RAC."""

        for version in ORACLE_DATABASE_VERSIONS:
            for platform_name in SUPPORTED_PLATFORMS:
                with self.subTest(version=version, platform=platform_name):
                    pack = self._load_pack(version, platform_name)
                    feature_query = pack[QUERIES_KEY][
                        DEPLOYMENT_FEATURES_QUERY_NAME
                    ][QUERY_KEY]
                    rac_expression, remaining_expression = feature_query.split(
                        RAC_RESULT_ALIAS,
                        maxsplit=1,
                    )
                    self.assertNotIn(LINUX_ASM_PROCESS_PATTERN, rac_expression)
                    self.assertNotIn(WINDOWS_ASM_SERVICE_PATTERN, rac_expression)
                    self.assertIn(ASM_RESULT_ALIAS, remaining_expression)


if __name__ == "__main__":
    unittest.main()
