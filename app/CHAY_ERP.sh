#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [ ! -x .venv/bin/python ]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m backend.scripts.setup_local
exec .venv/bin/python -m backend.scripts.run_server
