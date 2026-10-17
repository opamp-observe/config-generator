# Copyright 2026 opamp.info
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# http://www.apache.org/licenses/LICENSE-2.0

"""Run the configuration transformer as a Python module."""

from config_template_transformer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
