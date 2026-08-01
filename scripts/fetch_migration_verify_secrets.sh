#!/usr/bin/env bash
# Fetches the two credentials verify_neo4j_milvus_migration.py needs and
# writes them to an env-file the caller sources — never printed to the
# transcript. Read-only against both Coolify (env values) and the local
# secrets store; makes no infrastructure changes.
#
# Byline: Claude Code · Sonnet (agent) · 2026-08-01
#
# Usage:
#   COOLIFY_API_TOKEN=... bash scripts/fetch_migration_verify_secrets.sh <out_env_file>
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./migration_lib.sh
source "$HERE/migration_lib.sh"

OUT="${1:?usage: fetch_migration_verify_secrets.sh <out_env_file>}"
OVHDATA_UUID_NEO4J=jfvnf0i45mmccxonv1p570au

neo4j_pw=$(cf_get_env_value "$OVHDATA_UUID_NEO4J" NEO4J_PASSWORD)

milvus_token=$(python3 -c "
import re
text = open(r'$HOME/.secrets/memsearch.env').read()
m = re.search(r'MEMSEARCH_MILVUS_TOKEN\s*=\s*(.+?)\s*$', text, re.M)
print(m.group(1) if m else '')
")

{
  printf 'export NEO4J_PASSWORD=%q\n' "$neo4j_pw"
  printf 'export MEMSEARCH_MILVUS_TOKEN=%q\n' "$milvus_token"
} > "$OUT"

echo "wrote $OUT (neo4j_pw_len=${#neo4j_pw} milvus_token_len=${#milvus_token})"
