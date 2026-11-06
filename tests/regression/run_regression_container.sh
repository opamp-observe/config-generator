#!/bin/sh
# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

set -eu

script_directory=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repository_root=$(CDPATH= cd -- "${script_directory}/../.." && pwd)
output_directory=${1:-"${repository_root}/build/regression-artifacts"}

mkdir -p "${output_directory}"
docker build \
    --file "${script_directory}/Dockerfile" \
    --tag "opamp-nginx-postgresql-regression:test" \
    "${repository_root}"
docker run --rm \
    --cap-add SYS_PTRACE \
    --security-opt seccomp=unconfined \
    --volume "${output_directory}:/artifacts" \
    "opamp-nginx-postgresql-regression:test"
