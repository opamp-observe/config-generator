# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Opt-in end-to-end test for the NGINX and PostgreSQL regression image."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

CONTAINER_TEST_ENVIRONMENT = "RUN_CONTAINER_REGRESSION"
CONTAINER_TEST_ENABLED_VALUE = "1"
DOCKER_COMMAND = "docker"
IMAGE_NAME = "opamp-nginx-postgresql-regression:test"
PROCESS_INSPECTION_CAPABILITY = "SYS_PTRACE"
PROCESS_INSPECTION_SECURITY_OPTION = "seccomp=unconfined"
BUILD_TIMEOUT_SECONDS = 900
RUN_TIMEOUT_SECONDS = 180
VERIFICATION_FILE_NAME = "regression-verification.json"
STATUS_KEY = "status"
PASSED_STATUS = "passed"
UTF8_ENCODING = "utf-8"


@unittest.skipUnless(
    os.environ.get(CONTAINER_TEST_ENVIRONMENT) == CONTAINER_TEST_ENABLED_VALUE,
    f"set {CONTAINER_TEST_ENVIRONMENT}=1 to run the container regression",
)
class RegressionContainerTests(unittest.TestCase):
    """Build and run the container, then inspect its exported success report."""

    def test_container_generates_and_validates_artifacts(self) -> None:
        """Require the complete detector-to-transformer flow to succeed."""

        if shutil.which(DOCKER_COMMAND) is None:
            self.skipTest("Docker is unavailable")
        repository_root = Path(__file__).resolve().parents[1]
        build_root = repository_root / "build" / "regression-tests"
        build_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="container-", dir=build_root) as output_name:
            output_root = Path(output_name)
            build_process = subprocess.run(
                [
                    DOCKER_COMMAND,
                    "build",
                    "--file",
                    str(repository_root / "tests" / "regression" / "Dockerfile"),
                    "--tag",
                    IMAGE_NAME,
                    str(repository_root),
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=BUILD_TIMEOUT_SECONDS,
            )
            self.assertEqual(
                0,
                build_process.returncode,
                build_process.stdout + build_process.stderr,
            )
            run_process = subprocess.run(
                [
                    DOCKER_COMMAND,
                    "run",
                    "--rm",
                    "--cap-add",
                    PROCESS_INSPECTION_CAPABILITY,
                    "--security-opt",
                    PROCESS_INSPECTION_SECURITY_OPTION,
                    "--volume",
                    f"{output_root.resolve()}:/artifacts",
                    IMAGE_NAME,
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=RUN_TIMEOUT_SECONDS,
            )
            self.assertEqual(
                0,
                run_process.returncode,
                run_process.stdout + run_process.stderr,
            )
            verification = json.loads(
                (output_root / VERIFICATION_FILE_NAME).read_text(encoding=UTF8_ENCODING)
            )
            self.assertEqual(PASSED_STATUS, verification[STATUS_KEY])


if __name__ == "__main__":
    unittest.main()
