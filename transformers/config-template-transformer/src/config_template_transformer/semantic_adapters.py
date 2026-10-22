# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Common semantic generator interface and initial agent implementations."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML

from config_template_transformer.constants import (
    DETECTOR_LINK_KEY,
    FLUENT_BIT_TOOL_NAME,
    MEDIA_TYPE_FLUENT_BIT_YAML,
    MEDIA_TYPE_OTELCOL_YAML,
    OTELCOL_CONTRIB_TOOL_NAME,
    PLUGIN_ID_KEY,
    PROPERTIES_KEY,
    UTF8_ENCODING,
)
from config_template_transformer.errors import TransformerError
from config_template_transformer.semantic_models import (
    GeneratedSemanticArtifact,
    SemanticPlugin,
)

ATTRIBUTES_KEY = "attributes"
BODY_KEY = "body"
CALL_KEY = "call"
COLLECTION_INTERVAL_KEY = "collection_interval"
COLUMNS_KEY = "columns"
ENDPOINT_KEY = "endpoint"
EXPRESSION_KEY = "expression"
FIELD_KEY = "field"
FILTERS_KEY = "filters"
FORMAT_KEY = "format"
FROM_KEY = "from"
HEADER_KEY = "header"
IF_KEY = "if"
INCLUDE_KEY = "include"
INPUTS_KEY = "inputs"
KIND_KEY = "kind"
LOGS_KEY = "logs"
MATCH_KEY = "match"
NAME_KEY = "name"
OPERATORS_KEY = "operators"
PARSER_KEY = "parser"
PARSERS_KEY = "parsers"
PATH_KEY = "path"
PATH_SUFFIX_KEY = "path_suffix"
PIPELINE_KEY = "pipeline"
PIPELINES_KEY = "pipelines"
PROCESSORS_KEY = "processors"
RECEIVERS_KEY = "receivers"
REGEX_KEY = "regex"
RESOURCE_KEY = "resource"
SCRIPT_KEY = "script"
SEPARATOR_KEY = "separator"
SERVICE_KEY = "service"
SEVERITY_FIELD_KEY = "severity_field"
SEVERITY_KEY = "severity"
START_AT_KEY = "start_at"
TAG_KEY = "tag"
TIME_FIELD_KEY = "time_field"
TIME_FORMAT_KEY = "time_format"
TIME_KEEP_KEY = "time_keep"
TIME_KEY_KEY = "time_key"
TIMESTAMP_KEY = "timestamp"
TO_KEY = "to"
TYPE_KEY = "type"
TYPES_KEY = "types"
VALUE_KEY = "value"
PARSE_FROM_KEY = "parse_from"
LAYOUT_KEY = "layout"
LAYOUT_TYPE_KEY = "layout_type"
OPAMP_DETECTOR_LINK_ATTRIBUTE = "opamp.detector.link"
OPAMP_PLUGIN_ID_ATTRIBUTE = "opamp.plugin.id"
SEMCONV_VERSION_ATTRIBUTE = "otel.semconv.version"

SEMANTIC_CONFIG_BANNER = (
    "# generated_by=opamp-config-template-transformer stage=semantic-map\n"
)
FLUENT_BIT_CONFIG_PATH = Path("generated/fluent-bit/semantic-normalization.yaml")
FLUENT_BIT_LUA_PATH = Path("generated/fluent-bit/semantic-normalization.lua")
OTELCOL_CONFIG_PATH = Path("generated/otelcol-contrib/semantic-normalization.yaml")
FLUENT_BIT_LUA_RUNTIME_PATH = "/etc/fluent-bit/generated/semantic-normalization.lua"


class SemanticConfigurationAdapter(ABC):
    """Define the common interface implemented by every observability agent.

    Attributes:
        tool_name: Stable target name copied from the first-stage manifest.
    """

    tool_name: str

    @abstractmethod
    def generate(self, semantic_plugins: list[SemanticPlugin]) -> list[GeneratedSemanticArtifact]:
        """Generate target-specific configuration from neutral semantic mappings.

        Args:
            semantic_plugins: Verified plugins paired with selected mappings.

        Returns:
            One or more artifacts ready for atomic persistence.
        """


class FluentBitSemanticAdapter(SemanticConfigurationAdapter):
    """Generate Fluent Bit inputs, parsers, and Lua payload normalization.

    Attributes:
        tool_name: Stable target name for adapter lookup.
    """

    tool_name = FLUENT_BIT_TOOL_NAME

    def generate(self, semantic_plugins: list[SemanticPlugin]) -> list[GeneratedSemanticArtifact]:
        """Build a complete Fluent Bit collection and semantic-normalization fragment.

        Args:
            semantic_plugins: Log inputs paired with neutral parse and payload mappings.

        Returns:
            YAML configuration plus a Lua script that constructs OTLP-like records.
        """

        parsers, inputs, filters, lua_lines = self._build_components(semantic_plugins)
        configuration = {
            PARSERS_KEY: parsers,
            PIPELINE_KEY: {INPUTS_KEY: inputs, FILTERS_KEY: filters},
        }
        yaml_bytes = _serialize_yaml(configuration)
        lua_bytes = ("\n".join(lua_lines).rstrip() + "\n").encode(UTF8_ENCODING)
        return [
            GeneratedSemanticArtifact(
                path=FLUENT_BIT_CONFIG_PATH,
                media_type=MEDIA_TYPE_FLUENT_BIT_YAML,
                content=SEMANTIC_CONFIG_BANNER.encode(UTF8_ENCODING) + yaml_bytes,
            ),
            GeneratedSemanticArtifact(
                path=FLUENT_BIT_LUA_PATH,
                media_type="text/x-lua",
                content=lua_bytes,
            ),
        ]

    def _build_components(
        self,
        semantic_plugins: list[SemanticPlugin],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        """Build Fluent Bit parser, input, filter, and Lua component lists.

        Args:
            semantic_plugins: Verified plugins paired with neutral mappings.

        Returns:
            Ordered parsers, inputs, filters, and Lua source lines.
        """

        parsers: list[dict[str, Any]] = []
        inputs: list[dict[str, Any]] = []
        filters: list[dict[str, Any]] = []
        lua_lines = [
            "-- Copyright 2026 opamp.info",
            "-- Licensed under the Apache License, Version 2.0.",
            "-- Generated semantic payload normalization.",
            "",
        ]
        for semantic_plugin in semantic_plugins:
            plugin_id = semantic_plugin.plugin[PLUGIN_ID_KEY]
            safe_identifier = _safe_identifier(plugin_id)
            parser_name = f"opamp_{safe_identifier}"
            unique_tag = f"opamp.semantic.{safe_identifier}"
            properties = dict(semantic_plugin.plugin[PROPERTIES_KEY])
            path_value = str(properties.pop(PATH_KEY, ""))
            path_suffix = str(properties.pop(PATH_SUFFIX_KEY, ""))
            properties.pop(PROCESSORS_KEY, None)
            properties[PARSER_KEY] = parser_name
            properties[TAG_KEY] = unique_tag
            if path_value:
                properties[PATH_KEY] = f"{path_value}{path_suffix}"
            inputs.append(properties)
            parsers.append(self._build_parser(parser_name, semantic_plugin))
            function_name = f"map_{safe_identifier}"
            filters.append(
                {
                    NAME_KEY: "lua",
                    MATCH_KEY: unique_tag,
                    SCRIPT_KEY: FLUENT_BIT_LUA_RUNTIME_PATH,
                    CALL_KEY: function_name,
                }
            )
            lua_lines.extend(self._build_lua_function(function_name, semantic_plugin))
        return parsers, inputs, filters, lua_lines

    @staticmethod
    def _build_parser(parser_name: str, semantic_plugin: SemanticPlugin) -> dict[str, Any]:
        """Translate a neutral parser definition to Fluent Bit parser YAML.

        Args:
            parser_name: Unique parser identity for one generated input.
            semantic_plugin: Selected mapping containing parse details.

        Returns:
            Fluent Bit parser mapping.
        """

        parse = semantic_plugin.mapping.parse
        parser: dict[str, Any] = {NAME_KEY: parser_name, FORMAT_KEY: parse[TYPE_KEY]}
        if parse[TYPE_KEY] == "regex":
            parser[REGEX_KEY] = parse[EXPRESSION_KEY].replace("(?P<", "(?<")
        else:
            parser[COLUMNS_KEY] = ",".join(parse[COLUMNS_KEY])
            parser[SEPARATOR_KEY] = ","
        if TIME_FIELD_KEY in parse:
            parser[TIME_KEY_KEY] = parse[TIME_FIELD_KEY]
            parser[TIME_FORMAT_KEY] = parse[TIME_FORMAT_KEY]
            parser[TIME_KEEP_KEY] = True
        if TYPES_KEY in parse:
            parser[TYPES_KEY] = " ".join(
                f"{field_name}:{field_type}"
                for field_name, field_type in sorted(parse[TYPES_KEY].items())
            )
        return parser

    @staticmethod
    def _build_lua_function(
        function_name: str,
        semantic_plugin: SemanticPlugin,
    ) -> list[str]:
        """Build one Lua function that creates a structured semantic log record.

        Args:
            function_name: Safe function name referenced by the Lua filter.
            semantic_plugin: Provenance and semantic mapping for one input.

        Returns:
            Lua source lines for one filter callback.
        """

        mapping = semantic_plugin.mapping
        plugin = semantic_plugin.plugin
        lines = [
            f"function {function_name}(tag, timestamp, record)",
            "    local attributes = {}",
            "    local resource = {}",
        ]
        for source_field, target_field in sorted(mapping.field_mappings.items()):
            lines.extend(
                [
                    f"    if record[{_lua_string(source_field)}] ~= nil then",
                    f"        attributes[{_lua_string(target_field)}] = "
                    f"record[{_lua_string(source_field)}]",
                    "    end",
                ]
            )
        for attribute_name, attribute_value in sorted(mapping.record_attributes.items()):
            lines.append(
                f"    attributes[{_lua_string(attribute_name)}] = {_lua_value(attribute_value)}"
            )
        lines.extend(
            [
                f"    attributes[\"{OPAMP_PLUGIN_ID_ATTRIBUTE}\"] = "
                f"{_lua_string(plugin[PLUGIN_ID_KEY])}",
                f"    attributes[\"{OPAMP_DETECTOR_LINK_ATTRIBUTE}\"] = "
                f"{_lua_string(plugin[DETECTOR_LINK_KEY])}",
                f"    attributes[\"{SEMCONV_VERSION_ATTRIBUTE}\"] = "
                f"{_lua_string(mapping.semantic_conventions_version)}",
            ]
        )
        for attribute_name, attribute_value in sorted(mapping.resource_attributes.items()):
            lines.append(
                f"    resource[{_lua_string(attribute_name)}] = {_lua_value(attribute_value)}"
            )
        body_field = _lua_string(mapping.body_from)
        lines.extend(
            [
                "    local original_body = record[\"log\"] or record[\"message\"]",
                f"    local body = record[{body_field}] or original_body",
                "    record[\"body\"] = body",
                "    record[\"attributes\"] = attributes",
                "    record[\"resource\"] = resource",
                "    return 1, timestamp, record",
                "end",
                "",
            ]
        )
        return lines


class OpenTelemetryCollectorSemanticAdapter(SemanticConfigurationAdapter):
    """Generate Collector filelog receivers with semantic parsing operators.

    Attributes:
        tool_name: Stable target name for adapter lookup.
    """

    tool_name = OTELCOL_CONTRIB_TOOL_NAME

    def generate(self, semantic_plugins: list[SemanticPlugin]) -> list[GeneratedSemanticArtifact]:
        """Build Collector receivers whose operators emit semantic log attributes.

        Args:
            semantic_plugins: Log inputs paired with neutral parse and payload mappings.

        Returns:
            One complete Collector configuration fragment.
        """

        receivers: dict[str, Any] = {}
        receiver_names: list[str] = []
        for semantic_plugin in semantic_plugins:
            plugin = semantic_plugin.plugin
            properties = plugin[PROPERTIES_KEY]
            receiver_name = f"filelog/{_safe_identifier(plugin[PLUGIN_ID_KEY])}"
            receiver_names.append(receiver_name)
            path_value = str(properties.get(PATH_KEY, ""))
            path_suffix = str(properties.get(PATH_SUFFIX_KEY, ""))
            receivers[receiver_name] = {
                INCLUDE_KEY: [f"{path_value}{path_suffix}"],
                START_AT_KEY: properties.get(START_AT_KEY, "end"),
                OPERATORS_KEY: self._build_operators(semantic_plugin),
            }
        configuration = {
            RECEIVERS_KEY: receivers,
            SERVICE_KEY: {PIPELINES_KEY: {LOGS_KEY: {RECEIVERS_KEY: receiver_names}}},
        }
        return [
            GeneratedSemanticArtifact(
                path=OTELCOL_CONFIG_PATH,
                media_type=MEDIA_TYPE_OTELCOL_YAML,
                content=(
                    SEMANTIC_CONFIG_BANNER.encode(UTF8_ENCODING)
                    + _serialize_yaml(configuration)
                ),
            )
        ]

    @staticmethod
    def _build_operators(semantic_plugin: SemanticPlugin) -> list[dict[str, Any]]:
        """Translate one neutral mapping into Collector filelog operators.

        Args:
            semantic_plugin: Selected parser, attributes, and provenance.

        Returns:
            Ordered stanza operator mappings.
        """

        mapping = semantic_plugin.mapping
        parse = mapping.parse
        if parse[TYPE_KEY] == "regex":
            parser: dict[str, Any] = {
                TYPE_KEY: "regex_parser",
                REGEX_KEY: parse[EXPRESSION_KEY],
            }
        else:
            parser = {
                TYPE_KEY: "csv_parser",
                HEADER_KEY: ",".join(parse[COLUMNS_KEY]),
            }
        if TIME_FIELD_KEY in parse:
            parser[TIMESTAMP_KEY] = {
                PARSE_FROM_KEY: f"attributes.{parse[TIME_FIELD_KEY]}",
                LAYOUT_TYPE_KEY: "strptime",
                LAYOUT_KEY: parse[TIME_FORMAT_KEY],
            }
        if SEVERITY_FIELD_KEY in parse:
            parser[SEVERITY_KEY] = {
                PARSE_FROM_KEY: f"attributes.{parse[SEVERITY_FIELD_KEY]}"
            }
        if TYPES_KEY in parse:
            parser[TYPES_KEY] = {
                field_name: "int" if field_type == "integer" else field_type
                for field_name, field_type in parse[TYPES_KEY].items()
            }
        operators: list[dict[str, Any]] = [
            parser,
            {
                TYPE_KEY: "copy",
                FROM_KEY: f"attributes.{mapping.body_from}",
                TO_KEY: BODY_KEY,
                IF_KEY: f"attributes.{mapping.body_from} != nil",
            },
        ]
        for source_field, target_field in sorted(mapping.field_mappings.items()):
            operators.append(
                {
                    TYPE_KEY: "move",
                    FROM_KEY: f"attributes.{source_field}",
                    TO_KEY: f'attributes["{target_field}"]',
                    IF_KEY: f"attributes.{source_field} != nil",
                }
            )
        for attribute_name, attribute_value in sorted(mapping.record_attributes.items()):
            operators.append(
                {
                    TYPE_KEY: "add",
                    FIELD_KEY: f'attributes["{attribute_name}"]',
                    VALUE_KEY: attribute_value,
                }
            )
        plugin = semantic_plugin.plugin
        provenance_values = {
            OPAMP_DETECTOR_LINK_ATTRIBUTE: plugin[DETECTOR_LINK_KEY],
            OPAMP_PLUGIN_ID_ATTRIBUTE: plugin[PLUGIN_ID_KEY],
            SEMCONV_VERSION_ATTRIBUTE: mapping.semantic_conventions_version,
        }
        for attribute_name, attribute_value in sorted(provenance_values.items()):
            operators.append(
                {
                    TYPE_KEY: "add",
                    FIELD_KEY: f'attributes["{attribute_name}"]',
                    VALUE_KEY: attribute_value,
                }
            )
        for attribute_name, attribute_value in sorted(mapping.resource_attributes.items()):
            operators.append(
                {
                    TYPE_KEY: "add",
                    FIELD_KEY: f'resource["{attribute_name}"]',
                    VALUE_KEY: attribute_value,
                }
            )
        return operators


def get_semantic_adapter(tool_name: str) -> SemanticConfigurationAdapter:
    """Return the semantic generator registered for an observability agent.

    Args:
        tool_name: Stable target name from the first-stage manifest.

    Returns:
        Concrete implementation of the shared semantic adapter interface.

    Raises:
        TransformerError: The target has no semantic generator implementation.
    """

    if tool_name == FLUENT_BIT_TOOL_NAME:
        return FluentBitSemanticAdapter()
    if tool_name == OTELCOL_CONTRIB_TOOL_NAME:
        return OpenTelemetryCollectorSemanticAdapter()
    raise TransformerError(
        f"Unsupported semantic target '{tool_name}'; add a SemanticConfigurationAdapter"
    )


def _serialize_yaml(document: dict[str, Any]) -> bytes:
    """Serialize one JSON-compatible mapping as deterministic safe YAML.

    Args:
        document: Configuration mapping to serialize.

    Returns:
        UTF-8 encoded YAML bytes.
    """

    yaml_writer = YAML(typ="safe")
    yaml_writer.default_flow_style = False
    yaml_writer.sort_base_mapping_type_on_output = False
    output_stream = StringIO()
    yaml_writer.dump(document, output_stream)
    return output_stream.getvalue().encode(UTF8_ENCODING)


def _safe_identifier(value: str) -> str:
    """Convert one stable plugin ID to an agent-safe identifier.

    Args:
        value: Plugin ID containing detector and rule context.

    Returns:
        Identifier containing only letters, digits, and underscores.
    """

    return re.sub(r"[^A-Za-z0-9_]", "_", value)


def _lua_string(value: str) -> str:
    """Encode one Python string as a Lua-compatible quoted string.

    Args:
        value: Text to embed in generated Lua.

    Returns:
        JSON quoting, which is compatible with Lua string literals.
    """

    return json.dumps(value, ensure_ascii=False)


def _lua_value(value: Any) -> str:
    """Encode a scalar mapping value as a Lua literal.

    Args:
        value: String, numeric, or Boolean mapping value.

    Returns:
        Lua-compatible scalar literal.
    """

    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return _lua_string(str(value))
