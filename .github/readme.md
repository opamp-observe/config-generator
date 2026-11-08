<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
-->

# GitHub automation

The workflows in this directory run on GitHub-hosted runners. Change detection and job
conditions are evaluated within GitHub Actions before an eligible job starts. They are not
evaluated by a cloud deployment platform.

## Configuration generator workflow

The `workflows/main_config-generator.yml` workflow validates every pull request and every push
to `main`. Its `validate` job uses `dorny/paths-filter` to report whether the workflow run contains
deployment-relevant changes.

The `deployment-smoke-test` job runs only when at least one changed file is not documentation.
Changes under `docs/` and changes to Markdown files are treated as documentation-only changes.
The job is marked as skipped for documentation-only changes, while the validation job still runs
and reports its result.

A manual `workflow_dispatch` run always executes the deployment smoke test, regardless of change
detection. This makes it possible to request the complete regression test when investigating a
documentation-only commit or rerunning an earlier revision.

The deployment smoke test is also local to the GitHub-hosted runner. It builds and runs a
disposable Docker regression environment; it does not deploy resources to an external cloud
platform.
