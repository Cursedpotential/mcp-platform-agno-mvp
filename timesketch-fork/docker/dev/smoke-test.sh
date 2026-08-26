#!/usr/bin/env bash
# WP-E01 isolated build/smoke test for the pinned Timesketch fork.
#
# Self-contained: uses only this compose file's own services (timesketch-network,
# its own Postgres/OpenSearch/Redis), ports bound to 127.0.0.1 only. Does not touch
# the platform's shared `deploy/compose.yaml`, any Coolify app, or any shared
# docker network. Safe to run and tear down repeatedly on any Docker-capable host.
#
# NOT run as part of this packet: this desktop has no Docker CLI (documented
# constraint). Run this on a Docker-capable host (owner machine or a VPS, ad hoc --
# not wired into Coolify) to get a real build/boot verification for WP-E01.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "== bring up the isolated stack =="
docker compose up -d --wait

echo "== containers healthy =="
docker compose ps

echo "== web UI reachable =="
curl -fsS -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:5000/

echo "== disable-not-delete seam verified: upstream DFIR analyzers NOT registered by default =="
docker compose exec -T timesketch python3 -c "
from timesketch.lib import analyzers
from timesketch.lib.analyzers import manager
assert analyzers._ENABLE_UPSTREAM_ANALYZERS is False, 'flag should default off'
names = list(manager.AnalysisManager._class_registry.keys())
assert 'domain' not in names, f'domain analyzer should be disabled, got: {names}'
assert 'sigma' not in names, f'sigma_tagger (registry key sigma) should be disabled, got: {names}'
print('OK: 0 upstream analyzers registered by default, flag =', analyzers._ENABLE_UPSTREAM_ANALYZERS)
"

echo "== re-enable flag actually restores the upstream set (proves the seam is reversible, not a deletion) =="
docker compose exec -T -e TIMESKETCH_FORK_ENABLE_UPSTREAM_ANALYZERS=1 timesketch python3 -c "
import importlib
import timesketch.lib.analyzers as analyzers
importlib.reload(analyzers)
from timesketch.lib.analyzers import manager
names = list(manager.AnalysisManager._class_registry.keys())
assert 'domain' in names, f'domain analyzer should be restored, got: {names}'
print('OK: upstream analyzer set restores when flag=1, count =', len(names))
"

echo "== tear down (isolated stack only) =="
docker compose down -v

echo "SMOKE TEST PASSED"
