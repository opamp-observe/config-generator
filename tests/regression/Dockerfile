# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

FROM osquery/osquery:5.17.0-debian12 AS osquery_source

FROM postgres:17-bookworm

USER root

RUN apt-get update \
    && apt-get install --yes --no-install-recommends nginx python3 python3-venv \
    && rm -rf /var/lib/apt/lists/*

COPY --from=osquery_source /opt/osquery/bin/osqueryd /opt/osquery/bin/osqueryd
RUN ln -s /opt/osquery/bin/osqueryd /usr/bin/osqueryi

WORKDIR /opt/opamp-config-gen
COPY license.txt runner.py ./
COPY detectors ./detectors
COPY schemas ./schemas
COPY transformers/config-template-transformer ./transformers/config-template-transformer
COPY tests/regression ./tests/regression

RUN python3 -m venv /opt/config-transformer-venv \
    && /opt/config-transformer-venv/bin/python -m pip install \
        --no-cache-dir ./transformers/config-template-transformer \
    && chmod +x /opt/opamp-config-gen/tests/regression/*.sh

ENTRYPOINT ["/opt/opamp-config-gen/tests/regression/run_regression.sh"]
