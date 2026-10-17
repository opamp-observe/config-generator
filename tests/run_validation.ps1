# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

[CmdletBinding()]
param([string]$OsqueryPath = "osqueryi")

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$validationScript = Join-Path $PSScriptRoot "validate_detectors.py"

# Keep launcher arguments explicit because PowerShell does not splat a positional
# prefix array consistently across Windows PowerShell and PowerShell 7.
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 -m unittest discover -s $PSScriptRoot -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & py -3 $validationScript --osquery $OsqueryPath
} else {
    & python -m unittest discover -s $PSScriptRoot -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & python $validationScript --osquery $OsqueryPath
}
exit $LASTEXITCODE

