#!/usr/bin/env bash
# WP-E01 isolated build/smoke test for the pinned Timesketch fork -- Podman
# variant, live-verified on WSL2 Arch + Podman 5.8.3 + podman-compose 1.6.0,
# 2026-08-26. See smoke-test.sh for the Docker original and
# TIMESKETCH-FORK-WP-E01-HANDOFF.md for the full diagnostic trail explaining
# why this variant exists (two host-environment issues found and worked
# around here, neither a defect in the upstream compose file):
#
# 1. Ports 5000/5001/8080/9090 (and 15000) are unavailable to podman's
#    rootlessport on this host for reasons external to this project (a
#    leaked port reservation from another actor sharing this WSL2 mirrored-
#    networking host, most likely Podman Desktop's separate
#    "podman-horizon-swift-mvp" machine) -- confirmed free at the Windows
#    host and WSL kernel socket-table level, yet refused by podman
#    (rootless pasta, rootless slirp4netns, and rootful all three) while an
#    arbitrary port binds instantly. Worked around via
#    docker-compose.podman.yml, a standalone file (not a `-f a -f b` merge --
#    podman-compose concatenates list-type `ports:` instead of replacing
#    them) remapping to a verified-free block: 15005->5000, 15006->5001,
#    18080->8080, 19090->9090.
# 2. The upstream dev image's docker-entrypoint.sh deliberately does NOT
#    start the webserver -- see docker/dev/README.md "Start the Application
#    Services": it installs, configures, creates the dev user, prints
#    "Timesketch development server is ready!", then `sleep infinity`.
#    gunicorn must be started separately (README Option B, background). This
#    applies to the Docker original too, not just Podman -- the original
#    smoke-test.sh's immediate `curl` after `up -d --wait` would 000/reset
#    on real Docker as well. Added here as an explicit exec step.
#
# Self-contained: own timesketch-network, own Postgres/OpenSearch/Redis,
# ports bound to 127.0.0.1 only. Does not touch the platform's shared
# `deploy/compose.yaml` or any Coolify app.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

WEB_PORT="${WP_E01_WEB_PORT:-15005}"

echo "== bring up the isolated stack (podman-compose, port-remapped compose file) =="
podman-compose -f docker-compose.podman.yml up -d

echo "== wait for dependency healthchecks =="
for svc in opensearch postgres redis; do
  for _ in $(seq 1 30); do
    status=$(podman inspect --format '{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "unknown")
    [ "$status" = "healthy" ] && break
    sleep 2
  done
  echo "$svc: $status"
  [ "$status" = "healthy" ] || { echo "FAILED: $svc did not become healthy"; exit 1; }
done

echo "== containers up =="
podman-compose -f docker-compose.podman.yml ps

echo "== wait for entrypoint readiness banner (editable pip install + config + dev-user creation) =="
for _ in $(seq 1 60); do
  podman logs timesketch-dev 2>&1 | grep -q "Timesketch development server is ready" && break
  sleep 2
done
podman logs timesketch-dev 2>&1 | grep -q "Timesketch development server is ready" \
  || { echo "FAILED: entrypoint never reached ready banner"; exit 1; }

echo "== start the dev webserver (not auto-started by design -- see docker/dev/README.md) =="
podman exec -d timesketch-dev gunicorn --reload -b 0.0.0.0:5000 --log-file - --timeout 120 timesketch.wsgi:application

echo "== web UI reachable (remapped host port, poll up to 60s for gunicorn to bind) =="
code=""
for _ in $(seq 1 30); do
  code=$(curl -fsS -o /dev/null -w "%{http_code}" "http://127.0.0.1:${WEB_PORT}/" 2>/dev/null || echo "")
  [ -n "$code" ] && break
  sleep 2
done
echo "HTTP ${code:-000}"
[ -n "$code" ] || { echo "FAILED: web UI never responded"; exit 1; }

echo "== OpenSearch reachable from inside the app container =="
podman exec timesketch-dev curl -fsS "http://opensearch:9200/_cluster/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print('status:', d['status'])"

echo "== disable-not-delete seam verified: upstream DFIR analyzers NOT registered by default =="
podman exec timesketch-dev python3 -c "
from timesketch.lib import analyzers
from timesketch.lib.analyzers import manager
assert analyzers._ENABLE_UPSTREAM_ANALYZERS is False, 'flag should default off'
names = list(manager.AnalysisManager._class_registry.keys())
assert 'domain' not in names, f'domain analyzer should be disabled, got: {names}'
assert 'sigma' not in names, f'sigma_tagger (registry key sigma) should be disabled, got: {names}'
print('OK: 0 upstream analyzers registered by default, flag =', analyzers._ENABLE_UPSTREAM_ANALYZERS)
"

echo "== re-enable flag actually restores the upstream set (proves the seam is reversible, not a deletion) =="
podman exec -e TIMESKETCH_FORK_ENABLE_UPSTREAM_ANALYZERS=1 timesketch-dev python3 -c "
import importlib
import timesketch.lib.analyzers as analyzers
importlib.reload(analyzers)
from timesketch.lib.analyzers import manager
names = list(manager.AnalysisManager._class_registry.keys())
assert 'domain' in names, f'domain analyzer should be restored, got: {names}'
assert 'sigma' in names, f'sigma_tagger (registry key sigma) should be restored, got: {names}'
print('OK: upstream analyzer set restores when flag=1, count =', len(names))
"

echo "== tear down (isolated stack only: containers, network, volumes) =="
podman-compose -f docker-compose.podman.yml down -v
podman volume ls -q | xargs -r podman volume rm >/dev/null 2>&1 || true

echo "SMOKE TEST PASSED (podman variant)"
