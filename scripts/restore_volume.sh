#!/usr/bin/env bash
# Restore a cold-copy tarball produced by coldcopy_volume.sh onto the TARGET
# host (ovh-files), for the ovh-data -> ovh-files migration.
#
# Byline: Claude Code · Sonnet (agent) · 2026-08-01
#
# Usage (on ovh-files):
#   bash restore_volume.sh <tarball> [expected_sha256]
#
# Extracts to the exact absolute path(s) recorded in the tar (paths were
# stored relative to `/` by coldcopy_volume.sh, so `tar -C / -xzf` recreates
# them, uid/gid preserved numerically since we run as root).
set -euo pipefail

TARBALL="${1:?usage: restore_volume.sh <tarball> [expected_sha256]}"
EXPECTED_SHA="${2:-}"

[ -f "$TARBALL" ] || { echo "not found: $TARBALL" >&2; exit 1; }

ACTUAL_SHA=$(sha256sum "$TARBALL" | awk '{print $1}')
echo "sha256: $ACTUAL_SHA"
if [ -n "$EXPECTED_SHA" ]; then
  if [ "$ACTUAL_SHA" != "$EXPECTED_SHA" ]; then
    echo "SHA MISMATCH: expected $EXPECTED_SHA, got $ACTUAL_SHA — refusing to extract" >&2
    exit 1
  fi
  echo "sha256 verified OK against expected"
fi

echo "extracting $TARBALL -> /"
tar -C / -xzf "$TARBALL"
echo "done. restored top-level paths:"
tar -tzf "$TARBALL" | awk -F/ '{print "/"$1"/"$2}' | sort -u
