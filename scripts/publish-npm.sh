#!/usr/bin/env bash
# Publish the DSH plugin to npm with a token that never touches ~/.npmrc.
#
#   echo 'npm_xxxxxxxx' > .npm-token   # git-ignored
#   scripts/publish-npm.sh
#
# Env:
#   NPM_TOKEN_FILE  token file (default: <repo>/.npm-token)
#   NPM_REGISTRY    registry (default: https://registry.npmjs.org)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOKEN_FILE="${NPM_TOKEN_FILE:-$ROOT/.npm-token}"
REGISTRY="${NPM_REGISTRY:-https://registry.npmjs.org}"

if [ ! -f "$TOKEN_FILE" ]; then
  echo "missing $TOKEN_FILE — write the npm token there first (it is git-ignored)" >&2
  exit 1
fi

TOKEN="$(tr -d '[:space:]' < "$TOKEN_FILE")"
if [ -z "$TOKEN" ]; then
  echo "$TOKEN_FILE is empty" >&2
  exit 1
fi

TMPRC="$(mktemp)"
chmod 600 "$TMPRC"
trap 'rm -f "$TMPRC"' EXIT

cat > "$TMPRC" <<EOF
registry=$REGISTRY
//registry.npmjs.org/:_authToken=$TOKEN
always-auth=true
EOF

export NPM_CONFIG_USERCONFIG="$TMPRC"

echo "registry: $REGISTRY"
npm whoami --registry="$REGISTRY"
npm publish --registry="$REGISTRY" --access public "$@"
npm view dsh-archmap-explorer version --registry="$REGISTRY"
