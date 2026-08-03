#!/usr/bin/env bash
# Change the ContextForge platform-admin password via the email-auth API.
# Runs ON the gateway host (OVH-1). The OLD password is read from the running
# container's PLATFORM_ADMIN_PASSWORD env; the NEW password arrives on stdin
# (line 1) so no secret ever appears on a command line or in shell history.
#
# Usage:  printf '%s' "$NEW_PW" | bash cf_change_admin_password.sh
# After success: update the Coolify stored env CF_ADMIN_PASSWORD to the new
# value (bootstrap env is only consulted on an EMPTY user table, but stored-env
# parity is mandatory — "everything persists, always", owner rule 2026-07-19).
#
# Byline: Claude Code · Fable 5 · 2026-08-03
set -euo pipefail

BASE="http://100.72.169.40:4444"
EMAIL="admin@mitechconsult.com"

NEW_PW=$(head -1)
[ -n "$NEW_PW" ] || { echo "no new password on stdin" >&2; exit 1; }

C=$(docker ps --filter name=contextforge --format '{{.Names}}' | head -1)
OLD_PW=$(docker exec "$C" printenv PLATFORM_ADMIN_PASSWORD)

# 1. login with the current password
TOK=$(printf '{"email":"%s","password":"%s"}' "$EMAIL" "$OLD_PW" \
  | curl -sf -X POST "$BASE/auth/email/login" -H 'Content-Type: application/json' -d @- \
  | python3 -c 'import json,sys;print(json.load(sys.stdin)["access_token"])')
echo "login: ok"

# 2. discover the change-password path from the live OpenAPI spec
CHANGE_PATH=$(curl -sf -H "Authorization: Bearer $TOK" "$BASE/openapi.json" \
  | python3 -c 'import json,sys
d=json.load(sys.stdin)
cands=[p for p in d["paths"] if "password" in p.lower()]
print(cands[0] if cands else "")
print("all-candidates:", cands, file=sys.stderr)')
[ -n "$CHANGE_PATH" ] || { echo "no password endpoint found in OpenAPI" >&2; exit 1; }
echo "endpoint: $CHANGE_PATH"

# 3. change the password
printf '{"old_password":"%s","new_password":"%s"}' "$OLD_PW" "$NEW_PW" \
  | curl -s -X POST "$BASE$CHANGE_PATH" -H "Authorization: Bearer $TOK" \
      -H 'Content-Type: application/json' -d @- -w '\nchange HTTP %{http_code}\n'

# 4. verify: login with the NEW password
printf '{"email":"%s","password":"%s"}' "$EMAIL" "$NEW_PW" \
  | curl -s -X POST "$BASE/auth/email/login" -H 'Content-Type: application/json' -d @- \
      -o /dev/null -w 'verify-new-login HTTP %{http_code}\n'
