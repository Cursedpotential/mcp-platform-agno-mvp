# HANDOFF S2 — Build & test green
> _2026-08-09 · repo @ a68fabd · STATUS: READY once S4 task 4 allocates the SBV-promotion D-NNN id · Depends: S4 task 4 (OQ-10 ruling improves task 1) · Blocks: S3, S7_
> Inventory items: T1, T2, T3, T4 (=F-F), TR-3(sbv half). Audit baseline: 17 failed / 495 passed / 5 skipped (agnohq/python:3.12).
> MANDATORY: read PLAN-2026-08-09-completion-master.md §Standing constraints before executing.

## Goal
Clean reproducible build; 0 failing tests; stale-test debt retired without losing the forensic
guarantees the stale tests were protecting.

## Tasks
1. [T1] Regenerate requirements from pyproject (generator already carries the
   --python-platform/--python-version fix):
   `docker compose run --rm agentos-api ./scripts/generate_requirements.sh upgrade`
   Verify output contains beautifulsoup4, lxml, pikepdf, ijson, json-repair, clevercsv,
   charset-normalizer, pypdf, pdfplumber; verify grpcio/weaviate-client conflict resolved.
   pymilvus: per OQ-10 ruling — drop from Dockerfile (cutover verified) or declare in pyproject
   (not verified). If unruled: leave Dockerfile line, note in DEBT. NEVER hand-edit requirements.txt.
   Check: clean `docker compose build agentos-api` from scratch; `uv pip sync requirements.txt
   --system --dry-run` reports no conflict; the 7 dep-driven failures (facebook_html ×3,
   imessage_html ×3, test_repair_tools ×1) pass.
2. [T4] tests/test_session_embedder.py: mark the 3 live-Weaviate tests
   `@pytest.mark.integration` (marker + default `-m 'not integration'` exclusion already exist in
   pyproject.toml:163-166). Where intent is unit routing coverage, monkeypatch the client instead.
   Check: default `pytest -q` opens no sockets there; `pytest -m integration` still selects them.
3. [T3] tests/test_semantica_wiring.py: replace hardcoded 100.119.96.29 assertions with
   (a) assert-against-module-default-constant and (b) monkeypatched env-override path. Do NOT
   hardcode 100.91.190.107 — that re-arms the same trap. Check: a future host move requires zero
   test edits.
4. [T2] Rewrite tests/test_sbv_demotion.py for the 2026-08-05 promotion ruling (cite the S4 D-NNN
   entry in the test docstring — TR-3):
   a. Resolution tests → new contract: SBV primary when SBV_SERVICE_PASS wired; sms_xml fallback
      when not; no SBV_PRIMARY_ENABLED gate.
   b. RE-PIN the forensic guarantees against the LIVE paths: bodyless-media retention
      (516-dropped-MMS lesson) and outbound-role mapping (types 2/4/5/6) asserted against
      `_map_universal_record` AND against sms_xml.py (the fallback must uphold them too).
   c. Legacy `_map_message`: decide dead-code vs explicit-legacy; if kept, docstring must say
      which path uses it; if dead, move the function to `_stale/` (workspace never-delete rule —
      never `git rm`), leave a one-line pointer in sbv_sms.py's header, record in the commit.
   Check: suite green AND both forensic lessons still pinned by named tests.
5. Green-suite gate: `docker compose run --rm agentos-api pytest -q` → **0 failed** (integration
   deselected). Record the new pass count in docs/DEBT.md's stamp (S1 task 9 coordinates).

## Acceptance
Fresh-clone → `docker compose build` → `pytest -q` = green, no manual steps. Failures list from the
2026-08-09 audit fully dispositioned: T1 fixed, T2 rewritten-with-guarantees, T3 de-drifted,
T4 marked.

## Constraints
Standing constraints per PLAN master. requirements.txt only ever regenerated. evals/cases.py stays
`CASES = ()` in this segment (populated in S9 — it is a documented intentional stub, not drift).
