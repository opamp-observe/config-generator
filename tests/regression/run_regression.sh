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
export PGDATA=/var/lib/postgresql/17/data
docker-entrypoint.sh postgres -D "${PGDATA}" >"${artifact_root}/postgresql-service.log" 2>&1 &
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
    --mapping-root /opt/opamp-config-gen/transformers/config-template-transformer/mappings \
    --target-tool fluent-bit \
    --output-root "${artifact_root}" \
    --manifest-output "${artifact_root}/orchestration-fluent-bit.json" \
    --target-version 5.1.0

/opt/config-transformer-venv/bin/obs-config-transformer inject \
    --manifest "${artifact_root}/orchestration-fluent-bit.json" \
    --artifact-root "${artifact_root}" \
    --parent-config /opt/opamp-config-gen/transformers/config-template-transformer/examples/fluent_bit_parent.yaml \
    --output "${artifact_root}/fluent-bit-source.yaml"

/opt/config-transformer-venv/bin/obs-config-transformer semantic-map \
    --manifest "${artifact_root}/orchestration-fluent-bit.json" \
    --detector-results "${artifact_root}/detector-results.json" \
    --mapping-root /opt/opamp-config-gen/transformers/config-template-transformer/semantic-mappings \
    --output-root "${artifact_root}" \
    --semantic-manifest-output "${artifact_root}/semantic-manifest-fluent-bit.json"

cp /opt/opamp-config-gen/transformers/config-template-transformer/examples/fluent_bit_semantic_parent.yaml \
    "${artifact_root}/fluent-bit-semantic.yaml"

/opt/config-transformer-venv/bin/obs-config-transformer render \
    --detector-results "${artifact_root}/detector-results.json" \
    --mapping-root /opt/opamp-config-gen/transformers/config-template-transformer/mappings \
    --target-tool otelcol-contrib \
    --output-root "${artifact_root}" \
    --manifest-output "${artifact_root}/orchestration-otelcol.json" \
    --target-version 0.163.0

/opt/config-transformer-venv/bin/obs-config-transformer semantic-map \
    --manifest "${artifact_root}/orchestration-otelcol.json" \
    --detector-results "${artifact_root}/detector-results.json" \
    --mapping-root /opt/opamp-config-gen/transformers/config-template-transformer/semantic-mappings \
    --output-root "${artifact_root}" \
    --semantic-manifest-output "${artifact_root}/semantic-manifest-otelcol.json"

cp /opt/opamp-config-gen/transformers/config-template-transformer/examples/otelcol_semantic_parent.yaml \
    "${artifact_root}/otelcol-semantic-parent.yaml"

/opt/config-transformer-venv/bin/python \
    /opt/opamp-config-gen/tests/regression/verify_artifacts.py \
    --artifact-root "${artifact_root}"

