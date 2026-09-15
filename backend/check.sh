#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "--- DATC rules gate (160 cases) ---"
./venv/bin/python -m pytest --pyargs diplomacy.tests.test_datc -q | tail -1
echo "--- map build (7 silent traps asserted) ---"
./venv/bin/python scripts/build_map.py
echo "--- full game, 7 scripted bots ---"
./venv/bin/python tests/test_smoke.py
echo "--- persistence across restarts ---"
./venv/bin/python tests/test_persistence.py
echo "--- solo victory ends the game ---"
./venv/bin/python tests/test_victory.py
echo "--- promise-keeping: the six scoring rules and the chart ---"
./venv/bin/python tests/test_commitments.py | grep passed
echo "--- promise-keeping: recorded through the real resolve path ---"
./venv/bin/python tests/test_research_record.py | tail -1
