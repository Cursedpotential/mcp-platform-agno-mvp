# Comprehensive Review: Phase 2 — Security & Performance

## Context

Phase 1 (Quality & Architecture) is complete in `.full-review/quality-architecture.md`. Phase 2 analyzes security and performance. No code changes — analysis only. Output goes to `.full-review/security-performance.md`.

## Corrections from Feedback (Round 1)

- **Auth**: Platform uses Keycloak for API tokens + GUI login. Issue is exposed ports bypassing DIAL, not missing auth architecture.
- **Ollama**: NOT a Rule 3 violation. Proxies to Ollama Cloud + 2GB GPU handles classification, embedding, entity resolution. Reclassified as intentional.
- **PII redaction**: NOT auto-redaction. Redaction is a manual workflow before court submission. Tool should still avoid leaking raw PII in audit logs during analysis runs.
- **DuckDB hashing**: Intended design is multi-level (file hash, message hash, more). Current single-path-string hash is wrong on multiple levels.
- **Table validation**: Investigate Zod enum for table allowlisting + chain-of-custody validation for evidence tables as VIP concern.
- **Secrets**: Explore encrypting at rest in DB (for post-bootstrap secrets), `.env` minimum for Docker Compose.
- **Reviewer identity**: Should tie into Keycloak JWT claims.
- **Thread safety**: Confirmed critical by user.

## Proposed Action

Write `.full-review/security-performance.md` with all 26 findings incorporating the corrections above. Update `.full-review/state.json` to reflect Phase 2 completion.

## Files to Create/Modify
- `.full-review/security-performance.md` — Phase 2 report
- `.full-review/state.json` — update progress

## Open Design Questions (to document in report, not resolve now)
1. Zod vs separate validation for table allowlisting
2. Secret storage approach (`.env` / Doppler / Vault / DB encryption)
3. Multi-level hash spec (needs MODULE_2_COORDINATOR)
4. `include_raw_pii` flag design for court-prep workflows
5. Reviewer identity binding to Keycloak JWT

## Remaining Phases
- Phase 3: Testing & Documentation
- Phase 4: Best Practices & Standards
- Phase 5: Consolidated report mapping to spec-driven requirement IDs
