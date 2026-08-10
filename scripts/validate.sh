#!/bin/bash
# Byline: Claude Code · Sonnet 5 · 2026-08-09 (added the doc-path + ADR/D-NNN
# traceability checks appended below — HANDOFF-2026-08-09-S1, task 13)

############################################################################
#
#    Agno Workspace Validator
#
#    Usage: ./scripts/validate.sh
#
############################################################################

CURR_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "${CURR_DIR}")"

# Colors
ORANGE='\033[38;5;208m'
RED='\033[31m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

if [[ -z "${VIRTUAL_ENV:-}" ]]; then
  echo -e "${RED}Warning:${NC} no virtualenv active. Run: ${BOLD}source .venv/bin/activate${NC}"
  echo ""
fi

echo ""
echo -e "${ORANGE}▸${NC} ${BOLD}Validating workspace${NC}"
echo ""

failed=0

echo -e "${DIM}> ruff check ${REPO_ROOT}${NC}"
if ! ruff check "${REPO_ROOT}"; then
  failed=1
fi

echo ""
echo -e "${DIM}> mypy ${REPO_ROOT} --config-file ${REPO_ROOT}/pyproject.toml${NC}"
if ! mypy "${REPO_ROOT}" --config-file "${REPO_ROOT}/pyproject.toml"; then
  failed=1
fi

############################################################################
#
#    Doc / Registers Traceability Checks
#    (added 2026-08-09, HANDOFF-2026-08-09-S1-docs-registers-true-up, task 13)
#
#    (a) every backtick-quoted path cited in README.md / AGENTS.md / this
#        repo's docs/PROJECT_CANON.md §9 must resolve to a real file/dir
#        under REPO_ROOT.
#    (b) every ADR-\d{4} / D-\d{3} reference under server/, sql/, docs/ must
#        resolve to a real docs/adr/<NNNN>-*.md file / docs/DECISION_LOG.md
#        row.
#
#    Tolerant of (skips the whole citing block/line, does not fail):
#      - a `TODO(OQ-N)` marker anywhere in the same bullet/paragraph/row —
#        an explicitly-flagged open question, not silent drift.
#      - a `WORKSPACE-ROOT-relative` tag anywhere in the same bullet/
#        paragraph/row — the path is a deliberate sibling-of-this-repo
#        reference (see the workspace-root CLAUDE.md), not a repo-internal
#        path.
#      - an `NNNN`/placeholder token (template text, not a literal path).
#
############################################################################

cd "${REPO_ROOT}" || exit 1

echo ""
echo -e "${DIM}> doc-path resolution (README.md / AGENTS.md / canon §9)${NC}"

# Groups consecutive lines into "blocks": a blank line, a bullet ("- "), or a
# markdown table row ("|") each start a new block; other lines continue the
# current block. This lets the WORKSPACE-ROOT-relative / TODO(OQ-N) tolerance
# apply per-bullet/per-row rather than per-line (those tags are often a
# sentence after the path they cover, in the same bullet).
_extract_blocks() {
  awk '
    BEGIN{block=""}
    /^[[:space:]]*$/ { if (block!="") {print block; print "@@BLOCK@@"}; block=""; next }
    /^- / || /^\|/ { if (block!="") {print block; print "@@BLOCK@@"}; block=$0; next }
    { if (block=="") block=$0; else block = block "\n" $0 }
    END { if (block!="") {print block; print "@@BLOCK@@"} }
  '
}

_check_doc_paths() {
  local label="$1" content="$2"
  local block=""
  while IFS= read -r line; do
    if [[ "$line" == "@@BLOCK@@" ]]; then
      if echo "$block" | grep -qiE 'WORKSPACE-ROOT-relative|TODO\(OQ-'; then
        block=""
        continue
      fi
      while IFS= read -r tok; do
        [[ -z "$tok" ]] && continue
        [[ "$tok" == *NNNN* ]] && continue
        [[ "$tok" == http* ]] && continue
        [[ "$tok" == \$* ]] && continue
        if [[ "$tok" != */* ]]; then
          case "$tok" in
            *.md | *.py | *.sh | *.sql | *.yaml | *.yml | *.toml | *.json) ;;
            *) continue ;;
          esac
        fi
        if [[ ! -e "${REPO_ROOT}/${tok#./}" ]]; then
          echo -e "  ${RED}✗${NC} [${label}] cited path not found: ${tok}"
          failed=1
        fi
      done < <(printf '%s\n' "$block" | grep -oE '`[A-Za-z0-9_./-]+`' | tr -d '`' | sort -u)
      block=""
    else
      if [[ -z "$block" ]]; then block="$line"; else block="${block}"$'\n'"${line}"; fi
    fi
  done < <(printf '%s\n' "$content" | _extract_blocks)
}

_check_doc_paths "README.md" "$(cat "${REPO_ROOT}/README.md" 2>/dev/null)"
_check_doc_paths "AGENTS.md" "$(cat "${REPO_ROOT}/AGENTS.md" 2>/dev/null)"
_check_doc_paths "docs/PROJECT_CANON.md §9" \
  "$(awk '/^## 9\. Where things live/{flag=1} /^## 10\./{flag=0} flag' "${REPO_ROOT}/docs/PROJECT_CANON.md" 2>/dev/null)"

echo ""
echo -e "${DIM}> ADR-NNNN / D-NNN reference resolution (server/ sql/ docs/)${NC}"

_check_adr_refs() {
  while IFS=: read -r file lineno rest; do
    lc="$(sed -n "${lineno}p" "${REPO_ROOT}/${file}" 2>/dev/null)"
    echo "$lc" | grep -q 'TODO(OQ-' && continue
    for id in $(echo "$rest" | grep -oE '[0-9]{4}'); do
      if ! ls "${REPO_ROOT}"/docs/adr/"${id}"-*.md >/dev/null 2>&1; then
        echo -e "  ${RED}✗${NC} unresolved ADR-${id}  (${file}:${lineno})"
        failed=1
      fi
    done
  done < <(grep -rEno '\bADR-[0-9]{4}\b' "${REPO_ROOT}/server" "${REPO_ROOT}/sql" "${REPO_ROOT}/docs" 2>/dev/null \
    | sed "s|${REPO_ROOT}/||" | sed -E 's/(:[0-9]+:)ADR-([0-9]{4})/\1\2/')
}

_check_d_refs() {
  while IFS=: read -r file lineno rest; do
    lc="$(sed -n "${lineno}p" "${REPO_ROOT}/${file}" 2>/dev/null)"
    echo "$lc" | grep -q 'TODO(OQ-' && continue
    for id in $(echo "$rest" | grep -oE '[0-9]{3}'); do
      if ! grep -qE "^\| D-${id} " "${REPO_ROOT}/docs/DECISION_LOG.md" 2>/dev/null; then
        echo -e "  ${RED}✗${NC} unresolved D-${id}  (${file}:${lineno})"
        failed=1
      fi
    done
  done < <(grep -rEno '\bD-[0-9]{3}\b' "${REPO_ROOT}/server" "${REPO_ROOT}/sql" "${REPO_ROOT}/docs" 2>/dev/null \
    | sed "s|${REPO_ROOT}/||" | sed -E 's/(:[0-9]+:)D-([0-9]{3})/\1\2/')
}

_check_adr_refs
_check_d_refs

echo ""
if [[ $failed -eq 0 ]]; then
  echo -e "${BOLD}Done.${NC}"
else
  echo -e "${RED}${BOLD}Failed.${NC}"
fi
echo ""

exit $failed
