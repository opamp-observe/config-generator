# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Shared fixtures and builders for transformer unit tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from config_template_transformer.constants import UTF8_ENCODING

DETECTOR_RESULTS_TEXT = """{
  "detectors": [{
    "detector_name": "nginx_1",
    "detector_version": "1.0.0",
    "detected": true,
    "queries": {"log_locations": [
      {"path_or_destination": "/var/log/nginx/access.log"},
      {"path_or_destination": "/var/log/nginx/access.log"},
      {"path_or_destination": "  /var/log/nginx/error.log  "},
      {"path_or_destination": ""},
      {"unrelated": true}
    ]},
    "errors": []
  }]
}
"""

TRANSFORM_TEXT = """# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0.
api_version: opamp.info/v1alpha2
kind: ObservabilityFragmentTransform
metadata:
  name: nginx_1_logs
  version: 1.0.0
spec:
  detector:
    name: nginx_1
    version_constraint: ">=1,<2"
  target:
    tool: fluent-bit
    version_constraint: ">=3.2,<5"
  output:
    path: generated/nginx.inputs.yaml
    include_path: generated/nginx.inputs.yaml
  render:
    engine: jinja2
    template: fluent_bit_inputs.yaml.j2
    metadata_file: fluent_bit_inputs.metadata.yaml
    version: 1.0.0
    template_api_version: "1.0"
    context_name: plugins
  rules:
    - name: logs
      for_each: $.queries.log_locations[*]
      path_from: $.path_or_destination
      values:
        name: tail
        tag: nginx
"""

FIXTURE_DETECTOR_KEY = "detector"
FIXTURE_DEFINITION_KEY = "definition"
FIXTURE_MANIFEST_KEY = "manifest"
FIXTURE_OUTPUT_ROOT_KEY = "output_root"
FIXTURE_TEMPLATE_ROOT_KEY = "template_root"


def write_text(file_path: Path, content: str) -> Path:
    """Write UTF-8 fixture content and return its path.

    Args:
        file_path: Destination beneath a pytest temporary directory.
        content: Exact fixture text to persist.

    Returns:
        The input path for fluent fixture composition.
    """

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding=UTF8_ENCODING)
    return file_path


def read_json(file_path: Path) -> dict[str, Any]:
    """Read one generated JSON object for test assertions.

    Args:
        file_path: Generated JSON path.

    Returns:
        Parsed JSON mapping.
    """

    loaded_value = json.loads(file_path.read_text(encoding=UTF8_ENCODING))
    assert isinstance(loaded_value, dict)
    return loaded_value


@pytest.fixture(name="component_paths")
def fixture_component_paths(tmp_path: Path) -> dict[str, Path]:
    """Create common detector, transform, template, and output paths.

    Args:
        tmp_path: Pytest-managed isolated directory.

    Returns:
        Named paths used by rendering tests.
    """

    package_root = Path(__file__).parents[1] / "src" / "config_template_transformer"
    detector_path = write_text(tmp_path / "detectors.json", DETECTOR_RESULTS_TEXT)
    definition_path = write_text(tmp_path / "transform.yaml", TRANSFORM_TEXT)
    return {
        FIXTURE_DETECTOR_KEY: detector_path,
        FIXTURE_DEFINITION_KEY: definition_path,
        FIXTURE_TEMPLATE_ROOT_KEY: package_root / "templates",
        FIXTURE_OUTPUT_ROOT_KEY: tmp_path / "output",
        FIXTURE_MANIFEST_KEY: tmp_path / "output" / "orchestration.json",
    }
