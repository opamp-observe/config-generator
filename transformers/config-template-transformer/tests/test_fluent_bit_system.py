# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Optional system validation against the real Fluent Bit configuration parser."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from config_template_transformer.orchestrator import (
    TransformationOrchestrator,
    inject_manifest_includes,
)
from conftest import (
    FIXTURE_DEFINITION_KEY,
    FIXTURE_DETECTOR_KEY,
    FIXTURE_MANIFEST_KEY,
    FIXTURE_TEMPLATE_ROOT_KEY,
    write_text,
)

DOCKER_COMMAND = "docker"
FLUENT_BIT_IMAGE = "fluent/fluent-bit:4.2"
FLUENT_BIT_BINARY = "/fluent-bit/bin/fluent-bit"
CONTAINER_CONFIG_ROOT = "/fluent-bit/etc/generated-config"
DOCKER_SUCCESS = 0
SUBPROCESS_TIMEOUT_SECONDS = 20
PARENT_CONFIG_TEXT = """service:
  log_level: debug
pipeline:
  outputs:
    - name: stdout
      match: '*'
"""
SYSTEM_BUILD_DIRECTORY = "system-tests"


@pytest.mark.system
def test_generated_parent_passes_fluent_bit_dry_run(
    component_paths: dict[str, Path],
) -> None:
    """Render, assemble, and validate the example with Fluent Bit 4.2.

    Args:
        component_paths: Isolated fixture paths for one end-to-end transformation.
    """

    if shutil.which(DOCKER_COMMAND) is None:
        pytest.skip("Docker is unavailable")
    image_check = subprocess.run(
        [DOCKER_COMMAND, "image", "inspect", FLUENT_BIT_IMAGE],
        check=False,
        capture_output=True,
        text=True,
        timeout=SUBPROCESS_TIMEOUT_SECONDS,
    )
    if image_check.returncode != DOCKER_SUCCESS:
        pytest.skip(f"Docker image {FLUENT_BIT_IMAGE} is unavailable")

    build_root = Path(__file__).parents[1] / "build" / SYSTEM_BUILD_DIRECTORY
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="fluent-bit-", dir=build_root) as temporary_name:
        output_root = Path(temporary_name)
        manifest_path = output_root / component_paths[FIXTURE_MANIFEST_KEY].name
        orchestrator = TransformationOrchestrator(component_paths[FIXTURE_TEMPLATE_ROOT_KEY])
        orchestrator.render(
            detector_results_path=component_paths[FIXTURE_DETECTOR_KEY],
            definition_paths=[component_paths[FIXTURE_DEFINITION_KEY]],
            output_root=output_root,
            manifest_output=manifest_path,
            target_version="4.2.0",
        )
        parent_path = write_text(output_root / "parent.yaml", PARENT_CONFIG_TEXT)
        assembled_path = output_root / "fluent-bit.yaml"
        inject_manifest_includes(
            manifest_path,
            parent_path,
            assembled_path,
            output_root,
        )

        mount_argument = f"{output_root.resolve()}:{CONTAINER_CONFIG_ROOT}:ro"
        validation = subprocess.run(
            [
                DOCKER_COMMAND,
                "run",
                "--rm",
                "--volume",
                mount_argument,
                FLUENT_BIT_IMAGE,
                FLUENT_BIT_BINARY,
                "--config",
                f"{CONTAINER_CONFIG_ROOT}/{assembled_path.name}",
                "--dry-run",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_SECONDS,
        )
        assert validation.returncode == DOCKER_SUCCESS, validation.stdout + validation.stderr
