#!/usr/bin/env bash
# =============================================================================
# annotate-plans.sh — batch-annotate the planning docs in Plannotator.
#
# RUNS ON THE OWNER'S HOME MACHINE (Plannotator installed locally; this cannot
# work from a remote/cloud session — Plannotator opens a localhost browser UI).
#
# For each doc: opens it in the Plannotator annotation UI, blocks until you
# submit ("send feedback") or close the tab, captures the emitted annotations,
# then writes TWO outputs under docs/planning/annotations/:
#   <name>.<stamp>.annotations.md   raw annotation feedback only
#   <name>.<stamp>.annotated.md     full doc + appended "Annotations" section
#     (self-contained — Bluetooth this one to the phone)
#
# Usage:
#   ./scripts/annotate-plans.sh                    # the three default docs
#   ./scripts/annotate-plans.sh docs/foo.md ...    # explicit list
#
# Env overrides (the Plannotator CLI verb isn't formally documented — this
# script probes `--help` and falls back sanely):
#   PLANNOTATOR_BIN            path to the plannotator binary
#   PLANNOTATOR_ANNOTATE_CMD   subcommand for markdown annotation (default:
#                              auto-probe for "annotate")
#
# Alternative native flow: inside a LOCAL Claude Code session in this repo,
# `/plannotator-annotate docs/planning/gui-integration-spec.md` — annotations
# flow straight back to the agent, which can revise the doc for you.
# =============================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ "$#" -gt 0 ]; then
  DOCS=("$@")
else
  DOCS=(
    docs/planning/gui-integration-spec.md
    docs/planning/port-backlog.md
    docs/HANDOFFS.md
  )
fi

OUT_DIR="$REPO_ROOT/docs/planning/annotations"
STAMP="$(date +%Y%m%d-%H%M)"
mkdir -p "$OUT_DIR"

# --- locate the binary -------------------------------------------------------
BIN="${PLANNOTATOR_BIN:-$(command -v plannotator || true)}"
if [ -z "$BIN" ]; then
  for c in "$HOME/.plannotator/bin/plannotator" "$HOME/.local/bin/plannotator"; do
    [ -x "$c" ] && BIN="$c" && break
  done
fi
if [ -z "$BIN" ]; then
  echo "ERROR: plannotator binary not found. Install it (https://plannotator.ai) or set PLANNOTATOR_BIN." >&2
  exit 1
fi

# --- figure out the annotate subcommand --------------------------------------
ANNOTATE_CMD="${PLANNOTATOR_ANNOTATE_CMD:-}"
if [ -z "$ANNOTATE_CMD" ]; then
  if "$BIN" --help 2>&1 | grep -qiE '(^|\s)annotate(\s|$)'; then
    ANNOTATE_CMD="annotate"
  else
    # some builds take the file directly as the first argument
    ANNOTATE_CMD=""
  fi
fi
echo "plannotator: $BIN ${ANNOTATE_CMD:-<direct file arg>}"

# --- annotate each doc, sequentially -----------------------------------------
for doc in "${DOCS[@]}"; do
  if [ ! -f "$doc" ]; then
    echo "SKIP (missing): $doc" >&2
    continue
  fi
  base="$(basename "$doc" .md)"
  raw="$OUT_DIR/$base.$STAMP.annotations.md"
  merged="$OUT_DIR/$base.$STAMP.annotated.md"

  echo
  echo ">>> Opening in Plannotator: $doc"
  echo "    Annotate in the browser, then hit send (or close the tab to skip)."

  # Capture whatever plannotator emits on stdout when feedback is submitted.
  set +e
  if [ -n "$ANNOTATE_CMD" ]; then
    "$BIN" "$ANNOTATE_CMD" "$doc" | tee "$raw.tmp"
  else
    "$BIN" "$doc" | tee "$raw.tmp"
  fi
  status=$?
  set -e

  if [ $status -ne 0 ] || [ ! -s "$raw.tmp" ]; then
    rm -f "$raw.tmp"
    echo "    no annotations captured for $doc (skipped or closed) — moving on."
    continue
  fi

  mv "$raw.tmp" "$raw"
  {
    cat "$doc"
    printf '\n\n---\n\n## Annotations (%s, via Plannotator)\n\n' "$STAMP"
    cat "$raw"
  } > "$merged"
  echo "    wrote: $raw"
  echo "    wrote: $merged   <- self-contained copy for the phone"
done

echo
echo "Done. Annotated copies (if any) are in docs/planning/annotations/."
echo "Commit them, or hand the *.annotated.md files to a Claude session to apply."
