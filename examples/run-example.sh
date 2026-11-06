#!/bin/sh
# Run the checker over the example files and show the result.
# The checker exits 1 (three files fail), so the script keeps going
# and exits 0 either way.
set -e
cd "$(dirname "$0")/.."
python3 src/heading_order_checker.py examples/good.html examples/good.md examples/skipped-level.html examples/two-h1.md examples/no-h1.html || true
