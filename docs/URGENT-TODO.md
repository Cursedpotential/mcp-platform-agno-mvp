# URGENT TODO

> _Byline: Claude Code · Opus 5 · 2026-08-20_
>
> Required by the **LIVE ONLY / SPRINT MODE** policy in `AGENTS.md`.
> Every stub, every known-broken thing, every deferred fix lands here **loudly**.
> A silent stub is a defect. Nothing here is allowed to go quiet.

## How to use

- Any stub you are forced to write gets an inline `# STUB:` / `// STUB:` **and** a row below.
- A stub is only permitted when the real data or upstream service does not exist yet.
- If it is a function, write the whole function. Do not park a placeholder here to avoid work.
- Clear rows the moment the real implementation lands. This list should shrink.

## Open stubs

| # | Item | File / location | Why it is a stub | Blocking on |
|---|------|-----------------|------------------|-------------|
| — | _(none recorded yet)_ | | | |

## Known broken / deferred

_Seeded 2026-08-20 from the fleet audit. Queued per the "mid-task feedback is queued" rule._

| # | Item | Impact | Status |
|---|------|--------|--------|
| 1 | **Docker subnet `192.168.0.0/20` collides with owner's home LAN `192.168.10.0/24`** on ovh-files AND ovh-app. `ip route get 192.168.10.141` on ovh-files resolves to a local docker bridge — the VPS can never reach the home LAN. | Blocks home-LAN subnet routing; latent blackhole | OPEN |
| 2 | **ovh-files and ovh-app use identical docker subnets** (both 172.17–172.31 + 192.168.0–128). Tailscale can only route one host per CIDR. | Blocks subnet-routing both hosts at once | OPEN |
| 3 | Fix: set `/etc/docker/daemon.json` `default-address-pools` to a distinct 10.x range per host (neither box has a daemon.json; both run Docker defaults). Requires recreating networks = restart all stacks. | Resolves #1 and #2 | OPEN |
| 4 | **Traefik binds `0.0.0.0` on all 4 hosts**, not the Tailscale IP — contradicts the standing "tailscale only, no open net" position. | Public exposure | OPEN |
| 5 | **Port 8080 published to `0.0.0.0` on all 4 hosts**, nothing behind it (`api.insecure=false`). | Needless public surface | OPEN |
| 6 | **`Secrets/PLATFORM_REFERENCE.md` badly stale.** `chat.` / `browser.` / `n8n.` / `milvus.` / `attu.` / `windmill.` .mitechconsult.com all return 503, containers absent. Milvus gone (Weaviate cutover). LiteLLM retired. ovh-data now dead. | Doc drift — misleads every agent | OPEN |
| 7 | **Coolify `*.sslip.io` domains are catalogued but NOT wired to Traefik** — no `traefik.*` labels, return 404. They are not working hostnames. | False assumption of reachability | OPEN |
| 8 | ~~Parallel stacks: TWO Weaviates AND TWO Graphiti stacks violate the no-parallel rule.~~ **CORRECTED 2026-08-20 (archaeology):** the two **Graphiti** stacks are **intentional and load-bearing** — the upstream `zepai/knowledge-graph-mcp` image drops the Neo4j `database=` field, so one image can only bind one Neo4j DB; the `cursedpotential` fork exists to target the `memory` DB for the case lane. Not duplication. The two **Weaviates** remain unexplained → see #15. | Graphiti = by design | PARTLY RESOLVED |
| 9 | **ovh-data VPS still needs terminating at OVH** (billing action, owner-only). Host powered off 2026-08-20; disk with 5.1G surreal data intact until terminated. | Ongoing cost | OWNER |
| 10 | ~~Global `~/.claude/CLAUDE.md` contradiction between the old "confirm before changes" rule and SPRINT MODE.~~ **RESOLVED 2026-08-20** — old rule struck through and marked superseded; destructive/outward-facing carve-outs retained. | — | DONE |
| 14 | 🔴 **SurrealDB is formally RETIRED (ADR-0043, owner ruling 2026-08-06) — yet `data-surreal-phase1-t0-r1` is live in Coolify production and was ordered promoted on 2026-08-20.** These cannot both be current intent. Needs an owner ruling before the promotion proceeds. | Contradicts canon | **OWNER — BLOCKING** |
| 15 | **Two Weaviate instances on ovh-files are unexplained in every session log.** `weaviate-o97r85b7` (8081) vs `weaviate-native-v1-v43tfq` (8082). No log states which is canonical. Do not touch either until owner decides. | Unknown canonical store | OWNER |
| 16 | **LiteLLM container was never actually torn down.** Every doc says "retired" (ADR-0042, owner 2026-07-29) but DECISION_LOG D-030 clarifies only docs/refs were retired. Port 4000 is dead but the container persists. | Doc says done, reality differs | OPEN |
| 11 | **OVH private network never came up.** `/etc/netplan/60-salem-private.yaml` configures `ens7`; actual second NIC is `ens4` (DOWN, unconfigured). Intended "Salem priv" range is 10.1.x. | Private net unavailable | OPEN |
| 12 | **Dead port mapping:** `gateway` container on ovh-app publishes 4000 with nothing listening (retired LiteLLM). Only `opencode` on 4096 is live. | Misleading published port | OPEN |
| 13 | **Historical hazard:** a previously advertised `10.1.x` subnet route once blackholed the owner's public IPv4 (2026-06-25). Re-check before advertising anything in 10.1.x. | Repeat-outage risk | NOTE |

_Added 2026-08-23 (Claude Code · Opus 5) from the cross-repo document-handling audit. These are
ingest-capability gaps, not infra — the rows above are all fleet/networking._

| # | Item | Impact | Status |
|---|------|--------|--------|
| 17 | **DOCX / PPTX / XLSX / HTML ingest fails on a default install.** `server/ingest/service.py:_extract_document` registers `documents.extract-docling` for all of `_DOCUMENT_SUFFIXES`, but appends the `documents.extract-text` fallback **only for `.pdf`** (`service.py:155-158`). `docling` lives in the `document-ai` extra (`pyproject.toml:87`) and is **absent from `requirements.txt`**. The module import succeeds (docling is imported lazily *inside* `extract_docling`), so the extractor is registered and then raises at call time — `RuntimeError: Docling is unavailable; install the "document-ai" extra`. With no fallback for these five suffixes the loop exhausts and `service.py:181` raises `ValueError: document extraction failed for <name>: …`, giving receipt status `"failed"`. **Note:** `docling_extract.py`'s own docstring claims the caller "falls through to native/Tesseract" — that is true for `.pdf` only and wrong for the office formats. | 5 common document types cannot be ingested; docstring overstates coverage | OPEN |
| 18 | **Scanned / image-only PDFs do not OCR by default.** The OCR fallback in `server/tools/extractors/extract_text.py` needs `pytesseract` + `pdf2image`, which live in the `ocr` extra (`pyproject.toml:83`) and are **absent from `requirements.txt`** (only transitive `pillow==12.3.0` is present). Text-layer PDFs are fine — `pypdf==6.15.0` and `pdfplumber==0.11.10` are pinned in base. | Scanned exhibits ingest as empty/near-empty text, silently | OPEN |
| 19 | **The evidence lane cannot ingest PDFs or DOCX at all.** `server/ingest/service.py:197` skips the document-extraction branch entirely when `request.lane is IngestLane.evidence`. Combined with `_whole_file_text` being forbidden for evidence (`:130-131`, ADR-0044) and `_EVIDENCE_FORBIDDEN_PARSERS` (`:29,232-233`), the evidence lane accepts only chat/transcript/Go-registry formats. A scanned court order or a PDF exhibit has **no ingest path into the evidence lane**. | Court-facing document types cannot enter custody | OPEN — needs an owner ruling on whether this is intended (ADR-0044 scope) |

## 2026-08-24 — Coolify + fleet cleanup (owner order, queued mid-Temporal-deploy)
- Owner: "clean up Coolify and the servers — so many things running or dead or stale — BOTH OVH servers."
- Plan: full triage table per server (app, status, last deploy, branch, verdict running/dead/stale/duplicate),
  mine-before-retiring notes, then owner approves the kill/quarantine list. Known dead already: librechat +
  librechat-mongo (exited) vs librechat-app/-mongo-app pairs, nocodb + clone-of-nocodb vs nocodb-app,
  test project. NEVER delete without per-app owner sign-off.
