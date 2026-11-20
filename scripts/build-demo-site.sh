#!/usr/bin/env bash
# Build the static demo site: one self-contained HTML per sample project plus a
# hand-written landing page. Output goes to .demo-site/ (git-ignored) by default;
# pass a directory to override it.
#
#   scripts/build-demo-site.sh [OUT_DIR]
#
# Requires python3 3.10+ and the ArchMap package in this repository.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/.demo-site}"
PYTHON="${ARCHMAP_PYTHON:-python3}"

rm -rf "$OUT"
mkdir -p "$OUT/d1" "$OUT/d2" "$OUT/d3"

export PYTHONPATH="$ROOT"

echo "building d1/taskboard"
"$PYTHON" -m archmap build "$ROOT/examples/taskboard" \
  --annotations "$ROOT/examples/taskboard/annotations.json" \
  --out "$OUT/d1" >/dev/null

echo "building d2/student_system"
"$PYTHON" -m archmap build "$ROOT/examples/student_system" --out "$OUT/d2" >/dev/null

echo "building d3/self"
"$PYTHON" -m archmap build "$ROOT" \
  --config "$ROOT/examples/archmap_v3.archmap.json" \
  --out "$OUT/d3" >/dev/null

# The site only ships the self-contained HTML; JSON bundles are build outputs.
rm -f "$OUT"/d*/architecture.json
cp "$ROOT/demo-site/index.html" "$OUT/index.html"

echo "site written to $OUT"
du -sh "$OUT"
