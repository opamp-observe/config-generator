# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Command-line interface for rendering and injecting configuration fragments."""

from __future__ import annotations

import argparse
import logging
from collections.abc import Sequence
from pathlib import Path

from config_template_transformer import APPLICATION_NAME, APPLICATION_VERSION
from config_template_transformer.constants import (
    COMMAND_INJECT,
    COMMAND_RENDER,
    DEFAULT_LOG_FORMAT,
    EXIT_SUCCESS,
    EXIT_TRANSFORM_ERROR,
)
from config_template_transformer.errors import TransformerError
from config_template_transformer.orchestrator import (
    TransformationOrchestrator,
    inject_manifest_includes,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_TEMPLATE_ROOT = Path(__file__).parent / "templates"


def build_parser() -> argparse.ArgumentParser:
    """Build the complete command-line parser.

    Returns:
        Parser containing the render and inject workflows.
    """

    parser = argparse.ArgumentParser(
        prog="obs-config-transformer",
        description="Render versioned observability configuration fragments.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APPLICATION_NAME} {APPLICATION_VERSION}",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    render_parser = subparsers.add_parser(
        COMMAND_RENDER,
        help="Render fragments and write an orchestration JSON manifest.",
    )
    render_parser.add_argument("--detector-results", type=Path, required=True)
    render_parser.add_argument(
        "--definition",
        type=Path,
        action="append",
        required=True,
        help="Versioned YAML transform definition; repeat for multiple fragments.",
    )
    render_parser.add_argument(
        "--template-root",
        type=Path,
        default=DEFAULT_TEMPLATE_ROOT,
        help="Approved Jinja template directory.",
    )
    render_parser.add_argument("--output-root", type=Path, required=True)
    render_parser.add_argument("--manifest-output", type=Path, required=True)
    render_parser.add_argument("--target-version", required=True)
    render_parser.add_argument(
        "--detector-schema",
        type=Path,
        help="Optional aggregate detector-results JSON Schema.",
    )

    inject_parser = subparsers.add_parser(
        COMMAND_INJECT,
        help="Verify a manifest and inject its includes into a parent configuration.",
    )
    inject_parser.add_argument("--manifest", type=Path, required=True)
    inject_parser.add_argument("--parent-config", type=Path, required=True)
    inject_parser.add_argument("--output", type=Path, required=True)
    inject_parser.add_argument(
        "--artifact-root",
        type=Path,
        help="Artifact root; defaults to the manifest directory.",
    )
    return parser


def configure_logging() -> None:
    """Configure DEBUG logging as the component-wide operational default."""

    logging.basicConfig(level=logging.DEBUG, format=DEFAULT_LOG_FORMAT)


def run(arguments: argparse.Namespace) -> None:
    """Execute one already-parsed CLI command.

    Args:
        arguments: Namespace produced by :func:`build_parser`.

    Raises:
        TransformerError: The command name is unsupported or transformation fails.
    """

    if arguments.command == COMMAND_RENDER:
        orchestrator = TransformationOrchestrator(arguments.template_root)
        orchestrator.render(
            detector_results_path=arguments.detector_results,
            definition_paths=arguments.definition,
            output_root=arguments.output_root,
            manifest_output=arguments.manifest_output,
            target_version=arguments.target_version,
            detector_schema_path=arguments.detector_schema,
        )
        return
    if arguments.command == COMMAND_INJECT:
        inject_manifest_includes(
            manifest_path=arguments.manifest,
            parent_path=arguments.parent_config,
            output_path=arguments.output,
            artifact_root=arguments.artifact_root,
        )
        return
    raise TransformerError(f"Unsupported command: {arguments.command}")


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with concise expected errors and a process status.

    Args:
        argv: Optional arguments excluding the executable name.

    Returns:
        Zero on success and one for an expected transformation failure.
    """

    configure_logging()
    arguments = build_parser().parse_args(argv)
    try:
        run(arguments)
    except TransformerError as error:
        LOGGER.error("%s", error)
        return EXIT_TRANSFORM_ERROR
    LOGGER.debug("Command %s completed successfully", arguments.command)
    return EXIT_SUCCESS
