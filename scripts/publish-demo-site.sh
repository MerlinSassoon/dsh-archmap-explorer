#!/usr/bin/env bash
# Publish the generated demo site to the gh-pages branch (the branch is fully
# generated, so the push is forced). Build first:
#
#   scripts/build-demo-site.sh
#   scripts/publish-demo-site.sh
#
# Env:
#   DEMO_REMOTE  git remote to push to (default: origin)
#   DRY_RUN=1    build the commit locally and skip the push
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${1:-$ROOT/.demo-site}"
REMOTE="${DEMO_REMOTE:-origin}"

if [ ! -f "$SITE/index.html" ]; then
  echo "missing $SITE/index.html — run scripts/build-demo-site.sh first" >&2
  exit 1
fi

URL="$(git -C "$ROOT" remote get-url "$REMOTE")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cd "$TMP"
git init -q -b gh-pages
cp -r "$SITE"/. .
git add -A
git -c user.name="${GIT_AUTHOR_NAME:-dsh-archmap}" \
    -c user.email="${GIT_AUTHOR_EMAIL:-noreply@users.noreply.github.com}" \
    commit -q -m "site: publish demo build ($(date -u +%Y-%m-%dT%H:%MZ))"

echo "prepared $(git rev-parse --short HEAD) with $(find . -name '*.html' | wc -l) html files"

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo "DRY_RUN=1: skipping push to $URL"
  exit 0
fi

git remote add origin "$URL"
git push -f origin gh-pages
echo "pushed gh-pages to $URL"
echo "enable Pages once: Settings → Pages → Source: Deploy from a branch → gh-pages / (root)"
