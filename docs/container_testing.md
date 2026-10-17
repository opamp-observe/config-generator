<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Container test guide

## Candidate product images

| Detector | Candidate | Notes |
|---|---|---|
| Host inventory | `osquery/osquery:5.17.0-debian12` | Confirms container classification and container-visible identity/network data |
| PostgreSQL 17 | `postgres:17-bookworm` | Docker Official Image |
| PostgreSQL 18 | `postgres:18-bookworm` | Docker Official Image |
| PostgreSQL 19 | `postgres:19beta4-bookworm` | Development-only as of 2026-10-14 |
| WebLogic 12 | Oracle Container Registry WebLogic 12.2.1.4 image or Oracle `docker-images/OracleWebLogic` 12.2.1.4 sample | Registry login and accepted terms may be required |
| WebLogic 14 | Oracle Container Registry WebLogic 14.1.1 image or Oracle `docker-images/OracleWebLogic` 14.1.1.0 sample | Prefer Oracle's patched registry image |
| Oracle Database 19 | `container-registry.oracle.com/database/enterprise:19.3.0.0` or the Oracle 19.3 build context | Licensed media/terms required |
| Oracle Database 21 | Oracle 21.3 XE image/build context | XE is the lowest-friction functional target |
| Oracle Database 26 | `container-registry.oracle.com/database/free:latest` or Oracle 23.26.0 build context | 26ai uses 23.26.x image/build numbering |
| Oracle RAC | `database/rac_ru:latest-19`, `database/rac_ru:latest`, or `database/rac:latest` | Podman, privileges, storage, memory, and registry terms required |
| ORDS | Add a separate ORDS container or standalone ORDS process beside an Oracle DB target | Verify the DB detector reports an independent ORDS process |

Authoritative catalogs:

- https://hub.docker.com/_/postgres
- https://github.com/oracle/docker-images/tree/main/OracleWebLogic
- https://github.com/oracle/docker-images/tree/main/OracleDatabase/SingleInstance
- https://github.com/oracle/docker-images/tree/main/OracleDatabase/RAC/OracleRealApplicationClusters

## Test pattern

The strongest test installs osquery in an image derived from the product image.
That gives the query engine the same PID, network, environment, and filesystem
view as the product.

Example conceptual Dockerfile:

```dockerfile
FROM postgres:18-bookworm
USER root
# Add the official osquery apt repository for the base distribution, then:
RUN apt-get update && apt-get install -y osquery python3 && rm -rf /var/lib/apt/lists/*
COPY . /opt/detectors
```

Build and start the derived image with its normal product entry point. In a
second terminal, run:

```sh
docker exec --user root <container> \
  python3 /opt/detectors/runner.py \
  --detector postgresql_18 \
  --output /tmp/detector-results.json
docker exec --user root <container> \
  python3 /opt/detectors/tests/validate_detectors.py
docker cp <container>:/tmp/detector-results.json .
```

For Oracle Linux images, configure the official osquery RPM repository and
install the osquery RPM instead of using apt. Do not bake Oracle passwords,
wallets, registry credentials, or licensed installation media into a reusable
test image.

## Sidecar alternative

A Linux sidecar can share the target PID and network namespaces:

```sh
docker run --rm --user 0 \
  --cap-add SYS_PTRACE \
  --security-opt seccomp=unconfined \
  --pid=container:<target> \
  --network=container:<target> \
  --volumes-from <target>:ro \
  -v "$PWD:/opt/detectors:ro" \
  <your-osquery-test-image> \
  python3 /opt/detectors/runner.py --output /tmp/results.json
```

This is suitable for process and port tests. Image-layer configuration files
may still be invisible unless they live in shared volumes. Treat missing
filesystem evidence in sidecar output as inconclusive.

## Assertions

For each target:

1. Run `tests/validate_detectors.py` inside the same operating-system family.
2. Run only the expected detector and assert `detected` is true.
3. Assert at least one runtime row and one listening-port row.
4. Check every reported candidate path against the actual deployment.
5. For WebLogic, compare Administration/Managed Server mappings with the domain.
6. For Oracle, test standalone, separate ORDS, and RAC targets independently.
7. Stop the product and confirm strict discovery changes `detected` to false.
8. Preserve the aggregate JSON as CI evidence.

For `host_inventory_1`, assert the container test returns
`possible_container`, then compare `host_identity`, `network_ips`, and
`execution_identity` with the namespace and user assigned to the test
container.

PostgreSQL 19 assertions must retain `release_status: development` until the
PostgreSQL project publishes a stable 19 release.

## Ready-to-build sidecar

The repository includes `containers/Dockerfile`, which adds Python to the
osquery 5.17 Debian image and copies the detector runner and packs. Build it
from the repository root:

```sh
docker build -f containers/Dockerfile -t opamp-detectors:test .
```

The following is a complete PostgreSQL 18 example:

```sh
docker run -d --name detector-pg18 \
  -e POSTGRES_PASSWORD=detector-test-only \
  postgres:18-bookworm

mkdir -p test-results
docker run --rm --user 0 \
  --cap-add SYS_PTRACE \
  --security-opt seccomp=unconfined \
  --pid=container:detector-pg18 \
  --network=container:detector-pg18 \
  --volumes-from detector-pg18:ro \
  -v "$PWD/test-results:/output" \
  opamp-detectors:test \
  --detector postgresql_18 \
  --output /output/postgresql-18.json
```

Repeat with `postgres:17-bookworm`/`postgresql_17` and
`postgres:19beta4-bookworm`/`postgresql_19`. Remove the disposable target
container after reviewing the JSON:

```sh
docker rm -f detector-pg18
```

For a product split across containers, run the sidecar once per target
container and retain each aggregate. For example, run it against every
WebLogic Administration/Managed Server container and against the database,
ORDS, and each RAC node. PID-scoped results are intentionally not merged across
unrelated containers.

`SYS_PTRACE` and the relaxed seccomp profile allow osquery to read the target
process environment across the container boundary; without them, strict
version evidence such as `PG_MAJOR`, `ORACLE_HOME`, or `DOMAIN_HOME` may be
unavailable. Grant these only to the short-lived detector sidecar. If that
capability is prohibited, install/run osquery inside the product image instead.

