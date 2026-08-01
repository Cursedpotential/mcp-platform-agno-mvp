#!/usr/bin/env bash
# Hot (zero-downtime) logical backups of the ovh-data stateful stores.
#
# Byline: Claude Code · Opus 5 · 2026-08-01
#
# WHY THIS EXISTS
# ===============
# ovh-data (100.119.96.29) is being retired; everything moves to ovh-files
# (100.91.190.107). Owner decision 2026-08-01: snapshot first, transfer, then
# kill the box. This script is PHASE 1a — the snapshot that makes killing the
# box safe.
#
# Deliberately HOT (no container stops) for the three stores that support a
# consistent online export:
#
#   Postgres  -> pg_dumpall            (transactionally consistent)
#   SurrealDB -> surreal export        (consistent snapshot)
#   Weaviate  -> /v1/backups API       (Weaviate's own consistent backup)
#
# Neo4j and Milvus are file-backed with no online export on the community
# edition, so they are COLD-copied in phase 1b via the Coolify stop/start API —
# NEVER `docker stop` directly, because Coolify reconciles desired state
# server-side and a hand-stopped container becomes an orphan.
#
# WHY HOT MATTERS HERE: this box already carries SIX `milvus.corrupt-*`
# directories from previous hot copies of a running store. Logical exports do
# not have that failure mode; raw file copies of a live database do.
#
# Idempotent: re-running overwrites the artifacts in the dated staging dir.
# Nothing is deleted, moved, or stopped by this script.
#
# Usage (run ON ovh-data):
#   sudo bash scripts/backup_ovhdata_hot.sh
set -uo pipefail

STAGE="${STAGE:-/data/backup-ovhdata-20260801}"
WEAVIATE_URL="${WEAVIATE_URL:-http://100.119.96.29:8081}"
BACKUP_ID="${BACKUP_ID:-ovhdata-20260801}"

mkdir -p "$STAGE"
echo "staging dir : $STAGE"
echo "free space  : $(df -h "$STAGE" | awk 'NR==2 {print $4}')"
echo

fail=0

# --- Postgres -----------------------------------------------------------------
echo "=== Postgres (pg_dumpall, hot) ==="
PG=$(docker ps --format '{{.Names}}' | grep -m1 agentos-db || true)
if [ -z "$PG" ]; then
  echo "  SKIP: no agentos-db container running"
else
  # Credentials are read INSIDE the container so they never reach this shell,
  # the process list, or the transcript.
  if docker exec "$PG" sh -c 'PGPASSWORD=$POSTGRES_PASSWORD pg_dumpall -U $POSTGRES_USER' \
       > "$STAGE/pg_dumpall.sql" 2>"$STAGE/pg_dumpall.err"; then
    if tail -3 "$STAGE/pg_dumpall.sql" | grep -q 'dump complete'; then
      gzip -f "$STAGE/pg_dumpall.sql"
      echo "  OK  $(ls -lh "$STAGE/pg_dumpall.sql.gz" | awk '{print $5}')"
      echo "  databases: $(zcat "$STAGE/pg_dumpall.sql.gz" | grep -c '^CREATE DATABASE')"
      echo "  COPY blocks: $(zcat "$STAGE/pg_dumpall.sql.gz" | grep -c '^COPY ')"
    else
      echo "  FAIL: dump has no completion marker — TRUNCATED, do not trust"; fail=1
    fi
  else
    echo "  FAIL: pg_dumpall errored"; head -3 "$STAGE/pg_dumpall.err"; fail=1
  fi
fi
echo

# --- SurrealDB ----------------------------------------------------------------
echo "=== SurrealDB (surreal export, hot) ==="
SR=$(docker ps --format '{{.Names}}' | grep -m1 surrealdb || true)
if [ -z "$SR" ]; then
  echo "  SKIP: no surrealdb container running"
else
  docker exec "$SR" /surreal export \
      --endpoint http://localhost:8000 \
      --username "${SURREAL_USER:-root}" --password "${SURREAL_PASS:-root}" \
      --namespace agno --database platform /tmp/surreal.surql >"$STAGE/surreal.log" 2>&1
  # NOTE: do NOT verify with `docker exec ... test -s` — the surrealdb image is
  # distroless and has no `test` binary, so that check reports failure even when
  # the export succeeded (hit live 2026-08-01). Copy out, then size-check on the
  # HOST, where coreutils actually exists.
  docker cp "$SR:/tmp/surreal.surql" "$STAGE/surreal_platform.surql" 2>/dev/null
  if [ -s "$STAGE/surreal_platform.surql" ]; then
    tables=$(grep -c '^-- TABLE:' "$STAGE/surreal_platform.surql" || true)
    gzip -f "$STAGE/surreal_platform.surql"
    echo "  OK  $(ls -lh "$STAGE/surreal_platform.surql.gz" | awk '{print $5}')  tables=$tables"
  else
    echo "  FAIL: export produced no file"; tail -3 "$STAGE/surreal.log"; fail=1
  fi
fi
echo

# --- Weaviate -----------------------------------------------------------------
echo "=== Weaviate (GraphQL object export, hot) ==="
# The /v1/backups API needs the `backup-filesystem` module, which is NOT enabled
# on this instance (verified live 2026-08-01: "no backup backend filesystem").
# Enabling it means an env change + restart of a Coolify-managed container for a
# 6.5 MB store — not worth it. Export the objects (WITH their vectors, which is
# what makes this a real backup rather than a listing) straight out of GraphQL.
for CLS in $(curl -s "$WEAVIATE_URL/v1/schema" | grep -o '"class":"[^"]*"' | cut -d'"' -f4); do
  out="$STAGE/weaviate_${CLS}.json"
  curl -s -X POST "$WEAVIATE_URL/v1/graphql" -H 'Content-Type: application/json' \
    -d "{\"query\":\"{Get{${CLS}(limit:10000){name content meta_data content_id content_hash _additional{id vector}}}}\"}" \
    > "$out"
  n=$(grep -o '"id":' "$out" | wc -l)
  if [ -s "$out" ] && ! grep -q '"errors"' "$out" && [ "$n" -gt 0 ]; then
    gzip -f "$out"
    echo "  OK  ${CLS}: ${n} objects -> $(ls -lh "$out.gz" | awk '{print $5}')"
  elif [ "$n" -eq 0 ] && ! grep -q '"errors"' "$out"; then
    rm -f "$out"; echo "  ..  ${CLS}: 0 objects (empty class, nothing to back up)"
  else
    echo "  FAIL ${CLS}: $(head -c 150 "$out")"; fail=1
  fi
done
echo

# --- Manifest -----------------------------------------------------------------
echo "=== checksums (the restore contract) ==="
( cd "$STAGE" && sha256sum ./*.gz > SHA256SUMS 2>/dev/null; cat SHA256SUMS )
echo
echo "=== staged artifacts ==="
ls -lh "$STAGE" | tail -n +2

echo
if [ "$fail" -eq 0 ]; then
  echo "RESULT: hot backups OK"
else
  echo "RESULT: ONE OR MORE BACKUPS FAILED — do not proceed to the move"
fi
exit "$fail"
