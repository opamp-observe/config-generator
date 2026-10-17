# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Sandboxed Jinja rendering and YAML structural validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import FileSystemLoader, StrictUndefined, TemplateError
from jinja2.sandbox import ImmutableSandboxedEnvironment
from ruamel.yaml import YAML, YAMLError

from config_template_transformer.constants import (
    DEFAULT_MAX_PLUGIN_COUNT,
    DEFAULT_MAX_RENDERED_BYTES,
    UTF8_ENCODING,
)
from config_template_transformer.errors import TransformerError


class JinjaFragmentRenderer:
    """Render JSON-compatible plugin contexts with a restricted Jinja environment.

    Attributes:
        template_root: Directory containing only caller-approved templates.
        max_plugin_count: Maximum plugin objects accepted in one render operation.
        max_rendered_bytes: Maximum UTF-8 output size accepted after rendering.
        environment: Immutable sandbox configured with strict undefined behavior.
    """

    def __init__(
        self,
        template_root: Path,
        max_plugin_count: int = DEFAULT_MAX_PLUGIN_COUNT,
        max_rendered_bytes: int = DEFAULT_MAX_RENDERED_BYTES,
    ) -> None:
        """Create a reusable sandboxed template environment.

        Args:
            template_root: Directory containing approved Jinja template files.
            max_plugin_count: Safety limit for normalized plugin objects.
            max_rendered_bytes: Safety limit for rendered UTF-8 bytes.
        """

        self.template_root = template_root.resolve()
        self.max_plugin_count = max_plugin_count
        self.max_rendered_bytes = max_rendered_bytes
        self.environment = ImmutableSandboxedEnvironment(
            loader=FileSystemLoader(self.template_root),
            undefined=StrictUndefined,
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(
        self,
        template_name: str,
        context_name: str,
        plugins: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Render plugin objects and parse the result as a YAML mapping.

        Args:
            template_name: Template path relative to the configured template root.
            context_name: Jinja variable that receives the plugin list.
            plugins: Normalized JSON-compatible plugin objects.

        Returns:
            Parsed YAML fragment mapping.

        Raises:
            TransformerError: Limits, sandbox rendering, or YAML structure are invalid.
        """

        if len(plugins) > self.max_plugin_count:
            raise TransformerError(
                f"Plugin count {len(plugins)} exceeds limit {self.max_plugin_count}"
            )
        try:
            json.dumps(plugins)
            template = self.environment.get_template(template_name)
            rendered_text = template.render(**{context_name: plugins})
        except (TypeError, ValueError, TemplateError) as error:
            raise TransformerError(
                f"Jinja rendering failed for {template_name}: {error}"
            ) from error

        rendered_bytes = rendered_text.encode(UTF8_ENCODING)
        if len(rendered_bytes) > self.max_rendered_bytes:
            raise TransformerError(
                f"Rendered output exceeds {self.max_rendered_bytes} bytes: {template_name}"
            )
        yaml_parser = YAML(typ="safe")
        try:
            fragment = yaml_parser.load(rendered_text)
        except YAMLError as error:
            raise TransformerError(
                f"Rendered YAML is invalid for {template_name}: {error}"
            ) from error
        if not isinstance(fragment, dict):
            raise TransformerError(f"Rendered fragment must be a mapping: {template_name}")
        return fragment

    def template_path(self, template_name: str) -> Path:
        """Resolve a template path while preventing traversal outside its root.

        Args:
            template_name: Template path relative to the configured root.

        Returns:
            Resolved existing template path.

        Raises:
            TransformerError: The path escapes the root or is not a file.
        """

        resolved_path = (self.template_root / template_name).resolve()
        if not resolved_path.is_relative_to(self.template_root) or not resolved_path.is_file():
            raise TransformerError(
                f"Template is outside the template root or missing: {template_name}"
            )
        return resolved_path
