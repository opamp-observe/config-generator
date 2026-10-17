# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

# This sidecar shares a target's PID/network namespaces and runs the aggregate
# detector runner without modifying the product image.
FROM osquery/osquery:5.17.0-debian12

USER root
RUN apt-get update \
    && apt-get install --yes --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/detectors
COPY runner.py /opt/detectors/runner.py
COPY detectors /opt/detectors/detectors

ENTRYPOINT ["python3", "/opt/detectors/runner.py", "--osquery", "/usr/bin/osqueryi"]
