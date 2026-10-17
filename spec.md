# Universal Observability Agent Installer

## Overview
This Python utility interactively or non-interactively evaluates whether an observability
agent artifact can be installed on a host. When the metadata supports that host, it downloads,
verifies, and unpacks the artifact into a caller-selected directory.

The agents currently supported by this tool are:
- Fluent Bit
- Fluentd
- Vector
- OpenTelemetry
- Telegraf
- Elastic Agent (Open Source)
- Elastic Beats (represented by Filebeat in the initial catalog)

The installation request includes an agent and may include an exact version. When no version is
provided, the catalog's `latest` value is used. "Latest" deliberately means latest known to the
local catalog; the installer does not query release APIs at runtime.

The default installation target is the current working directory, not the application source
directory. `--target` overrides it. Archive contents are placed directly in that directory.

For container builds, the agent, version, operating system, architecture, metadata path, and target
can all be supplied on the command line. These parameters are documented in `docs/cli.md`.

## Scope decisions

- The first release retrieves and unpacks artifacts but does not register system services, start
  agents, or invoke OS package managers. A raw MSI is therefore downloaded but not executed.
- Fluentd's vendor distribution is packaged differently from standalone archives; the initial
  catalog exposes its Windows MSI as a raw artifact.
- Filebeat is the initial concrete Elastic Beats selection. Other Beats can be added as distinct
  catalog keys without changing application code.
- Supported archive types are `raw`, `tar.gz`, and `zip`.
- Only regular files are extracted. Absolute paths and parent-directory traversal are rejected.
- SHA-256 is checked when `sha256` is present in metadata. It is optional so upstream artifacts
  without a stable published digest remain usable, but production catalog updates should include it.
- The application never elevates privileges. The target must be writable by the current user.
- Package setup commands exist only for disposable catalog-validation containers. The normal
  installer still never runs downloaded installers or elevates privileges.
- `--dry-run` validates metadata, platform selection, and prerequisites without creating the target
  or using the network.


## Deployment Process
Each find and action performed will be logged in a user, reader friendly manner. For example the details of the OS being used.
The following steps need to be performed:
- Confirm that the metadata file is valid against its bundled JSON Schema. Stop on failure.
- Determine and normalize the OS and processor architecture (the installation footprint).
- Select the requested version and matching platform artifact.
- Evaluate configured command prerequisites, caching each result for the process lifetime.
- Confirm that the target directory can be created and used.
- Download into an isolated temporary directory and validate the optional SHA-256 digest.
- Safely copy or extract files into the target and confirm the declared executable exists.

Prerequisite installation is intentionally deferred: silently invoking package managers would
require privilege and policy decisions that are inappropriate for a portable first release.


## Prereq checker
The prerequisite checker performs command-availability and target checks. Command results are
binary values cached by command name, then reported together if anything is missing. Target
failures retain the operating-system error as their reason.


## Metadata needed
A versioned JSON catalog provides:

- stable agent key and display name;
- latest known and explicitly available versions;
- operating-system and architecture mappings;
- URL templates using `{version}`, `{os}`, and `{arch}` placeholders;
- archive type, expected executable, optional raw install name, and strip count;
- optional SHA-256 digest and agent-level command prerequisites.
- reusable agent-level version defaults and operating-system-level artifact defaults;
- per-version variables, including regex-safe expansion, for differing package versions;
- three installable releases per agent, preferring explicit upstream LTS releases when available.

The schema is packaged with the application. Unknown fields are rejected to catch mistakes early.
Both the inheritance-aware source catalog and its fully resolved artifacts are schema validated.
Every schema attribute includes a description suitable for editor assistance and generated
metadata reference documentation.

## Testing
Unit tests cover metadata validation and selection, normalization, prerequisite caching, download
integrity, archive safety, extraction, and CLI behavior. System tests run the installed CLI against
a local HTTP server, perform a complete download and extraction into a fresh directory, and execute
the installed fixture agent to validate its version. This keeps CI deterministic and offline.

Live upstream smoke tests are operational checks rather than deterministic automated tests. The
procedure in `docs/testing.md` describes how to test catalog entries in disposable containers.

## Acceptance criteria

- The package installs into a Python 3.10+ virtual environment and exposes `obs-agent-installer`.
- Default logging is DEBUG and describes platform selection, download, and final executable path.
- Invalid or unavailable metadata exits non-zero before download.
- Supported platform archives install without writing outside the requested target.
- Expected failures are concise and do not emit Python tracebacks from the CLI.
- Unit and system test suites pass, along with Ruff and Pylint checks.
- Linux and Windows container definitions exercise every catalog version available for their
  platform in an isolated target and emit JSON and Markdown pass/fail reports.
