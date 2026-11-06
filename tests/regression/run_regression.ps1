# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

[CmdletBinding()]
param(
    [string]$OutputDirectory = "build/regression-artifacts"
)

$repositoryRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot "../..")).Path
$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $repositoryRoot $OutputDirectory))
New-Item -ItemType Directory -Force -Path $resolvedOutput | Out-Null

$buildArguments = @(
    "build",
    "--file",
    (Join-Path $PSScriptRoot "Dockerfile"),
    "--tag",
    "opamp-nginx-postgresql-regression:test",
    $repositoryRoot
)
& docker @buildArguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$runArguments = @(
    "run",
    "--rm",
    "--cap-add",
    "SYS_PTRACE",
    "--security-opt",
    "seccomp=unconfined",
    "--volume",
    "${resolvedOutput}:/artifacts",
    "opamp-nginx-postgresql-regression:test"
)
& docker @runArguments
exit $LASTEXITCODE
