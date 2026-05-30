#!/usr/bin/env bash
# Compile all .po translation files to .mo binary files.
# Run from the repository root.
set -euo pipefail

echo "Compiling translations..."
pybabel compile -d translations --statistics
echo "Done."
