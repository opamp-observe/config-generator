# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Shared names and safety limits for transformation contracts."""

API_VERSION_KEY = "api_version"
ARTIFACT_KIND_KEY = "artifact_kind"
ARTIFACTS_KEY = "artifacts"
CAPABILITIES_KEY = "capabilities"
INCLUDE_KEY = "include"
CONFIGURATION_FORMAT_KEY = "configuration_format"
CONTEXT_NAME_KEY = "context_name"
DETECTED_KEY = "detected"
DETECTOR_KEY = "detector"
DETECTOR_NAME_KEY = "detector_name"
DETECTOR_VERSION_KEY = "detector_version"
DETECTORS_KEY = "detectors"
ENGINE_KEY = "engine"
ERRORS_KEY = "errors"
FOR_EACH_KEY = "for_each"
INCLUDE_PATH_KEY = "include_path"
INCLUDES_KEY = "includes"
INPUTS_KEY = "inputs"
JINJA_ENGINE_NAME = "jinja2"
KIND_KEY = "kind"
LOG_LOCATIONS_QUERY_NAME = "log_locations"
MEDIA_TYPE_FLUENT_BIT_YAML = "application/vnd.fluent-bit.config+yaml"
METADATA_KEY = "metadata"
METADATA_API_VERSION_KEY = "metadata_api_version"
METADATA_FILE_KEY = "metadata_file"
METADATA_PATH_KEY = "metadata_path"
METADATA_SHA256_KEY = "metadata_sha256"
NAME_KEY = "name"
OUTPUT_KEY = "output"
PATH_KEY = "path"
PATH_FROM_KEY = "path_from"
PIPELINE_KEY = "pipeline"
PLUGIN_COUNT_KEY = "plugin_count"
QUERIES_KEY = "queries"
RENDER_KEY = "render"
RULES_KEY = "rules"
SCHEMA_VERSION = "2.0"
SPEC_KEY = "spec"
SIGNALS_KEY = "signals"
SUPPORTS_KEY = "supports"
TARGET_KEY = "target"
TEMPLATE_API_VERSION_KEY = "template_api_version"
TEMPLATE_KEY = "template"
TEMPLATE_METADATA_KIND = "ObservabilityTemplateMetadata"
TOOL_KEY = "tool"
TRANSFORM_KIND = "ObservabilityFragmentTransform"
VALUES_KEY = "values"
VERSION_CONSTRAINT_KEY = "version_constraint"
VERSION_KEY = "version"
SHA256_KEY = "sha256"
STRATEGY_KEY = "strategy"
LITERAL_KEY = "literal"

FLUENT_BIT_TOOL_NAME = "fluent-bit"
FLUENT_BIT_CONFIGURATION_FORMAT = "yaml"
FLUENT_BIT_INCLUDE_STRATEGY = "yaml_top_level_includes"

DEFAULT_MAX_PLUGIN_COUNT = 10_000
DEFAULT_MAX_RENDERED_BYTES = 2 * 1024 * 1024
FILE_DIGEST_BLOCK_SIZE = 64 * 1024
JSON_INDENT_SPACES = 2
UTF8_ENCODING = "utf-8"

DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
EXIT_SUCCESS = 0
EXIT_TRANSFORM_ERROR = 1
COMMAND_RENDER = "render"
COMMAND_INJECT = "inject"

SELECTION_RENDERED = "rendered"
SELECTION_STATUS_KEY = "selection_status"
SELECTION_DETECTOR_NOT_FOUND = "detector_not_found"
SELECTION_DETECTOR_NOT_DETECTED = "detector_not_detected"
SELECTION_DETECTOR_ERRORS = "detector_errors"

TRANSFORM_SCHEMA_RESOURCE = "transform_definition.schema.json"
TEMPLATE_METADATA_SCHEMA_RESOURCE = "template_metadata.schema.json"
MANIFEST_SCHEMA_RESOURCE = "orchestration_manifest.schema.json"
