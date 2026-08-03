#!/usr/bin/env bash
# Deploy the HSTS middleware to the Coolify control-plane Traefik (IONOS box).
#
# Byline: Claude Code . Opus 5 (1M) . 2026-08-02
#
#   scripts/deploy_coolify_hsts.sh stage    # copy the middleware file only (no effect yet)
#   scripts/deploy_coolify_hsts.sh verify   # is the file loaded / is the header live?
#   scripts/deploy_coolify_hsts.sh attach   # wire it to the https entrypoint (no effect yet)
#   scripts/deploy_coolify_hsts.sh restart  # apply it; auto-rolls-back if unhealthy
#   scripts/deploy_coolify_hsts.sh maxage N # change stsSeconds to N and hot-reload
#   scripts/deploy_coolify_hsts.sh rollback # remove the file + the entrypoint arg
#
# STAGE IS SAFE: the middleware is attached to nothing until `attach`, so a
# malformed file cannot affect routing. Verify between the two steps -- a bad
# entrypoint arg stops Traefik from starting, which takes the whole control
# plane down until someone SSHes in.
#
# The host path /data/coolify/proxy is root-only and sudo is password-gated on
# this box, so every write goes through `docker exec coolify-proxy`, which has
# the directory bind-mounted at /traefik and runs as root.
set -euo pipefail

HOST="${COOLIFY_SSH_HOST:-ionos-ts}"
FQDN="${COOLIFY_FQDN:-coolify.mitechconsult.com}"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/docker/coolify-proxy/dynamic/hsts.yaml"
DST="/traefik/dynamic/hsts.yaml"
COMPOSE="/traefik/docker-compose.yml"
ARG="--entrypoints.https.http.middlewares=hsts@file"

ssh_do() { ssh -o ConnectTimeout=10 -o BatchMode=yes "$HOST" "$@"; }

stage() {
  [[ -f "$SRC" ]] || { echo "missing $SRC" >&2; exit 1; }
  echo "staging $SRC -> $HOST:$DST"
  base64 -w0 < "$SRC" | ssh_do "base64 -d | docker exec -i coolify-proxy sh -c 'cat > $DST'"
  ssh_do "docker exec coolify-proxy sh -c 'ls -l $DST && tail -6 $DST'"
  echo
  echo "staged. Attached to nothing yet -- run 'verify' then 'attach'."
}

verify() {
  echo "=== traefik errors since staging (empty is good) ==="
  ssh_do "docker logs coolify-proxy --since 3m 2>&1 | grep -iE 'error|hsts|middleware' | tail -10" || true
  echo
  echo "=== file present in container ==="
  ssh_do "docker exec coolify-proxy sh -c 'test -f $DST && echo yes || echo NO'"
  echo
  echo "=== entrypoint arg wired? ==="
  ssh_do "docker inspect coolify-proxy --format '{{json .Config.Cmd}}' | grep -q 'middlewares=hsts@file' && echo yes || echo 'no (run attach)'"
  echo
  echo "=== live header on https://$FQDN ==="
  curl -sI --max-time 20 "https://$FQDN/login" | grep -i 'strict-transport-security' \
    || echo "  (no Strict-Transport-Security yet)"
}

attach() {
  # Fetch, edit HERE, push the whole file back. In-container sed/awk needs the
  # replacement escaped through ssh -> docker exec -> sh -> sed, four quoting
  # layers deep, on the file that decides whether the control plane's proxy
  # starts at all. Not worth it.
  local tmp="${TMPDIR:-/tmp}/coolify-proxy-compose.$$"
  ssh_do "docker exec coolify-proxy cat $COMPOSE" > "$tmp"
  [[ -s "$tmp" ]] || { echo "could not read $COMPOSE" >&2; rm -f "$tmp"; exit 1; }

  if grep -q 'hsts@file' "$tmp"; then
    echo "already attached"; rm -f "$tmp"; return 0
  fi

  python3 - "$tmp" "$ARG" <<'PY'
import sys
path, arg = sys.argv[1], sys.argv[2]
lines = open(path, encoding="utf-8").read().splitlines(keepends=True)
out, done = [], False
for line in lines:
    out.append(line)
    if not done and "--entrypoints.https.address=:443" in line:
        indent = line[: len(line) - len(line.lstrip())]
        out.append(f"{indent}- '{arg}'\n")
        done = True
if not done:
    sys.exit("anchor '--entrypoints.https.address=:443' not found; aborting")
open(path, "w", encoding="utf-8", newline="").writelines(out)
print("inserted after the https entrypoint definition")
PY

  echo "backing up on the box, then writing the modified compose"
  ssh_do "docker exec coolify-proxy sh -c 'cp $COMPOSE ${COMPOSE}.bak-hsts'"
  base64 -w0 < "$tmp" | ssh_do "base64 -d | docker exec -i coolify-proxy sh -c 'cat > $COMPOSE'"
  rm -f "$tmp"
  ssh_do "docker exec coolify-proxy grep -n 'hsts@file' $COMPOSE"
  echo
  echo "compose updated. Nothing has changed yet -- args apply on restart:"
  echo "    $0 restart"
}

#: Compose identity, read off the running container's labels.
PROJECT="coolify-proxy"
PROJDIR="/data/coolify/proxy"

# `docker restart` does NOT apply a command-arg change: args are baked into the
# container at CREATION, so a restart re-runs the old config and reports
# healthy while changing nothing. Same shape as Coolify's env-var trap (values
# are rendered into the container at deploy; editing them does not reach a
# running container). The container has to be RECREATED.
#
# $PROJDIR is root-only and sudo is password-gated on this box, so the compose
# file is streamed out of the container and fed to `docker compose -f -`.
recreate() {
  echo "recreating coolify-proxy from its compose (args apply at creation) ..."
  # --env-file /dev/null: compose otherwise stats $PROJDIR/.env, which is
  # root-only here, and fails the whole run with "permission denied" while
  # leaving the old container up (so it silently does nothing). All volume
  # paths in this compose are absolute, so no .env is needed.
  ssh_do "docker exec coolify-proxy cat $COMPOSE | docker compose -p $PROJECT --project-directory $PROJDIR --env-file /dev/null -f - up -d --force-recreate 2>&1 | tail -5"
  _await_healthy_or_rollback
}

restart() {
  # A bad arg stops Traefik booting, which takes every HTTPS route on this box
  # with it -- including the dashboard needed to fix it. So: restart, poll for
  # health, and put the backup back automatically if it does not recover.
  echo "restarting coolify-proxy ..."
  ssh_do "docker restart coolify-proxy >/dev/null 2>&1"
  _await_healthy_or_rollback
}

_await_healthy_or_rollback() {
  local ok=""
  for i in $(seq 1 15); do
    sleep 2
    if ssh_do "docker inspect coolify-proxy --format '{{.State.Health.Status}}' 2>/dev/null" | grep -q healthy; then
      ok=yes; break
    fi
  done

  if [[ -z "$ok" ]]; then
    echo "PROXY DID NOT COME BACK HEALTHY -- restoring the backup and recreating"
    # Restore via a still-running container if there is one; otherwise the
    # backup lives on the host bind mount and compose can be fed from a
    # throwaway container that mounts the same directory.
    ssh_do "docker exec coolify-proxy sh -c 'cp ${COMPOSE}.bak-hsts $COMPOSE' 2>/dev/null \
      || docker run --rm -v $PROJDIR:/traefik alpine sh -c 'cp /traefik/docker-compose.yml.bak-hsts /traefik/docker-compose.yml'"
    ssh_do "docker run --rm -v $PROJDIR:/t alpine cat /t/docker-compose.yml \
      | docker compose -p $PROJECT --project-directory $PROJDIR -f - up -d --force-recreate >/dev/null 2>&1 || true"
    echo "rolled back. Check: docker logs coolify-proxy --tail 50"
    exit 1
  fi

  echo "proxy healthy."
  local code
  code=$(curl -s -o /dev/null --max-time 20 -w '%{http_code}' "https://$FQDN/login" || echo 000)
  echo "https://$FQDN/login -> $code"
  [[ "$code" == "200" ]] || echo "WARNING: dashboard not returning 200 -- consider '$0 rollback'"
}

maxage() {
  local n="${1:?usage: maxage <seconds>}"
  echo "setting stsSeconds=$n (hot-reloaded, no restart)"
  ssh_do "docker exec coolify-proxy sh -c 'sed -i \"s/stsSeconds: .*/stsSeconds: $n/\" $DST && grep stsSeconds $DST'"
  echo "remember to mirror this in $SRC and commit."
}

rollback() {
  echo "removing middleware file and entrypoint arg"
  ssh_do "docker exec coolify-proxy sh -c '
    rm -f $DST
    if [ -f ${COMPOSE}.bak-hsts ]; then cp ${COMPOSE}.bak-hsts $COMPOSE; echo \"compose restored\"; fi'"
  echo "rolled back. Restart the proxy from the Coolify UI if attach had been run."
  echo "NOTE: browsers that already cached HSTS keep enforcing it until max-age expires."
}

case "${1:-}" in
  stage) stage ;;
  verify) verify ;;
  attach) attach ;;
  restart) restart ;;
  recreate) recreate ;;
  maxage) shift; maxage "$@" ;;
  rollback) rollback ;;
  *) sed -n '2,20p' "$0"; exit 1 ;;
esac
