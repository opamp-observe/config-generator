<!--
Copyright 2026 opamp.info
Licensed under the Apache License, Version 2.0.
-->

# Detector result schemas

The schemas use JSON Schema Draft 2020-12. Each file in `detectors/`
validates the result object emitted for one detector. The
[`detector_results.schema.json`](detector_results.schema.json) master schema
validates the aggregate document written by `runner.py` and references every
detector schema.

A detected result must contain every query defined by that detector's Linux and
Windows packs. Query arrays may be empty when osquery finds no matching rows or
when a query reports an error. An undetected result may have an empty `queries`
object unless the runner was invoked with `--include-undetected`.

Validate an aggregate output with a Draft 2020-12-compatible validator. For
example, from the repository root with the Python `jsonschema` package:

```powershell
py -3 -m jsonschema -i detector-results.json schemas/detector_results.schema.json
```

The repository validation command also checks that manifest schema references,
schema identities, and declared query names remain synchronized:

```powershell
.\tests\run_validation.ps1
```
