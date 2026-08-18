#!/usr/bin/env bash
# Hot (zero-downtime) logical backups of the ovh-data stateful stores.
#
# Byline: Claude Code · Opus 5 · 2026-08-01
# Byline: Codex · GPT-5 · 2026-08-18 (typed Weaviate schema + arbitrary-property export)
# Byline: Codex · GPT-5 · 2026-08-18 (explicit target, auth, restore reconciliation proof)
#
# WHY THIS EXISTS
# ===============
# ovh-data (100.119.96.29) is being retired; everything moves to ovh-files
# (100.91.190.107). Owner decision 2026-08-01: snapshot first, transfer, then
# kill the box. This script is PHASE 1a — the snapshot that makes killing the
# box safe.
#
# Deliberately HOT (no container stops). Postgres and SurrealDB provide
# consistent logical snapshots; this Weaviate deployment lacks a backup
# backend, so its schema/object export is a best-effort logical capture:
#
#   Postgres  -> pg_dumpall            (transactionally consistent)
#   SurrealDB -> surreal export        (consistent snapshot)
#   Weaviate  -> schema + paginated raw-object/vector export
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
#   sudo WEAVIATE_URL=http://host:8081 WEAVIATE_CURRENT_TARGET=EvidenceChunkV1 \
#     bash scripts/backup_ovhdata_hot.sh
set -uo pipefail

STAGE="${STAGE:-/data/backup-ovhdata-20260801}"
: "${WEAVIATE_URL:?Set WEAVIATE_URL to the explicit current Weaviate target}"
: "${WEAVIATE_CURRENT_TARGET:?Set WEAVIATE_CURRENT_TARGET to the activated versioned collection}"
WEAVIATE_CURRENT_ALIAS="${WEAVIATE_CURRENT_ALIAS:-EvidenceChunks}"
WEAVIATE_API_KEY="${WEAVIATE_API_KEY:-}"
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
echo "=== Weaviate (typed schema + raw object/vector export, hot) ==="
# The /v1/backups API needs the `backup-filesystem` module, which is NOT enabled
# on this instance (verified live 2026-08-01: "no backup backend filesystem").
# Enabling it means an env change + restart of a Coolify-managed container.
# The fallback therefore captures the COMPLETE typed schema plus every raw
# object returned by REST with its vector. Unlike the former GraphQL selection,
# this does not assume Agno fields (`name`, `content`, `meta_data`, ...), so a
# versioned native collection with DATE/INT/BOOL or future typed properties is
# restorable. Pagination is cursor-based; no 10,000-object truncation remains.
weaviate_curl=(--fail --show-error --silent)
if [ -n "$WEAVIATE_API_KEY" ]; then
  weaviate_curl+=(--header "Authorization: Bearer $WEAVIATE_API_KEY")
fi
inventory="$STAGE/weaviate_restore_inventory.tsv"
: > "$inventory"

if ! command -v jq >/dev/null 2>&1; then
  echo "  FAIL: jq is required for typed Weaviate export"; fail=1
elif ! curl "${weaviate_curl[@]}" "$WEAVIATE_URL/v1/schema" > "$STAGE/weaviate_schema.json"; then
  echo "  FAIL: could not export Weaviate schema"; fail=1
elif ! jq -e '.classes | type == "array"' "$STAGE/weaviate_schema.json" >/dev/null; then
  echo "  FAIL: Weaviate schema response is invalid"; fail=1
elif ! jq -e --arg target "$WEAVIATE_CURRENT_TARGET" \
    '.classes[] | select(.class == $target)' "$STAGE/weaviate_schema.json" >/dev/null; then
  echo "  FAIL: expected current collection $WEAVIATE_CURRENT_TARGET is absent"; fail=1
elif ! curl "${weaviate_curl[@]}" "$WEAVIATE_URL/v1/aliases" > "$STAGE/weaviate_aliases.json"; then
  echo "  FAIL: could not export Weaviate aliases"; fail=1
elif ! jq -e --arg alias "$WEAVIATE_CURRENT_ALIAS" --arg target "$WEAVIATE_CURRENT_TARGET" \
    '.aliases[] | select(.alias == $alias and .class == $target)' \
    "$STAGE/weaviate_aliases.json" >/dev/null; then
  echo "  FAIL: $WEAVIATE_CURRENT_ALIAS is not activated on $WEAVIATE_CURRENT_TARGET"; fail=1
else
  gzip -f "$STAGE/weaviate_schema.json"
  gzip -f "$STAGE/weaviate_aliases.json"
  echo "  OK  typed schema -> $(ls -lh "$STAGE/weaviate_schema.json.gz" | awk '{print $5}')"
  echo "  OK  alias $WEAVIATE_CURRENT_ALIAS -> $WEAVIATE_CURRENT_TARGET"

  while IFS= read -r CLS; do
    [ -n "$CLS" ] || continue
    out="$STAGE/weaviate_${CLS}.ndjson"
    : > "$out"
    after=""
    n=0
    class_failed=0

    while true; do
      curl_args=(
        "${weaviate_curl[@]}" --get "$WEAVIATE_URL/v1/objects"
        --data-urlencode "class=$CLS"
        --data-urlencode "limit=100"
        --data-urlencode "include=vector"
      )
      if [ -n "$after" ]; then
        curl_args+=(--data-urlencode "after=$after")
      fi
      if ! page=$(curl "${curl_args[@]}"); then
        echo "  FAIL ${CLS}: object page request failed"; fail=1; class_failed=1; break
      fi
      if ! page_n=$(printf '%s' "$page" | jq -er '.objects | length'); then
        echo "  FAIL ${CLS}: invalid object page"; fail=1; class_failed=1; break
      fi
      [ "$page_n" -gt 0 ] || break
      printf '%s' "$page" | jq -c '.objects[]' >> "$out"
      next_after=$(printf '%s' "$page" | jq -er '.objects[-1].id')
      if [ "$next_after" = "$after" ]; then
        echo "  FAIL ${CLS}: cursor did not advance"; fail=1; class_failed=1; break
      fi
      after="$next_after"
      n=$((n + page_n))
      [ "$page_n" -eq 100 ] || break
    done

    if [ "$class_failed" -eq 0 ]; then
      gzip -f "$out"
      # Local restore proof: every exported line must retain the typed object
      # identity, arbitrary properties, and vector needed for replay.
      replay_n=$(zcat "$out.gz" | jq -ce 'select(has("id") and has("class") and has("properties") and has("vector"))' | wc -l)
      if [ "$replay_n" -ne "$n" ]; then
        echo "  FAIL ${CLS}: restore contract reconciled ${replay_n}/${n} objects"; fail=1
      else
        printf '%s\t%s\t%s\n' "$CLS" "$n" "weaviate_${CLS}.ndjson.gz" >> "$inventory"
        echo "  OK  ${CLS}: ${n} objects, restore-reconciled -> $(ls -lh "$out.gz" | awk '{print $5}')"
      fi
    fi
  done < <(zcat "$STAGE/weaviate_schema.json.gz" | jq -r '.classes[].class')
  gzip -f "$inventory"
fi
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
