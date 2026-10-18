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

"""Unit tests for detector and aggregate JSON Schema synchronization."""

from __future__ import annotations

import unittest

import validate_detectors


class DetectorSchemaTests(unittest.TestCase):
    """Verify that result schemas remain aligned with manifests and packs."""

    def test_detector_and_master_schemas_match_repository_metadata(self) -> None:
        """Every manifest, pack query, and master reference should agree."""

        manifest_paths = sorted(
            validate_detectors.DETECTORS_ROOT.glob("*/*/detector.json")
        )
        seen_detector_names: set[str] = set()
        detector_schema_references: set[str] = set()

        for manifest_path in manifest_paths:
            manifest = validate_detectors.validate_manifest(
                manifest_path,
                seen_detector_names,
            )
            platform_query_names = {
                platform_name: set(
                    validate_detectors.load_object(
                        manifest_path.parent / relative_pack_path
                    )["queries"]
                )
                for platform_name, relative_pack_path in manifest["packs"].items()
            }
            unique_query_sets = {
                frozenset(query_names)
                for query_names in platform_query_names.values()
            }
            self.assertEqual(1, len(unique_query_sets))
            common_query_names = set(next(iter(unique_query_sets)))
            detector_schema_references.add(
                validate_detectors.validate_detector_schema(
                    manifest_path,
                    manifest,
                    common_query_names,
                )
            )

        validate_detectors.validate_master_schema(detector_schema_references)
        self.assertEqual(len(manifest_paths), len(detector_schema_references))


if __name__ == "__main__":
    unittest.main()
