#!/usr/bin/env bash
# Cold-copy (tar) file-backed data-tier volumes for the ovh-data -> ovh-files
# migration. Runs ON THE SOURCE HOST while the owning Coolify app is STOPPED
# (the caller, phase1b_coldcopy.sh, is responsible for stop/start via the
# Coolify API — this script never touches the container itself).
#
# Byline: Claude Code · Sonnet (agent) · 2026-08-01
#
# Usage (on ovh-data):
#   bash coldcopy_volume.sh <stage_dir> <archive_basename> <abs_path> [abs_path ...]
#
# Bundles every given absolute path into ONE archive, storing paths relative
# to `/` so `tar -C / -xzf` on the target host recreates the exact absolute
# path (uid/gid preserved numerically, which is what matters — the neo4j
# 7474:7474 and milvus 999:999 owners don't need to resolve to names).
set -euo pipefail

STAGE="${1:?usage: coldcopy_volume.sh <stage_dir> <archive_basename> <abs_path> [abs_path ...]}"
LABEL="${2:?usage: coldcopy_volume.sh <stage_dir> <archive_basename> <abs_path> [abs_path ...]}"
shift 2
PATHS=("$@")
[ "${#PATHS[@]}" -ge 1 ] || { echo "need at least one absolute path to archive" >&2; exit 1; }

mkdir -p "$STAGE"
ARCHIVE="$STAGE/${LABEL}.tar.gz"

RELS=()
for p in "${PATHS[@]}"; do
  [ -e "$p" ] || { echo "MISSING: $p" >&2; exit 1; }
  RELS+=("${p#/}")
done

echo "== $LABEL =="
echo "archiving:"
printf '  %s\n' "${PATHS[@]}"
tar -C / -czf "$ARCHIVE" "${RELS[@]}"

( cd "$STAGE" && sha256sum "$(basename "$ARCHIVE")" > "${LABEL}.tar.gz.sha256" )
echo "sha256: $(cat "$STAGE/${LABEL}.tar.gz.sha256")"
echo "size:   $(ls -lh "$ARCHIVE" | awk '{print $5}')"
echo "top-level entries:"
tar -tzf "$ARCHIVE" | awk -F/ '{print "/"$1"/"$2}' | sort -u
