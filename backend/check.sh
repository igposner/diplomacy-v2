#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "--- DATC rules gate (160 cases) ---"
./venv/bin/python -m pytest --pyargs diplomacy.tests.test_datc -q | tail -1
echo "--- map build (7 silent traps asserted) ---"
./venv/bin/python scripts/build_map.py
echo "--- full game, 7 scripted bots ---"
./venv/bin/python tests/test_smoke.py
