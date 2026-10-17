@echo off
rem Copyright 2026 opamp.info
rem Licensed under the Apache License, Version 2.0 (the "License");
rem you may not use this file except in compliance with the License.

setlocal
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 -m unittest discover -s "%~dp0" -p "test_*.py"
  if errorlevel 1 exit /b %ERRORLEVEL%
  py -3 "%~dp0validate_detectors.py" %*
  exit /b %ERRORLEVEL%
)
python -m unittest discover -s "%~dp0" -p "test_*.py"
if errorlevel 1 exit /b %ERRORLEVEL%
python "%~dp0validate_detectors.py" %*
exit /b %ERRORLEVEL%

