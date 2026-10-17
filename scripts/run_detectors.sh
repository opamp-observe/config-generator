#!/usr/bin/env sh
# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

# Resolve the repository from this script so mounted container paths work.
SCRIPT_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$SCRIPT_DIRECTORY/.." && pwd)
OUTPUT_PATH=${DETECTOR_OUTPUT_PATH:-"$REPOSITORY_ROOT/detector-results.json"}
PYTHON_COMMAND=${PYTHON_COMMAND:-python3}

exec "$PYTHON_COMMAND" "$REPOSITORY_ROOT/runner.py" --output "$OUTPUT_PATH" "$@"

