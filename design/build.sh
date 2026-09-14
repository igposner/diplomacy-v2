#!/usr/bin/env bash
# Regenerate every artboard, then seed the publishable canvas.
set -euo pipefail
cd "$(dirname "$0")"
for g in gen_main gen_lang gen_states gen3; do python3 "tools/$g.py"; done
echo "artboards rebuilt. seed with the design skill's seed-canvas.mjs"
