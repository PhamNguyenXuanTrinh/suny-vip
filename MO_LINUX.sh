#!/usr/bin/env bash
set -eu
sunny_bundle_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$sunny_bundle_dir/app"
exec "$sunny_bundle_dir/runtime/linux/bin/python3.13" -m backend.scripts.desktop "$@"
