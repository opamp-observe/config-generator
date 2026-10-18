# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Target adapter contract and initial Fluent Bit implementation."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Any, Protocol

from ruamel.yaml import YAML, YAMLError

from config_template_transformer.constants import (
    FLUENT_BIT_CONFIGURATION_FORMAT,
    FLUENT_BIT_INCLUDE_STRATEGY,
    FLUENT_BIT_TOOL_NAME,
    INCLUDES_KEY,
    INPUTS_KEY,
    MEDIA_TYPE_FLUENT_BIT_YAML,
    MEDIA_TYPE_OTELCOL_YAML,
    NAME_KEY,
    OTELCOL_CONTRIB_CONFIGURATION_FORMAT,
    OTELCOL_CONTRIB_INCLUDE_STRATEGY,
    OTELCOL_CONTRIB_TOOL_NAME,
    PIPELINE_KEY,
    PIPELINES_KEY,
    RECEIVERS_KEY,
    SERVICE_KEY,
    UTF8_ENCODING,
)
from config_template_transformer.errors import TransformerError
from config_template_transformer.files import write_bytes_atomically
from config_template_transformer.models import TransformDefinition


class TargetAdapter(Protocol):
    """Define target-specific validation, serialization, and include injection.

    Attributes:
        tool_name: Stable name used in transform definitions and manifests.
        configuration_format: Syntax name produced by the adapter.
        include_strategy: Manifest strategy consumed during parent injection.
        media_type: Media type assigned to generated artifacts.
    """

    tool_name: str
    configuration_format: str
    include_strategy: str
    media_type: str

    def serialize_fragment(
        self,
        fragment: dict[str, Any],
        definition: TransformDefinition,
    ) -> bytes:
        """Validate and serialize a rendered fragment for the target tool."""

    def inject_includes(
        self,
        parent_path: Path,
        include_paths: list[str],
        output_path: Path,
    ) -> None:
        """Inject literal include paths into a target parent configuration."""


class FluentBitAdapter:
    """Produce Fluent Bit YAML fragments and top-level include lists.

    Attributes:
        tool_name: Manifest and definition name for Fluent Bit.
        configuration_format: YAML syntax emitted by this adapter.
        include_strategy: Top-level YAML includes merge strategy.
        media_type: Fluent Bit YAML artifact media type.
    """

    tool_name = FLUENT_BIT_TOOL_NAME
    configuration_format = FLUENT_BIT_CONFIGURATION_FORMAT
    include_strategy = FLUENT_BIT_INCLUDE_STRATEGY
    media_type = MEDIA_TYPE_FLUENT_BIT_YAML

    def serialize_fragment(
        self,
        fragment: dict[str, Any],
        definition: TransformDefinition,
    ) -> bytes:
        """Validate a Fluent Bit input fragment and serialize deterministic YAML.

        Args:
            fragment: Parsed Jinja output expected to contain `pipeline.inputs`.
            definition: Versioned transform used for the provenance banner.

        Returns:
            UTF-8 YAML bytes with transform and template version comments.

        Raises:
            TransformerError: The fragment does not contain valid plugin objects.
        """

        self._validate_fragment(fragment)
        yaml_writer = YAML(typ="safe")
        yaml_writer.default_flow_style = False
        yaml_writer.sort_base_mapping_type_on_output = False
        output_stream = StringIO()
        yaml_writer.dump(fragment, output_stream)
        provenance = (
            f"# generated_by=opamp-config-template-transformer "
            f"transform={definition.name}@{definition.version} "
            f"template={definition.template_name}@{definition.template_version} "
            f"template_api={definition.template_api_version}\n"
        )
        return (provenance + output_stream.getvalue()).encode(UTF8_ENCODING)

    def inject_includes(
        self,
        parent_path: Path,
        include_paths: list[str],
        output_path: Path,
    ) -> None:
        """Merge manifest include paths into a Fluent Bit YAML parent.

        Args:
            parent_path: Existing Fluent Bit YAML parent configuration.
            include_paths: Literal include paths in deterministic manifest order.
            output_path: Destination for the updated parent; it may equal the source.

        Raises:
            TransformerError: Parent YAML or its `includes` section is invalid.
        """

        yaml_editor = YAML()
        yaml_editor.preserve_quotes = True
        try:
            parent = yaml_editor.load(parent_path.read_text(encoding=UTF8_ENCODING))
        except (OSError, YAMLError) as error:
            raise TransformerError(
                f"Unable to load Fluent Bit parent {parent_path}: {error}"
            ) from error
        if not isinstance(parent, dict):
            raise TransformerError(f"Fluent Bit parent must be a mapping: {parent_path}")
        existing_includes = parent.get(INCLUDES_KEY, [])
        if not isinstance(existing_includes, list) or not all(
            isinstance(include_path, str) for include_path in existing_includes
        ):
            raise TransformerError("Fluent Bit parent includes must be a list of strings")
        merged_includes = list(existing_includes)
        for include_path in include_paths:
            if include_path not in merged_includes:
                merged_includes.append(include_path)
        parent[INCLUDES_KEY] = merged_includes
        output_stream = StringIO()
        yaml_editor.dump(parent, output_stream)
        write_bytes_atomically(output_path, output_stream.getvalue().encode(UTF8_ENCODING))

    @staticmethod
    def _validate_fragment(fragment: dict[str, Any]) -> None:
        """Require the Fluent Bit `pipeline.inputs` structure and plugin names.

        Args:
            fragment: Parsed Jinja output to validate.

        Raises:
            TransformerError: Required pipeline structure or plugin names are absent.
        """

        pipeline = fragment.get(PIPELINE_KEY)
        if not isinstance(pipeline, dict):
            raise TransformerError("Fluent Bit fragment must contain a pipeline mapping")
        inputs = pipeline.get(INPUTS_KEY)
        if not isinstance(inputs, list):
            raise TransformerError("Fluent Bit fragment pipeline.inputs must be a list")
        if not all(isinstance(plugin, dict) and plugin.get(NAME_KEY) for plugin in inputs):
            raise TransformerError("Every Fluent Bit input must be a mapping with a name")


class OpenTelemetryCollectorContribAdapter:
    """Produce OpenTelemetry Collector Contrib YAML configuration fragments.

    Attributes:
        tool_name: Manifest and mapping name for the Contrib distribution.
        configuration_format: YAML syntax emitted by this adapter.
        include_strategy: Multiple configuration files supplied by repeated CLI flags.
        media_type: OpenTelemetry Collector YAML artifact media type.
    """

    tool_name = OTELCOL_CONTRIB_TOOL_NAME
    configuration_format = OTELCOL_CONTRIB_CONFIGURATION_FORMAT
    include_strategy = OTELCOL_CONTRIB_INCLUDE_STRATEGY
    media_type = MEDIA_TYPE_OTELCOL_YAML

    def serialize_fragment(
        self,
        fragment: dict[str, Any],
        definition: TransformDefinition,
    ) -> bytes:
        """Validate and serialize an OpenTelemetry Collector configuration.

        Args:
            fragment: Parsed Jinja output containing receivers and service pipelines.
            definition: Versioned mapping used for the provenance banner.

        Returns:
            UTF-8 YAML bytes with transform and template version comments.

        Raises:
            TransformerError: The receiver or service pipeline structure is invalid.
        """

        self._validate_fragment(fragment)
        yaml_writer = YAML(typ="safe")
        yaml_writer.default_flow_style = False
        yaml_writer.sort_base_mapping_type_on_output = False
        output_stream = StringIO()
        yaml_writer.dump(fragment, output_stream)
        provenance = (
            f"# generated_by=opamp-config-template-transformer "
            f"transform={definition.name}@{definition.version} "
            f"template={definition.template_name}@{definition.template_version} "
            f"template_api={definition.template_api_version}\n"
        )
        return (provenance + output_stream.getvalue()).encode(UTF8_ENCODING)

    def inject_includes(
        self,
        parent_path: Path,
        include_paths: list[str],
        output_path: Path,
    ) -> None:
        """Explain how Collector fragments must be supplied to the executable.

        Args:
            parent_path: Unused parent configuration path from the generic interface.
            include_paths: Generated configuration files intended for CLI arguments.
            output_path: Unused output path from the generic interface.

        Raises:
            TransformerError: Collector configuration composition is a CLI operation.
        """

        del parent_path, include_paths, output_path
        raise TransformerError(
            "OpenTelemetry Collector fragments use repeated --config arguments; "
            "automatic parent-file injection is not supported"
        )

    @staticmethod
    def _validate_fragment(fragment: dict[str, Any]) -> None:
        """Require receiver definitions and service pipeline configuration.

        Args:
            fragment: Parsed Jinja output to validate.

        Raises:
            TransformerError: Required Collector mappings are absent.
        """

        receivers = fragment.get(RECEIVERS_KEY)
        service = fragment.get(SERVICE_KEY)
        if not isinstance(receivers, dict) or not all(
            isinstance(receiver_name, str) and isinstance(receiver_config, dict)
            for receiver_name, receiver_config in receivers.items()
        ):
            raise TransformerError("OpenTelemetry Collector receivers must be a mapping")
        if not isinstance(service, dict) or not isinstance(service.get(PIPELINES_KEY), dict):
            raise TransformerError(
                "OpenTelemetry Collector service.pipelines must be a mapping"
            )


def get_target_adapter(tool_name: str) -> TargetAdapter:
    """Return the adapter registered for a target tool.

    Args:
        tool_name: Stable tool name from a transform or manifest.

    Returns:
        Adapter implementing the target configuration contract.

    Raises:
        TransformerError: No adapter has been implemented for the requested tool.
    """

    if tool_name == FLUENT_BIT_TOOL_NAME:
        return FluentBitAdapter()
    if tool_name == OTELCOL_CONTRIB_TOOL_NAME:
        return OpenTelemetryCollectorContribAdapter()
    raise TransformerError(
        f"Unsupported target tool '{tool_name}'; add a TargetAdapter implementation"
    )
