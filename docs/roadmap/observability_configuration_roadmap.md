<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Observability configuration roadmap

## Purpose

This roadmap describes the planned evolution from product-specific discovery
and a small set of configuration templates into a broader, testable
observability configuration system. It focuses on six areas:

- general and application-specific log-source discovery;
- explicit duplicate-log policy and deterministic deduplication;
- safe database queries for operational data such as slow-query statistics;
- MongoDB discovery and configuration support;
- additional observability-agent adapters and mappings;
- container-based regression evidence and automated mapping-version gap
  detection.

The roadmap records intended direction rather than committed release dates.
Each phase should be delivered as a versioned contract with tests and migration
notes rather than as an undocumented behavior change.

## Guiding principles

1. **Discovery and collection are separate decisions.** Finding a possible log,
   endpoint, or database capability does not automatically authorize its
   collection.
2. **Observed evidence is stronger than convention.** An open log file or
   parsed application configuration should rank above a conventional path that
   may not exist.
3. **Generated configuration must be explainable.** Every plugin parameter
   should trace back to detector evidence, a named mapping default, or explicit
   deployment policy.
4. **Duplicates must be visible.** Deduplication should produce an audit record;
   it must not silently discard sources.
5. **Database access is least-privilege and bounded.** Discovery must not enable
   extensions, modify schema, or run arbitrary operator-supplied SQL by default.
6. **Compatibility is demonstrated, not assumed.** A version number alone does
   not prove that an existing mapping works with a new agent release.
7. **Regression evidence is a build artifact.** Detector input, generated
   configuration, native validation output, and checksums should be retained
   together.

## Current baseline

The repository already provides versioned osquery detectors, aggregate result
schemas, an external agent-mapping catalogue, version-floor selection,
sandboxed Jinja rendering, Fluent Bit and OpenTelemetry Collector Contrib
adapters, orchestration manifests, and an initial NGINX/PostgreSQL regression
container.

The following limitations motivate this roadmap:

- log locations use product-specific row shapes rather than one normalized
  cross-detector contract;
- the same physical log can be reported by a host detector, application
  detector, container runtime, or multiple application instances;
- candidate paths and observed paths are not consistently distinguished during
  configuration generation;
- database detectors primarily inspect processes, files, and ports rather than
  making authenticated database queries;
- mappings cover only a small number of products and agent types;
- regression results are locally retained but not yet published as a complete,
  portable evidence bundle; and
- maintainers must manually notice new observability-agent releases and decide
  whether mappings need updates.

## Workstream 1: normalized log-source discovery

### Goal

Discover log sources consistently across the host, operating system,
containers, and applications while retaining enough evidence to make safe
collection decisions.

### Source categories

The normalized contract should represent at least:

- regular files and file globs;
- systemd journal units and namespaces;
- syslog files, sockets, facilities, and remote destinations;
- kernel log access through journal, `/dev/kmsg`, or equivalent interfaces;
- process standard output and standard error;
- Docker and other container-runtime log files or APIs;
- Kubernetes pod/container log paths when visible from the host;
- Windows Event Log channels;
- application-configured file, syslog, or event destinations; and
- database-native log, audit, and slow-query destinations.

### Normalized contract

Introduce a versioned `log_source` result object shared by generic and
application detectors. A proposed shape is:

```json
{
  "source_id": "stable detector-local identity",
  "source_type": "file",
  "locator": "/var/log/nginx/access.log",
  "product": "nginx",
  "instance_id": "host-or-process-scoped identity",
  "signal": "application_log",
  "format_hint": "nginx_access",
  "evidence_level": "observed_open",
  "readable": true,
  "discovered_by": ["nginx_1", "linux_system_1"]
}
```

The final schema should define stable enums and type-specific locator fields
rather than relying on a single overloaded string. Each row must describe one
source; detectors should stop returning semicolon-separated collections of
candidate paths in one field.

### General versus application discovery

General discovery should answer “what log mechanisms and readable sources are
visible on this host?” Application discovery should answer “which sources
belong to this product instance, and how should they be parsed?”

The two are intentionally allowed to overlap:

- a general detector may observe that NGINX has an open file descriptor for
  `/var/log/nginx/access.log`;
- the NGINX detector may derive the same file from active configuration and add
  an `nginx_access` format hint; and
- a container detector may identify that the same stream is also captured by a
  container-runtime JSON log.

Overlap supplies corroborating evidence. Deduplication occurs after discovery,
when the system has all evidence available.

### Discovery precedence

Rank evidence without automatically discarding lower-ranked records:

1. source observed open or actively receiving data;
2. source parsed from active application configuration;
3. source reported by a service manager or container runtime;
4. source derived from process arguments or environment;
5. accessible conventional path; and
6. documented candidate requiring verification.

Mappings should default to collecting verified sources. Candidate-only sources
should require an explicit policy or should be emitted as recommendations rather
than active plugins.

### Deliverables

- Versioned normalized log-source JSON Schema.
- Shared detector-output conventions and helper validation.
- Migration of NGINX, PostgreSQL, Linux system, and host inventory detectors.
- Separate rows for every candidate or observed source.
- Platform-specific canonicalization tests.
- Mapping support for source type, evidence level, readability, and format
  hints.

### Acceptance criteria

- One physical source can be correlated across multiple detectors.
- Candidate-only paths are distinguishable from verified readable paths.
- Linux files, journald/syslog, container logs, and Windows Event Log channels
  can be represented without overloading one field.
- Existing detector data can be migrated or adapted without silently changing
  collection behavior.

## Workstream 2: duplicate policy and log-source reconciliation

### Goal

Permit intentional duplication where it is useful, while preventing accidental
double ingestion, duplicate billing, repeated processing, and feedback loops.

### Policy modes

Support an explicit configuration policy rather than one hard-coded behavior:

| Mode | Behavior |
| --- | --- |
| `preserve` | Generate every discovered source and annotate possible duplicates. |
| `deduplicate` | Generate one collector input for each canonical source identity and retain merged provenance. |
| `report_only` | Do not alter generation; publish duplicate groups and a recommended winner. |
| `error` | Stop generation when unresolved duplicate groups remain. Intended for tightly controlled deployments. |

The initial default should be `report_only` until canonicalization is proven
across supported platforms.

### Exact duplicate identity

For file sources, construct a canonical identity from fields such as:

- host or container namespace;
- resolved path with platform-appropriate case handling;
- filesystem/device and inode identity when safely available;
- source type and transport;
- container ID or workload identity; and
- rotation relationship.

Do not resolve symlinks or host/container path translations blindly. Resolution
must preserve both the observed locator and canonical locator so generated
configuration still uses a path valid in the agent's namespace.

For journal, event-log, syslog, and network sources, define type-specific keys
instead of forcing them into a file-path algorithm.

### Semantic duplicate detection

Some sources contain the same events without sharing an identity. Examples are
an application file also forwarded to syslog, or container stdout collected
through both the runtime and a host file. Treat these as possible semantic
duplicates with a confidence and reason, not as exact duplicates.

Initial reconciliation rules should prefer:

- observed sources over candidates;
- application-specific records with parser/format knowledge over generic file
  observations;
- one namespace-correct locator over an inaccessible host/container alias; and
- a source already owned by deployment policy over a newly inferred source.

### Merging configuration intent

When exact duplicates merge, preserve all detector provenance and combine
compatible enrichment such as tags, format hints, and instance identifiers.
Processor lists must not be concatenated blindly: processor identity, order,
and configuration affect output semantics. Conflicting processors or plugin
parameters should create a reconciliation conflict requiring policy or review.

### Deliverables

- Canonical source-identity library with Linux and Windows behavior.
- Versioned duplicate-policy configuration.
- Reconciliation report in the orchestration manifest or a companion JSON
  artifact.
- Exact and semantic duplicate classifications with reasons and confidence.
- Conflict reporting for tags, parsers, processors, and plugin defaults.
- Tests for symlinks, rotated logs, bind mounts, container paths, case
  differences, and cross-detector overlap.

### Acceptance criteria

- Every removed duplicate points to the retained source and lists all evidence.
- Repeated runs over identical input select the same winner.
- `preserve` never drops a source and `error` never silently chooses one.
- Processor or parameter conflicts are reported rather than arbitrarily merged.
- No generated agent configuration tails the same exact file twice under the
  default production policy.

## Workstream 3: safe database-query execution

### Goal

Augment process/file/port discovery with bounded, authenticated database queries
for operational facts that cannot be obtained reliably from the host. Slow
queries are the first use case.

### Separate query classes

Keep two classes of database interaction distinct:

1. **Discovery-time queries** run briefly to identify server version,
   capabilities, enabled extensions, configuration, and available telemetry.
2. **Runtime telemetry queries** are configured in an observability agent and
   run repeatedly to collect metrics or logs.

The detector result should state which class produced each field. The
configuration generator should not turn a one-time discovery query into a
recurring production query without an explicit mapping and interval.

### Query catalogue

Store reviewed, versioned query definitions rather than accepting arbitrary SQL
from detector output. Each definition should declare:

- database engine and supported server versions;
- stable query name and query-definition version;
- purpose and expected columns;
- required privileges and optional extensions;
- read-only expectation;
- statement timeout, row limit, and byte limit;
- whether query text or values may contain sensitive data;
- redaction and truncation policy; and
- result schema.

For PostgreSQL slow-query support, evaluate:

- `pg_stat_statements` availability and privilege requirements;
- query identifier, calls, total/mean/max execution time, returned rows, and
  database/user identity;
- whether full SQL text is disabled by default in favor of query identifiers or
  normalized fingerprints;
- reset behavior and cumulative-counter interpretation; and
- log-based slow-query collection when database statistics are unavailable.

The system must report that an extension is unavailable; it must not enable or
install the extension automatically.

After the PostgreSQL path is proven, add separate reviewed catalogues for other
supported relational engines such as Oracle. SQL, privilege models, statistics
lifecycles, and redaction requirements are engine-specific; queries must not be
treated as portable merely because their output columns look similar.

### Execution boundary

Introduce a small database-query runner with a narrow interface rather than
placing driver and credential logic in every detector. It should:

- resolve a credential reference from the approved credentials mechanism
  without writing plaintext credentials into detector results;
- require TLS according to deployment policy;
- open a read-only transaction where supported;
- allow only catalogue query identifiers and bound parameters;
- apply connection, statement, row, and output-size limits;
- redact sensitive errors and query values;
- record engine/version, query identity, timing, and outcome; and
- close connections deterministically.

If this becomes a Python-served endpoint, its component name must use the
`*-service` suffix. A local executable without an endpoint may use a
`*-runner` name.

### Runtime-agent mappings

Add mappings for agents capable of scheduled SQL collection, beginning with an
OpenTelemetry Collector Contrib SQL query receiver if it satisfies the required
security and version constraints. Generated configuration should reference
deployment-managed credentials or environment expansion supported by the
agent; it must not embed discovered secrets.

### Deliverables

- Versioned database query-definition schema and catalogue.
- Credential-reference and connection-policy contract.
- PostgreSQL capability and slow-query definitions.
- Result schemas with redaction tests.
- Optional runtime telemetry mapping for a suitable agent receiver.
- Ephemeral PostgreSQL regression cases with and without required extensions.

### Acceptance criteria

- No arbitrary SQL can enter through detector result JSON.
- Queries are bounded, read-only, version-aware, and independently testable.
- Slow-query output is useful without exposing full query text by default.
- Missing privileges or extensions produce explicit capability results.
- Generated runtime configuration contains credential references, not secrets.

## Workstream 4: MongoDB support

### Goal

Provide first-class MongoDB discovery, log/metrics mapping, and optional safe
database interrogation for common standalone, replica-set, and sharded
deployments.

### Detector scope

Create versioned MongoDB detectors covering supported Community and Enterprise
server versions. Discovery should include:

- `mongod` and `mongos` process identity and executable version;
- listening TCP and Unix-domain sockets;
- configuration-file locations and active command-line overrides;
- storage path and log destination;
- file, syslog, and stdout logging modes;
- profiler and slow-operation configuration when observable;
- replica-set or sharded-cluster role without exposing credentials;
- TLS configuration evidence and certificate paths;
- service/container identity; and
- stable instance identifiers.

Start with Linux packages and containers. Add Windows service coverage after the
cross-platform path and service contracts are stable.

### Authenticated interrogation

MongoDB is not SQL, so it needs a separate allowlisted command catalogue using
an official driver. Candidate commands should be read-only and bounded, such as
server/build information, connection status, replica-set role, operation
latency, and profiler configuration. Current operations or profiler documents
may contain application data and require explicit redaction and opt-in policy.

### Agent mappings

Provide mappings for:

- MongoDB server logs through Fluent Bit `tail` and OpenTelemetry `filelog`;
- multiline handling where supported and required by the actual log format;
- MongoDB metrics through a supported OpenTelemetry or other agent receiver;
- stable resource attributes for cluster, replica set, role, host, and instance;
  and
- optional processors for parsing or redacting records, with external scripts
  and assets packaged separately.

### Regression topology

Add container scenarios for:

- standalone MongoDB;
- authenticated standalone MongoDB with TLS where practical;
- a minimal replica set;
- file logging and container stdout logging; and
- profiler disabled/enabled with synthetic slow operations.

### Acceptance criteria

- Detection does not require authentication for basic process/file/port facts.
- Authenticated commands use least-privilege credentials and explicit opt-in.
- Log mappings do not double-collect file and container representations by
  default.
- Native agent validation and a live smoke collection pass for supported
  mappings.
- Sensitive command/query content is excluded or redacted in published
  regression artifacts.

## Workstream 5: additional observability-agent types

### Goal

Extend the same detector evidence to more agents without duplicating discovery
logic or weakening compatibility checks.

### Proposed order

| Priority | Agent | Initial scope | Composition model to implement |
| --- | --- | --- | --- |
| 1 | Vector | File and journald logs; NGINX/PostgreSQL/MongoDB sources | Generated source/transform fragments merged into Vector configuration. |
| 2 | Fluentd | File logs and parser/filter chains | Include-based fragment composition. |
| 3 | Grafana Alloy | OpenTelemetry-compatible logs and metrics | Component graph or supported config include mechanism. |
| 4 | Elastic Agent and Filebeat | File, journald, and application modules | Policy or input-fragment composition with versioned integration constraints. |
| 5 | Telegraf | Database and service metrics | Input plugin fragments and directory includes. |

Priorities may change based on deployment demand and whether an agent provides
native receivers for the required signals.

### Adapter contract work

Every new agent requires:

- stable agent type and configuration media type;
- mapping JSON resources with honest minimum versions;
- Jinja templates and metadata sidecars;
- structural validation beyond merely parsing YAML/TOML/JSON;
- a composition strategy for a parent configuration;
- native validation or dry-run integration;
- empty-fragment behavior;
- credential-reference handling where relevant; and
- container regression coverage for every advertised capability.

### Capability matrix

Publish a generated matrix with rows for detector capabilities and columns for
agent/version families. Distinguish:

- supported and regression-tested;
- supported but requiring deployment assets;
- syntactically generated but not live-tested;
- not supported by the agent; and
- planned.

### Acceptance criteria

- Adding an adapter does not require modifying detector output for
  agent-specific field names.
- Every advertised mapping has a tested version floor and native validation.
- Composition behavior is explicit; unsupported injection fails with an
  actionable message.
- The capability matrix is generated from validated mapping/template metadata
  rather than maintained only by hand.

## Workstream 6: rich container regression and published evidence

### Goal

Build a reproducible matrix that starts real products and agents, exercises the
complete detector-to-agent flow, and publishes enough evidence to diagnose a
failure without rerunning it locally.

### Test layers

1. **Contract tests:** validate detector manifests, schemas, mappings, template
   metadata, and orchestration manifests.
2. **Product discovery tests:** start a real product and prove expected detector
   evidence is present.
3. **Configuration generation tests:** render mappings for each supported agent
   version and compare semantic configuration structures.
4. **Native validation tests:** run each agent's dry-run or configuration check.
5. **Live smoke tests:** start the agent, create a known log/metric/database
   event, and verify it reaches a local test sink.
6. **Upgrade regression tests:** rerun unchanged mappings against newly released
   agent versions before declaring them compatible.

### Container topology

Use isolated Docker Compose or equivalent scenarios rather than one increasingly
large image. Compose services should include:

- the product under test;
- osquery/detector execution where host visibility can be represented safely;
- the observability agent and generated configuration;
- a deterministic local sink for logs and metrics;
- optional credential and TLS fixtures; and
- an artifact collector.

Images should be pinned by version and, in CI, recorded by immutable digest.
Tests should avoid publishing product ports to the host unless a scenario
requires it.

### Published result format

Every regression run should write a machine-readable `regression-results.json`
and standard JUnit XML. The result should include:

- repository revision and dirty-state indicator;
- scenario name and start/end timestamps;
- host/container runtime versions;
- product and agent image tags and digests;
- detector, mapping, template, and adapter versions;
- pass/fail/skip status for each test layer;
- command exit codes and bounded stdout/stderr references;
- generated artifact and manifest hashes;
- redaction summary; and
- failure classification.

Generate a concise Markdown or HTML summary for human review. CI should publish
the summary and JUnit results directly and retain the complete evidence archive.

### Evidence archive

Create one deterministic ZIP archive per scenario or matrix shard containing
only relevant, sanitized content:

```text
scenario-name.zip
  regression-results.json
  junit.xml
  environment.json
  detector-results.json
  selected-mappings/
  templates-and-metadata/
  generated-config/
  orchestration.json
  native-validation/
  agent-output/
  sink-observations/
  checksums.sha256
```

Do not include database credentials, private keys, bearer tokens, complete
environment dumps, or unredacted query/application payloads. Add a pre-archive
secret scan and fail packaging if prohibited material is detected.

### CI publication

- Upload JUnit results through the CI test-report mechanism.
- Publish the human summary as a job summary.
- Upload ZIP evidence with a documented retention period.
- Attach release-qualified compatibility evidence to releases where supported.
- Keep failed-run evidence long enough for triage.
- Provide the same packaging command locally so CI output is reproducible.

### Acceptance criteria

- A developer can reproduce one scenario with one documented command.
- CI publishes structured results and a sanitized ZIP even when a test fails.
- Every supported mapping is covered by contract and native-validation tests.
- Representative mappings have live event-to-sink tests.
- Archive contents have checksums and enough version information to reproduce
  the run.

## Workstream 7: observability-agent version and mapping-gap audit

### Goal

Provide a quick utility that detects newly available agent versions and decides
what validation or mapping work is required.

### Important distinction

A new upstream version does not always require a new mapping. A new mapping is
needed when configuration syntax, plugin availability, defaults, deprecations,
or behavior differs from the highest compatible mapping. Otherwise, the
existing highest version floor can remain valid after regression testing.

The utility should therefore report a **mapping gap** separately from a
**validation gap**.

### Proposed utility

Add a command such as:

```text
mapping-version-audit
```

It should support two modes:

- **Offline audit:** compare a supplied agent/version inventory with local
  mapping floors and template constraints.
- **Online audit:** query configured authoritative release APIs or container
  registries, cache results, and compare them with the local catalogue.

### Inputs

- mapping JSON resources and minimum versions;
- template metadata version constraints and capabilities;
- adapter registration and supported configuration format;
- configured release sources for each agent;
- optional container-image allowlist and architecture list;
- latest successful regression results; and
- ignored/prerelease version policy.

### Output statuses

| Status | Meaning |
| --- | --- |
| `covered` | A compatible mapping exists and this exact agent version passed regression. |
| `validation_required` | A mapping appears compatible, but this exact version has not passed regression. |
| `mapping_required` | No mapping/template contract covers the version or a known breaking change applies. |
| `adapter_required` | The agent type has no registered target adapter. |
| `unsupported` | Policy explicitly excludes the version, edition, architecture, or prerelease. |
| `unknown` | Release information or compatibility evidence is incomplete. |

### Suggested workflow

1. Discover stable upstream versions from authoritative release sources.
2. Compare them with local mapping floors and template constraints.
3. Check the regression-results index for the exact version and platform.
4. For `validation_required`, enqueue the existing mapping against the new
   agent container.
5. Promote to `covered` when native and live regression checks pass.
6. Mark `mapping_required` only when validation fails for a configuration
   compatibility reason or an upstream breaking change is known.
7. Produce JSON and Markdown reports, a meaningful process exit code, and an
   optional issue-ready summary. Creating issues or pull requests should remain
   a separate explicitly authorized action.

### Supply-chain and reliability requirements

- Use authoritative release APIs or registries and record source URLs.
- Cache responses and tolerate rate limits or temporary network failure.
- Do not execute an untrusted downloaded binary merely to inspect its version.
- Pin regression images by digest after discovery.
- Record prerelease, edition, operating-system, and CPU architecture dimensions.
- Treat mutable tags such as `latest` as discovery hints, never compatibility
  evidence.

### Acceptance criteria

- One local command reports mapping and validation gaps for every registered
  agent.
- CI can run the audit on a schedule and publish JSON plus Markdown output.
- A newly released agent version becomes `validation_required` without forcing
  an unnecessary mapping copy.
- Successful regression changes the status to `covered` reproducibly.
- Breaking configuration changes produce `mapping_required` with supporting
  validation evidence.

## Proposed sequencing

| Phase | Scope | Depends on | Exit condition |
| --- | --- | --- | --- |
| 1 | Normalized log-source contract and report-only reconciliation | Existing detector schemas | NGINX, PostgreSQL, and Linux sources use the shared contract with duplicate reports. |
| 2 | Regression result schema and deterministic ZIP evidence | Existing regression container | Current Fluent Bit and Collector mappings publish sanitized evidence bundles. |
| 3 | Exact deduplication policy and manifest reconciliation records | Phase 1 | Production policy prevents exact double collection with auditable winners. |
| 4 | PostgreSQL safe-query catalogue and slow-query prototype | Phase 2 credential/test fixtures | Bounded discovery query and one runtime collection path pass container regression. |
| 5 | MongoDB detector, logging mappings, and container scenarios | Phases 1–2 | Standalone MongoDB logs/metrics pass detection, generation, and live smoke tests. |
| 6 | Version-audit utility and scheduled validation-gap workflow | Phase 2 result index | New agent releases produce actionable covered/validation/mapping statuses. |
| 7 | Vector, Fluentd, Alloy, Elastic, and Telegraf expansion | Phases 1–3 and 6 | Each added adapter has mappings, native validation, evidence, and matrix entries. |
| 8 | Adaptive dashboard generation | Normalized telemetry contracts and regression evidence | Backend-neutral blueprints compile into validated Grafana and Kibana artifacts for supported storage backends. |

Workstreams may progress in parallel where their contracts do not conflict. In
particular, the result/evidence format and offline version audit can begin while
the normalized log-source schema is being designed.

## Cross-cutting deliverables

- Version every public detector, query, mapping, template, result, and evidence
  contract.
- Keep environment variables as the highest-precedence runtime override where
  shared configuration is involved.
- Add schema migration guidance when fields are renamed or normalized.
- Generate compatibility documentation from validated metadata where possible.
- Preserve DEBUG-level diagnostic logging while redacting secrets and sensitive
  database content.
- Run module-local Ruff, Pylint, pytest, and coverage gates for focused changes.
- Run the repository-wide security and validation gate for shared contracts,
  build changes, releases, and broad refactors.

## Completion definition

This roadmap is complete when:

- host and application detectors emit normalized, reconcilable log sources;
- duplicate handling is explicit, deterministic, configurable, and auditable;
- PostgreSQL slow-query and MongoDB operational data can be collected through
  bounded, least-privilege mechanisms;
- supported products map to multiple agent families through versioned external
  mappings;
- every advertised compatibility claim has containerized regression evidence;
- CI publishes structured results and sanitized ZIP archives; and
- maintainers can identify new agent versions and mapping/validation gaps with
  one utility command; and
- transformer outputs can drive validated, backend-adaptive dashboard bundles
  with explicit coverage and provenance.

The detailed dashboard architecture, agent roles, contracts, validation gates,
and delivery phases are defined in the
[adaptive dashboard generation proposal](adaptive_dashboard_generation.md).

## Open design decisions

- Whether reconciliation belongs in the detector runner, transformer, or a
  separate normalization component.
- Whether canonical source identity should include live filesystem inode data
  or remain stable across file recreation.
- Which deployment policy controls candidate-only log activation.
- Which credential-reference providers are mandatory for the first database
  query runner.
- Whether slow-query SQL text is ever retained, even with explicit opt-in.
- Which MongoDB versions, editions, and topologies define the first support
  boundary.
- Which agent becomes the first post-Fluent-Bit/Collector adapter.
- Which CI artifact store and retention periods apply to regression evidence.
- Whether the version-audit utility only reports gaps or can also prepare local
  mapping skeletons without external side effects.
