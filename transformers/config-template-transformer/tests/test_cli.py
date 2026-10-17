# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Unit tests for command-line rendering and include injection."""

from __future__ import annotations

import argparse
import runpy
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from config_template_transformer.cli import build_parser, configure_logging, main, run
from config_template_transformer.constants import (
    ARTIFACTS_KEY,
    CAPABILITIES_KEY,
    COMMAND_RENDER,
    INCLUDES_KEY,
    INPUTS_KEY,
    METADATA_API_VERSION_KEY,
    METADATA_PATH_KEY,
    PATH_KEY,
    PIPELINE_KEY,
    PLUGIN_COUNT_KEY,
    SELECTION_RENDERED,
    SELECTION_STATUS_KEY,
    SUPPORTS_KEY,
    TARGET_KEY,
    TEMPLATE_KEY,
    TOOL_KEY,
    UTF8_ENCODING,
)
from config_template_transformer.errors import TransformerError
from conftest import (
    FIXTURE_DEFINITION_KEY,
    FIXTURE_DETECTOR_KEY,
    FIXTURE_MANIFEST_KEY,
    FIXTURE_OUTPUT_ROOT_KEY,
    FIXTURE_TEMPLATE_ROOT_KEY,
    read_json,
    write_text,
)


def test_cli_renders_manifest_and_injects_parent(component_paths: dict[str, Path]) -> None:
    """Render deduplicated inputs and inject their verified literal include."""

    render_status = main(
        [
            COMMAND_RENDER,
            "--detector-results",
            str(component_paths[FIXTURE_DETECTOR_KEY]),
            "--definition",
            str(component_paths[FIXTURE_DEFINITION_KEY]),
            "--template-root",
            str(component_paths[FIXTURE_TEMPLATE_ROOT_KEY]),
            "--output-root",
            str(component_paths[FIXTURE_OUTPUT_ROOT_KEY]),
            "--manifest-output",
            str(component_paths[FIXTURE_MANIFEST_KEY]),
            "--target-version",
            "4.2.0",
        ]
    )
    assert render_status == 0
    manifest = read_json(component_paths[FIXTURE_MANIFEST_KEY])
    artifact = manifest[ARTIFACTS_KEY][0]
    assert artifact[SELECTION_STATUS_KEY] == SELECTION_RENDERED
    assert artifact[PLUGIN_COUNT_KEY] == 2
    template = artifact[TEMPLATE_KEY]
    assert template[METADATA_PATH_KEY] == "fluent_bit_inputs.metadata.yaml"
    assert template[METADATA_API_VERSION_KEY] == "opamp.info/v1alpha1"
    assert template[TARGET_KEY][TOOL_KEY] == "fluent-bit"
    assert "file_tail_inputs" in template[SUPPORTS_KEY][CAPABILITIES_KEY]

    artifact_path = component_paths[FIXTURE_OUTPUT_ROOT_KEY] / artifact[PATH_KEY]
    fragment = YAML(typ="safe").load(artifact_path.read_text(encoding=UTF8_ENCODING))
    assert len(fragment[PIPELINE_KEY][INPUTS_KEY]) == 2

    parent_path = write_text(
        component_paths[FIXTURE_OUTPUT_ROOT_KEY] / "parent.yaml",
        "service:\n  log_level: debug\nincludes:\n  - existing.yaml\n",
    )
    assembled_path = component_paths[FIXTURE_OUTPUT_ROOT_KEY] / "fluent-bit.yaml"
    inject_status = main(
        [
            "inject",
            "--manifest",
            str(component_paths[FIXTURE_MANIFEST_KEY]),
            "--artifact-root",
            str(component_paths[FIXTURE_OUTPUT_ROOT_KEY]),
            "--parent-config",
            str(parent_path),
            "--output",
            str(assembled_path),
        ]
    )
    assert inject_status == 0
    assembled = YAML(typ="safe").load(assembled_path.read_text(encoding=UTF8_ENCODING))
    assert assembled[INCLUDES_KEY] == ["existing.yaml", artifact[PATH_KEY]]


def test_cli_returns_error_without_traceback(component_paths: dict[str, Path]) -> None:
    """Translate expected transformation failures into status one."""

    status = main(
        [
            COMMAND_RENDER,
            "--detector-results",
            str(component_paths[FIXTURE_DETECTOR_KEY]),
            "--definition",
            str(component_paths[FIXTURE_DEFINITION_KEY]),
            "--output-root",
            str(component_paths[FIXTURE_OUTPUT_ROOT_KEY]),
            "--manifest-output",
            str(component_paths[FIXTURE_MANIFEST_KEY]),
            "--target-version",
            "invalid-version",
        ]
    )
    assert status == 1


def test_cli_parser_version_and_unknown_dispatch(capsys: pytest.CaptureFixture[str]) -> None:
    """Expose the package version and reject an impossible parsed command."""

    with pytest.raises(SystemExit) as exit_error:
        build_parser().parse_args(["--version"])
    assert exit_error.value.code == 0
    assert "0.2.0" in capsys.readouterr().out

    with pytest.raises(TransformerError, match="Unsupported command"):
        run(argparse.Namespace(command="unknown"))
    configure_logging()


def test_python_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    """Delegate module execution to the CLI main function."""

    monkeypatch.setattr("config_template_transformer.cli.main", lambda: 7)
    with pytest.raises(SystemExit) as exit_error:
        runpy.run_module("config_template_transformer.__main__", run_name="__main__")
    assert exit_error.value.code == 7
