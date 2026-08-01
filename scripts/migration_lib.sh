#!/usr/bin/env bash
# Shared Coolify control-plane helpers for the ovh-data -> ovh-files migration
# scripts (phase1b_coldcopy.sh, phase2_standup.sh). Sourced, never executed
# directly.
#
# Byline: Claude Code · Sonnet (agent) · 2026-08-01
#
# Requires COOLIFY_API_TOKEN in the environment. The caller parses it out of
# ~/.secrets/coolify-ionos-api.env with a tolerant regex — NEVER `source` that
# file (its `KEY = value` spacing makes a naive `source` execute the value as
# a command; see repo CLAUDE.md). The token is never printed by this file.
#
#   export COOLIFY_API_TOKEN="$(python3 -c "
#   import re
#   text = open(r'$HOME/.secrets/coolify-ionos-api.env').read()
#   m = re.search(r'(?:COOLIFY_API_TOKEN|COOLIFY_TOKEN|API_TOKEN)\s*[=:]\s*[\"\']?([A-Za-z0-9|_\-.]{20,})', text)
#   print(m.group(1))
#   ")"

COOLIFY_API="${COOLIFY_API:-http://100.98.98.38:8000/api/v1}"

_cf_auth_header() {
  : "${COOLIFY_API_TOKEN:?COOLIFY_API_TOKEN not set — see header of migration_lib.sh}"
  echo "Authorization: Bearer ${COOLIFY_API_TOKEN}"
}

# cf_status <uuid> — prints the app's current "status" field (e.g.
# "running:healthy", "exited:unhealthy"). Never assume the exact suffix.
cf_status() {
  curl -s -H "$(_cf_auth_header)" "$COOLIFY_API/applications/$1" \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('status','?'))"
}

cf_stop() {
  echo "  Coolify: POST /applications/$1/stop"
  curl -s -H "$(_cf_auth_header)" "$COOLIFY_API/applications/$1/stop" >/dev/null
}

cf_start() {
  echo "  Coolify: POST /applications/$1/start"
  curl -s -H "$(_cf_auth_header)" "$COOLIFY_API/applications/$1/start" >/dev/null
}

# cf_wait_not_running <uuid> [timeout_s] — polls until status no longer starts
# with "running" (i.e. genuinely stopped), or times out.
cf_wait_not_running() {
  local uuid="$1" timeout="${2:-120}" waited=0 st
  while true; do
    st=$(cf_status "$uuid")
    echo "    [${waited}s] status=$st"
    case "$st" in running*) ;; *) echo "    stopped."; return 0 ;; esac
    [ "$waited" -ge "$timeout" ] && { echo "    TIMEOUT waiting for stop (last=$st)"; return 1; }
    sleep 5; waited=$((waited + 5))
  done
}

# cf_wait_running <uuid> [timeout_s] — polls until status starts with
# "running", or times out.
cf_wait_running() {
  local uuid="$1" timeout="${2:-240}" waited=0 st
  while true; do
    st=$(cf_status "$uuid")
    echo "    [${waited}s] status=$st"
    case "$st" in running*) echo "    running."; return 0 ;; esac
    [ "$waited" -ge "$timeout" ] && { echo "    TIMEOUT waiting for running (last=$st)"; return 1; }
    sleep 5; waited=$((waited + 5))
  done
}

# cf_create_dockercompose_app <project_uuid> <server_uuid> <env_name> \
#     <github_app_uuid> <git_repo> <git_branch> <compose_location> <name>
# Prints the created app's uuid on success (POST /applications/private-github-app,
# the only creation route that works on this Coolify 4.1.2 instance — plain
# POST /applications 404s, per repo CLAUDE.md).
cf_create_dockercompose_app() {
  local project_uuid="$1" server_uuid="$2" env_name="$3" github_app_uuid="$4" \
        git_repo="$5" git_branch="$6" compose_location="$7" name="$8"
  curl -s -H "$(_cf_auth_header)" -H "Content-Type: application/json" \
    -X POST "$COOLIFY_API/applications/private-github-app" \
    -d "$(python3 -c "
import json
print(json.dumps({
  'project_uuid': '$project_uuid',
  'server_uuid': '$server_uuid',
  'environment_name': '$env_name',
  'github_app_uuid': '$github_app_uuid',
  'git_repository': '$git_repo',
  'git_branch': '$git_branch',
  'build_pack': 'dockercompose',
  'docker_compose_location': '$compose_location',
  'name': '$name',
  'instant_deploy': False,
}))
")"
}

# cf_get_env_value <uuid> <key> — prints one env's raw value (needs a token
# scoped read:sensitive). Caller must NOT echo the result to the transcript;
# pass it straight into another command / variable.
cf_get_env_value() {
  local uuid="$1" key="$2"
  curl -s -H "$(_cf_auth_header)" "$COOLIFY_API/applications/$uuid/envs" \
    | python3 -c "
import json, sys
data = json.load(sys.stdin)
for e in data:
    if e.get('key') == '$key':
        print(e.get('value') or '')
        break
"
}

# cf_upsert_envs <uuid> <key1>=<val1> [key2=val2 ...]
cf_upsert_envs() {
  local uuid="$1"; shift
  local payload
  payload=$(python3 -c "
import json, sys
data = []
for kv in sys.argv[1:]:
    k, _, v = kv.partition('=')
    data.append({'key': k, 'value': v, 'is_preview': False})
print(json.dumps({'data': data}))
" "$@")
  curl -s -H "$(_cf_auth_header)" -H "Content-Type: application/json" \
    -X PATCH "$COOLIFY_API/applications/$uuid/envs/bulk" -d "$payload"
}

# Byline: Claude Code · Sonnet (agent) · 2026-08-01
