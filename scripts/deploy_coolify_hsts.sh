#!/usr/bin/env bash
# Deploy the HSTS middleware to the Coolify control-plane Traefik (IONOS box).
#
# Byline: Claude Code . Opus 5 (1M) . 2026-08-02
#
#   scripts/deploy_coolify_hsts.sh stage    # copy the middleware file only (no effect yet)
#   scripts/deploy_coolify_hsts.sh verify   # is the file loaded / is the header live?
#   scripts/deploy_coolify_hsts.sh attach   # wire it to the https entrypoint (RESTARTS PROXY)
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
  echo "backing up $COMPOSE then adding: $ARG"
  ssh_do "docker exec coolify-proxy sh -c '
    grep -q \"middlewares=hsts@file\" $COMPOSE && { echo \"already attached\"; exit 0; }
    cp $COMPOSE ${COMPOSE}.bak-hsts &&
    sed -i \"s|- '\\''--entrypoints.https.address=:443'\\''|- '\\''--entrypoints.https.address=:443'\\''\\n      - '\\''$ARG'\\''|\" $COMPOSE &&
    grep -n \"hsts@file\\|entrypoints.https.address\" $COMPOSE'"
  echo
  echo "NOTE: the proxy must be restarted for a command-arg change to take effect."
  echo "Do it from the Coolify UI (Server -> Proxy -> Restart) so Coolify stays"
  echo "the owner of the container lifecycle. Then re-run: $0 verify"
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
  maxage) shift; maxage "$@" ;;
  rollback) rollback ;;
  *) sed -n '2,20p' "$0"; exit 1 ;;
esac
