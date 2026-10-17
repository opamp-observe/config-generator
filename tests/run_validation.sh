#!/usr/bin/env sh
# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

TEST_DIRECTORY=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPOSITORY_ROOT=$(CDPATH= cd -- "$TEST_DIRECTORY/.." && pwd)
PYTHON_COMMAND=${PYTHON_COMMAND:-python3}

"$PYTHON_COMMAND" -m unittest discover -s "$TEST_DIRECTORY" -p "test_*.py"
"$PYTHON_COMMAND" "$TEST_DIRECTORY/validate_detectors.py" "$@"

