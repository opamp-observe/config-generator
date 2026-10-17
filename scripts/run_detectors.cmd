@echo off
rem Copyright 2026 opamp.info
rem Licensed under the Apache License, Version 2.0 (the "License");
rem you may not use this file except in compliance with the License.

setlocal
set "REPOSITORY_ROOT=%~dp0.."
if defined DETECTOR_OUTPUT_PATH (
  set "OUTPUT_PATH=%DETECTOR_OUTPUT_PATH%"
) else (
  set "OUTPUT_PATH=%REPOSITORY_ROOT%\detector-results.json"
)

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 "%REPOSITORY_ROOT%\runner.py" --output "%OUTPUT_PATH%" %*
  exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python "%REPOSITORY_ROOT%\runner.py" --output "%OUTPUT_PATH%" %*
  exit /b %ERRORLEVEL%
)

echo Python 3 was not found. Install Python or add it to PATH. 1>&2
exit /b 1

