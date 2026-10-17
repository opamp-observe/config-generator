# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

[CmdletBinding()]
param(
    [string]$OutputPath = "",
    [string]$OsqueryPath = "",
    [string[]]$Detector = @(),
    [switch]$IncludeUndetected
)

# Resolve repository-relative paths without depending on the caller's directory.
$repositoryRoot = Split-Path -Parent $PSScriptRoot
if (-not $OutputPath) {
    $OutputPath = Join-Path $repositoryRoot "detector-results.json"
}

$runnerArguments = @((Join-Path $repositoryRoot "runner.py"), "--output", $OutputPath)
if ($OsqueryPath) {
    $runnerArguments += @("--osquery", $OsqueryPath)
}
foreach ($detectorName in $Detector) {
    $runnerArguments += @("--detector", $detectorName)
}
if ($IncludeUndetected) {
    $runnerArguments += "--include-undetected"
}

# Prefer the Windows launcher, falling back to a directly installed Python.
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 @runnerArguments
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python @runnerArguments
} else {
    throw "Python 3 was not found. Install Python or add it to PATH."
}
exit $LASTEXITCODE

