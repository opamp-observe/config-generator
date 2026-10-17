#!/bin/sh
# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

set -eu

artifact_root="${REGRESSION_ARTIFACT_ROOT:-/artifacts}"
readiness_attempt=0
maximum_readiness_attempts=60

cleanup_services() {
    # Stop both disposable deployments even when detection or transformation fails.
    nginx -s quit >/dev/null 2>&1 || true
    if [ -n "${postgres_launcher_pid:-}" ]; then
        kill "${postgres_launcher_pid}" >/dev/null 2>&1 || true
        wait "${postgres_launcher_pid}" >/dev/null 2>&1 || true
    fi
    chmod -R a+rwX "${artifact_root}" >/dev/null 2>&1 || true
}

trap cleanup_services EXIT INT TERM
mkdir -p "${artifact_root}"

# Trust is confined to this unpublished, single-container regression deployment.
export POSTGRES_HOST_AUTH_METHOD=trust
docker-entrypoint.sh postgres >"${artifact_root}/postgresql-service.log" 2>&1 &
postgres_launcher_pid=$!
nginx -t >"${artifact_root}/nginx-service.log" 2>&1
nginx >>"${artifact_root}/nginx-service.log" 2>&1

while ! pg_isready --username postgres >/dev/null 2>&1; do
    readiness_attempt=$((readiness_attempt + 1))
    if [ "${readiness_attempt}" -ge "${maximum_readiness_attempts}" ]; then
        echo "PostgreSQL did not become ready" >&2
        exit 1
    fi
    sleep 1
done

python3 /opt/opamp-config-gen/runner.py \
    --osquery /usr/bin/osqueryi \
    --detectors-root /opt/opamp-config-gen/detectors \
    --detector nginx_1 \
    --detector postgresql_17 \
    --output "${artifact_root}/detector-results.json"

/opt/config-transformer-venv/bin/obs-config-transformer render \
    --detector-results "${artifact_root}/detector-results.json" \
    --definition /opt/opamp-config-gen/transformers/config-template-transformer/examples/transforms/nginx_1_logs.yaml \
    --definition /opt/opamp-config-gen/transformers/config-template-transformer/examples/transforms/postgresql_17_logs.yaml \
    --output-root "${artifact_root}" \
    --manifest-output "${artifact_root}/orchestration.json" \
    --target-version 4.2.8

/opt/config-transformer-venv/bin/obs-config-transformer inject \
    --manifest "${artifact_root}/orchestration.json" \
    --artifact-root "${artifact_root}" \
    --parent-config /opt/opamp-config-gen/transformers/config-template-transformer/examples/fluent_bit_parent.yaml \
    --output "${artifact_root}/fluent-bit.yaml"

/opt/config-transformer-venv/bin/python \
    /opt/opamp-config-gen/tests/regression/verify_artifacts.py \
    --artifact-root "${artifact_root}"

