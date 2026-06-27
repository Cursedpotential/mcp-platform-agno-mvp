# HANDOFF — sort/dedupe → `evidence/sort.py` + `evidence sort`

> _Byline: Claude Code (PIPELINE, git side) · Opus 4.8 · 2026-06-27_
> **Verbatim sort/dedupe logic supplied by the SORT lane** (transcribed from the case-bible plugin
> tools); PIPELINE owns the branch/commit. NO secret VALUES here — env/file names only.
> **You (cloud agent) are isolated**: not on Tailscale, cannot reach R2/ovh3/`D:/backup`, cannot see
> our coordinator bus. Everything you need is in this file. Build the tool; the owner runs it on the
> Windows box (which has the R2 mount + `D:/backup`).

## Your goal
Re-implement the **proven** raw→sorted pipeline as `evidence/sort.py` exposing an **`evidence sort`** CLI
subcommand, on the existing custody/workflows/registry spine. It MUST stay: **copy-only / never-delete**,
**best-version deduped**, **package-intact**, **type-first**, **idempotent with a provenance ledger**.
Reuse custody's `sha256` hashing (see §3 for the sha256-vs-md5 contract). Unit tests against a **fake
filesystem** (no real R2/`D:`), a **non-destructive dry-run** mode, and **keep CI green** (ruff + mypy +
pytest on `main`). Open a PR for review — do not merge.

Canonical source tools (the working logic transcribed below lives here, on the owner's box — you can't
reach them, they're listed for provenance): `cb_r2_sort.py` (taxonomy + md5 best-version dedup + rclone
emit), `cb_typefirst_ledger.py` (type-first classifier + tags), `cb_execute_typefirst.py` (server-side
rclone COPY executor + executed ledger), `cb_connect.py` (credential/endpoint resolution), `cb_clean_names.py`
(`clean_path` filename normalization). All under `~/.claude/local-plugins/case-bible/tools/`.

---

## 1. EXISTING LOGIC (verbatim)
The three load-bearing pieces, exactly as they run today. Re-implement these behaviors in `evidence/sort.py`.

**(a) Best-version dedup (DuckDB SQL, from `cb_r2_sort.py`)** — partition by md5, rank, keep one:
```sql
dedup AS (
  SELECT *, CASE WHEN md5 IS NULL OR md5='' THEN 1 ELSE row_number() OVER (
      PARTITION BY md5 ORDER BY
        (CASE WHEN p LIKE '%_review_hold%' OR p LIKE '%legacy%' OR p LIKE '%(copy%' THEN 1 ELSE 0 END),
        length(old_path), bytes DESC) END AS rn
  FROM withmd5
)
-- decision_state: md5 null/'' -> 'canonical_nohash'; rn=1 -> 'canonical'; else 'duplicate_superseded'
```

**(b) Server-side copy op (from `cb_execute_typefirst.py`)** — copy-only, never move/delete:
```python
def copy_one(row):
    src = f"{RAW}/{row['old_path']}"                       # RAW = "r2:casebible-raw"
    dst = f"r2:{row['dest_bucket']}/{row['new_path']}"
    p = subprocess.run([RCLONE, "copyto", src, dst, "--s3-no-check-bucket"], capture_output=True, text=True)
    return {**row, "status": "ok" if p.returncode == 0 else "ERR", "err": (p.stderr or "")[:240]}
# parallelized with ThreadPoolExecutor (default 8 workers); each op records ok/ERR + truncated stderr.
```

**(c) Type-first classifier (from `cb_typefirst_ledger.py`)** — `classify(r) -> (type_bucket, sub, source)`,
evaluated TOP-DOWN, first match wins:
```python
# inputs per row: basename(bn), ext, doc_type(dt), relevance(rel), platform(plat), is_conversation(isconv), low=bn.lower()
# --- hard junk (always quarantine, even if code-typed) ---
if bn.startswith("$R") or bn.startswith("$I"):          -> QUARANTINE/recycle
if ext in INSTALLER_EXT:                                 -> QUARANTINE/installer
if re.match(r"^f\d+\.(txt|xml|html|svg|ini)$", bn):      -> QUARANTINE/shader-junk
# --- RESCUE: model mislabeled real content/tools as junk (basename allow-list) ---
if bn in RESCUE:                                         -> RESCUE[bn]
if low.startswith("copy of geocoding"):                  -> Documents/general
if any(t in low for t in THIRD_PARTY):                   -> Tools & Platform/forked-3rd-party
# --- code / tools (keep case scripts even if flagged junk) ---
# Tools & Platform SUBSTRUCTURE (owner): AI-Platform (agents/code) · TraceIQ (geo/Google-timeline)
#   · forked-3rd-party · to-review/junk. Route by content: code/agents -> AI-Platform;
#   geolocation/Google-timeline tooling -> TraceIQ; the THIRD_PARTY allow-list -> forked-3rd-party.
if dt=="code" or ext in CODE_EXT:                        -> Tools & Platform/AI-Platform
# --- generic flagged-junk (non-code, non-rescued) ---
if dt=="junk" or rel=="junk":                            -> QUARANTINE/flagged-junk
# --- knowledge (Context Corpus = NOT evidence) ---
if dt=="ai_chat" or (isconv and plat in AI_PLATS):       -> Knowledge/ai-chats/<plat|misc>
if dt in (research,note,documentation,technical):        -> Knowledge/<research|notes|docs|docs>
# --- legal (NO "Legal" top-level — it was DROPPED from the locked taxonomy; route into Case Mgmt / Knowledge) ---
if dt in (legal_filing,court_order):                     -> Case Management/filings
if dt=="legal_reference" or rel=="legal_reference":      -> Knowledge/legal-reference
if rel=="work_product":                                  -> Case Management/work-product
# --- evidence (sub-sorted by SOURCE/platform) ---
if dt=="message_thread" or (isconv and plat in MSG_PLATS): -> Evidence/messaging/<plat|misc>
if dt=="screenshot":                                     -> Evidence/screenshots/<plat|misc>
if dt in (photo,image,video) or ext in IMG_EXT:          -> Evidence/media/<plat|misc>
if dt in (call_log,audio):                               -> Evidence/audio/<plat|phone>
if dt=="financial" or rel=="financial":                  -> Evidence/financial
if dt=="public_record":                                  -> Evidence/public-record
if dt in (dataset,log):                                  -> Evidence/records-data
# --- entities ---
if dt=="contacts" or "people" in dom:                    -> Entities/<contacts|candidates>
# --- exports & bundles ---
if dt=="export_bundle" or ext in ARCHIVE_EXT:            -> Exports & Bundles/<plat|misc>
# --- documents (generic) ---
if dt in (document,text) or rel=="personal_admin":       -> Documents/general
else:                                                    -> Inbox/_triage
```
Constant sets (verbatim):
```python
AI_PLATS  = {chatgpt, claude, gemini, perplexity}
MSG_PLATS = {sms, imessage, facebook, snapchat, whatsapp, instagram}
CODE_EXT  = {.py,.js,.mjs,.cjs,.ts,.go,.sh,.ps1,.sql,.ipynb,.rb,.pl,.r,.code-workspace}
INSTALLER_EXT = {.exe,.msi,.dll,.deb,.xapk,.apk,.dmg,.pkg,.p7b,.woff}
ARCHIVE_EXT   = {.zip,.rar,.7z,.tar,.gz,.tgz,.zst}
IMG_EXT       = {.jpg,.jpeg,.png,.gif,.heic,.webp,.bmp,.tiff,.svg}
THIRD_PARTY   = (fclones, deduplicator, dude-main, word-duplicate, zoplicate, tidycobra, storm-main)
# RESCUE = basename -> (bucket, sub):
#   data.json -> Documents/general; content.zip & "content (3).zip" -> Exports & Bundles/pdf-bundle;
#   place_id_db.json & enriched_timeline_human_readable.csv & refs_dick_summary_2024_2025.csv -> Evidence/records-data;
#   exporter.html -> Tools & Platform/AI-Platform
```
`platform(relpath, plat)` source detection: scan path+plat for chatgpt / perplex(→perplexity) / gemini /
claude / snapchat / imessage / whatsapp / instagram; `messenger|facebook`→facebook; `sms|/sms|_sms`→sms;
phone variants / `call.?log`→phone; else `""`.

**CLASSIFIER CAVEAT (carry forward):** use the ORIGINAL path/folder name as a *signal* (gemini/chatgpt/
Facebook/account name) but **VERIFY by content + extension** — the current sort has real misclassifications
(~53% of `ai_chat`-tagged files have non-chat extensions .docx/.csv/.pdf/.py/.zip). Tag richly EARLY.

Filename dup-markers (`Copy of`, ` - Copy`, `(2)`) are stripped from the DESTINATION path only via
`cb_clean_names.clean_path`; the SOURCE path is preserved verbatim in the ledger.

---

## 2. SOURCES
| Role | Location | Notes |
|---|---|---|
| RAW (authoritative source) | `r2:casebible-raw` | NEVER modified/deleted — the archive of record. Reached via the `rclone` remote `r2:` (S3 R2 endpoint). |
| SORTED (vault / destination) | `r2:casebible-sorted` | **This IS the "Case Bible" vault.** Copies land here. |
| QUARANTINE (junk destination) | `r2:casebible-quarantine` | Obvious junk copies (never deleted from raw). |
| Local hydrated backup | `D:/backup` | Authoritative HYDRATED content source (OneDrive ingest left dehydrated stubs). Read IN PLACE. **Must stay intact.** Except `icloud/` placeholders. |
| Local working drive | `D:/casebible/` | catalog duckdb, ledgers/exports, working sqlite. |
| Enrichment index | Postgres `casebible` (ovh2 Coolify container) via SSH tunnel | drives classification (`cb.enrichment`). |
| Dedup md5 snapshot | `D:/casebible/casebible.duckdb` table `r2_files(path, md5)` | the md5 source for best-version dedup. |
| Working/registry store | `D:/casebible/casebible_work.sqlite` (`CB_WORK_DB`) | durable `sort_map` + dedup decisions + progress. |

`rclone` is reached via `shutil.which("rclone")` (Windows fallback: the WinGet rclone path). **You should
just assume `rclone` is on PATH** and never hard-code a path. R2 R/W creds live in the rclone config (and/or
`CB_R2_*` env) — never in code.

**KEY-DRIFT (resolve before any copy):** the enrichment index `source_path`s come from an OLDER
`/home/ubuntu/r2raw` snapshot and have **drifted from the current `casebible-raw` keys** — so `old_path` from
enrichment is NOT guaranteed to be a live raw object key. Before emitting a copy op, **resolve each `old_path`
to a real current raw key**: (1) exact match against the live raw listing / the `r2_files` snapshot, else
(2) unique-basename match. Rows that resolve to neither are **deferred** (phase-2 re-match / re-enrich), never
copied to a guessed key. (In today's run only ~9.3k of ~15k resolved; the rest were deferred.)

---

## 3. DEDUPE RULES
**Hash identity contract (owner decision — put this here):** **`sha256` is the ONE canonical identity**;
**md5 is a PRE-FILTER only, never the recorded hash.** The existing R2 snapshot uses md5 (cheap S3 ETag) to
*group* candidates fast; when you build `evidence/sort.py`, **reuse custody's `sha256`** as the recorded
identity (custody already computes it), and use md5 only to shrink the candidate set before the sha256 check.
A md5 match is a *suspected* duplicate → confirm with sha256 before declaring "same file."

Best-version selection (within a hash group), exactly as today (`cb_r2_sort.py`, SQL in §1a):
- Source md5 by LEFT JOIN of the ledger to `r2_files` on `path = old_path` (the precomputed R2 md5 snapshot).
- **No hash → treat as canonical** (`decision_state='canonical_nohash'`; NEVER silently drop an un-hashed file).
- Within a group (`PARTITION BY md5`), keep `row_number()=1` ordered by:
  1. **de-prioritize copies/legacy:** `+1` if path matches `%_review_hold%` OR `%legacy%` OR `%(copy%` (else 0),
  2. then **shorter `old_path`** (cleaner location wins),
  3. then **larger `bytes` DESC** (more complete wins).
- Winner → `decision_state='canonical'` (copied); losers → `'duplicate_superseded'` (NOT copied, retained in ledger).
- **Identity is content, not name+size+path:** name+size+path NEVER decide identity — only the hash does.
  `(copy`/legacy path markers only break TIES between byte-identical copies.

**raw-vs-backup tie-break:** RAW (`r2:casebible-raw`) is the provenance source for the copy op; `D:/backup`
is the hydrated-content fallback when a raw object is a dehydrated stub. Hash identity governs "same file";
the path-rank above governs which LOCATION is canonical. **Content is NEVER changed by the sort — only paths.**

---

## 4. MOVE vs COPY (HARD RULE: copy-only, never delete)
- Every op is a **server-side `rclone copyto <raw-src> <dest> --s3-no-check-bucket`**. **No move, no delete, EVER.**
- RAW root stays intact (proven: 401 objects, **0 deletes, 0 errors** on the executed root-pile run).
- `D:/backup` is read in place and **must stay intact** — never delete originals after a copy.
- Parallelize with a `ThreadPoolExecutor` (default 8 workers); each op records `status` ok/ERR + truncated stderr.
- Optional later "tidy": copy now-sorted originals into `raw/_moved_<stamp>/` (preserving structure) — still a
  COPY (the owner's "moved folder" pattern); do NOT remove originals.

**2-LLM QUARANTINE HARD RULE (owner, REQUIRED — the classifier over-flags):** nothing is sent to
`r2:casebible-quarantine` on a single model's call. A file the classifier marks junk goes to a HOLD, then a
**DIFFERENT LLM** (Morph / Sonnet / Opus — **NEVER Haiku**) re-reads it to confirm it's actually junk, **then a
human-review step** before the quarantine copy fires. Proven 2026-06-27: the 1st model flagged **522**; the 2nd
confirmed only **10** (512 rescued). Also run a **rescue pass first** — pull real-content extensions back out of
the quarantine candidate set before the 2nd-LLM pass. So quarantine is: classifier-flag → rescue-pass →
2nd-LLM confirm → human review → copy. Never one-model-to-quarantine.

---

## 5. VAULT LAYOUT (TYPE-FIRST — the final, locked model)
Top level = **TYPE**, never domain. Final top-level set:
`Inbox · Evidence · Entities · Case Management · Knowledge · Tools & Platform · Documents · Exports & Bundles ·
Legacy · Archive` (+ a `Quarantine` bucket, which is the separate `r2:casebible-quarantine`).
- **Inside `Evidence/` → sub-divide by SOURCE/platform** (sms / imessage / facebook / snapchat / phone /
  whatsapp / instagram …) and **preserve the original source folder structure** (`rel_tail`).
- **Knowledge** = Context Corpus (AI chats, research, notes, docs, **legal-reference**) — **NOT evidence**. AI
  chats are Knowledge/context, never the evidence schema (canonical vector home Milvus `casebible_ai_conversations`).
- **NO "Legal" top-level** (dropped from the locked taxonomy): legal filings/orders + work-product →
  `Case Management/{filings,work-product}`; legal reference material → `Knowledge/legal-reference`.
- **`Tools & Platform/` substructure** (owner): `AI-Platform` (agents/code) · `TraceIQ` (geo / Google-timeline) ·
  `forked-3rd-party` (the THIRD_PARTY allow-list) · `to-review` (uncertain/junk-pending). Not a flat `code/` dir.
- **Domain is NEVER a folder** — it rides as multi-tag metadata (§6) so the DB can pivot by domain with zero re-sorting.
- **Destination path (COLLISION-SAFE — this is load-bearing, do not flatten to basename):**
  `new_path = <Type>/<sub>/<basename>` **ONLY when that basename is UNIQUE within `(Type, sub)`**. Otherwise
  **disambiguate**: preserve the package **`rel_tail`** (platform-relative structure), and as the
  guaranteed-unique fallback use the **FULL raw key path** under `<Type>/<sub>/`. **Basename-only flattening =
  SILENT EVIDENCE LOSS** — proven 2026-06-27: a basename-only run raced/overwrote 2,632 files across 563
  collision groups (600 `manifest.json` → 1 path; **75 Facebook `message_1.json` EVIDENCE files → 2 paths**).
  raw was intact so it was recoverable, but `evidence/sort.py` MUST NOT repeat it (see build notes:
  assert zero `new_path` collisions before any copy). The `_root_intake_<stamp>/` / `_root_cleanup_<stamp>/`
  framing is ROOT-PILE-specific (a one-off intake batch) — not the general layout.
- **Package-intact:** a conversation + its attachment tail stay together. `rel_tail` keeps platform-relative
  structure: `imessage`→strip `^.*imessage exports/`; `snapchat`→strip `^.*[Ss]napchat[^/]*/`;
  `facebook`→strip `^.*(court/fb/|[Ff]acebook/)`; else basename.
- Layout is **type/source/relative-tail**, NOT content-addressed (`<sha[:2]>/<sha>/<name>`). Content-addressing
  is custody's job (the write-once evidence blob store); the sorted vault is human-navigable by type+source.

---

## 6. IDEMPOTENCY + MANIFEST (the provenance ledger)
- **Idempotent by construction:** `rclone copyto` to a fixed `new_path` is safe to re-run (same content → same
  dest). Dedup decisions are deterministic (no randomness; the stamp comes from env `CB_STAMP`, never `Date.now`).
- **Proposal ledger** (DRY-RUN, no R2 ops): `D:/casebible/exports/sort_proposal_typefirst_root_<STAMP>.{parquet,csv}`.
- **Executed ledger** (provenance, REQUIRED): `D:/casebible/exports/sort_executed_typefirst_root_<STAMP>.csv` —
  every row = `old_path → new_path` + dest/type/tags/status. **HARD REQ: record `old_path→new_path` on EVERY
  raw→sorted copy** (package/associated-file traceability).
- Executed-CSV header (schema): `file_id, old_path, dest_bucket, type_bucket, sub, new_path, source, domain_tags,
  ref_proposed_domain, ref_relevance, ref_doc_type, parties, date_start, date_end, model_tags, bytes, confidence,
  needs_review, status, err`.
- **Durable working store:** the `sort_map` table mirrored into `D:/casebible/casebible_work.sqlite`
  (DuckDB↔SQLite ATTACH) for dedup decisions + sort progress + the file registry.
- **Re-run behavior:** consult the executed ledger / `sort_map`; skip ops already `status=ok` for the same
  `old_path→new_path`; re-attempt prior `ERR` rows. Do NOT re-mint a new stamp for a resume.

**Multi-tag metadata** (domain rides as tags, not folders) — `tags_for(row, bucket)` → `domain_tags` JSON array:
```python
DOMAIN_TAG = {Evidence:#evidence, Knowledge:#context-corpus, Legal:#legal, Entities:#entities,
              Case Management:#case-management, Tools & Platform:#platform, Documents:#document,
              Exports & Bundles:#artifact, Inbox:#needs-review}
TYPE_TAG   = {ai_chat/message_thread:#chat-export, screenshot:#screenshot, photo/image:#image, video:#video,
              call_log/audio:#audio, legal_filing:#motion, court_order:#court-order, legal_reference:#legal,
              public_record:#public-record, contacts:#people-search, email:#email, code:#tooling,
              research:#research, note/dataset/financial:#document, export_bundle:#artifact}
FUNC_TAG   = {research:#research, code:#tooling, timeline:#timeline}
# + regex on title+summary: timeline|chronolog -> #timeline ; affidavit|motion|subpoena|statute|\bmcl\b -> #legal-strategy
# + always add #raw
```
Each ledger row also carries: `ref_proposed_domain, ref_relevance, ref_doc_type, parties, date_start, date_end,
model_tags, bytes, confidence, needs_review`.

---

## 7. PROCESS HANDOFF (how "process" consumes `sorted/`)  — _PIPELINE lane_
After `evidence sort` lands files in `r2:casebible-sorted`, the **evidence pipeline** (PIPELINE's spine)
consumes them. `evidence sort` should **just organize files into `sorted/` + emit the executed ledger** — it
must NOT parse/embed/hash-chain. The downstream pipeline (separate, already built) does:
```
custody (sha256 + write-once blob + evidence.evidence_hash)
  -> parse   (registry atomic parsers: messaging/transcript/chat; one record per message, never blend)
  -> store   (analysis.normalized_record in Postgres = relational SSOT)
  -> knowledge (embed bge-m3 -> Milvus casebible_evidence)
  -> [graph, Part 3] Graphiti / Neo4j (group_id=casebible)
```
Entry points already in the repo to reuse (do NOT rebuild): `evidence/cli.py` (`evidence` CLI), the
`run_chat_transcript` / `sms-xml` / messaging workflows in `evidence/workflows.py`, and the parser registry in
`evidence/registry.py` + `evidence/tools/`. So: **sort feeds files into `sorted/`; process imports from
`sorted/` by content-hash via the existing custody→parse→store→knowledge workflow.** Two boundaries to honor:
(1) **AI chats / Knowledge are NOT evidence** — they do not enter the custody/evidence schema (their home is
Milvus `casebible_ai_conversations`); evidence ingest takes `Evidence/**` (+ records/docs), not `Knowledge/**`.
(2) a **Semantica enrichment layer** may later be inserted *between parse and the stores* (see the platform's
`specs/SEMANTICA-PIPELINE-READ.md`) — out of scope for `evidence sort`; just be aware process is evolving.

---

## 8. CONFIG / env names (NO secret values — resolved at runtime via `cb_connect.py`)
| Name | Default / source | Purpose |
|---|---|---|
| `CB_PG_TUNNEL_PORT` | `15432` | local port for the SSH tunnel to enrichment PG |
| PG DSN | `host=127.0.0.1 port=<tunnel> dbname=casebible user=postgres password=<resolved>` | enrichment connect |
| PG password | `Backups/config/cb.env` OR `~/.secrets/casebible-databases.md` OR `CB_PG_PASSWORD` | never hard-coded |
| `CB_MILVUS_URI` | `http://100.119.96.29:19530` | Context Corpus vectors |
| `CB_MILVUS_TOKEN` | `root:Milvus` | Milvus auth |
| `CB_MILVUS_COLLECTION` | `casebible_ai_conversations` | SORT's collection (AI chats / context) |
| `R2_CATALOG_TOKEN` | `~/.secrets/cloudflare.env` OR env | R2 Iceberg catalog |
| `LOCAL_DUCKDB` | `D:/casebible/casebible.duckdb` | dedup md5 snapshot (`r2_files`) |
| `CB_WORK_DB` | `D:/casebible/casebible_work.sqlite` | durable working/registry store |
| `CB_STAMP` | env (scripts must NOT call `Date.now`) | ledger filename stamp |
| rclone remote | `r2:` (rclone config) | S3 R2 access; R2 R/W creds in rclone config / `CB_R2_*` env |

SSH tunnel to enrichment PG (prerequisite before any classification run — **owner's box only; you can't do this**):
`ssh -i ~/.ssh/ovh -N -L 15432:172.18.0.3:5432 ubuntu@100.91.190.107` (container IP can drift → re-derive with
`cb_refresh_dsn.sh` on ovh2).

---

## Ground truth (verify-before-claiming)
Executed root-pile run: **364** content files COPIED raw→sorted (13 top-level type folders) + **35** junk→quarantine;
raw root INTACT at 401 objects; **0 deletes, 0 errors**; 195 `needs_review` routed+tagged in place. Full-corpus
re-bucket (executed 2026-06-27): **9,321** non-quarantine copies + **10** both-model-confirmed junk; raw untouched.
Existing sorted content was UNCHANGED (additive only).

## Notes for the build
- **CI gate (`main`): ruff + mypy + pytest must stay green.** Type-annotate `evidence/sort.py`; keep imports light.
- **Dry-run first:** `evidence sort --dry-run` writes the proposal ledger, performs NO `rclone` ops.
- **Tests:** fake-filesystem unit tests for the classifier (`classify`), the dedup ranker, the `rel_tail`
  stripper, and idempotent resume — no real R2 / `D:` access in tests.
- **Reuse, don't rebuild:** custody's sha256 hashing, the `evidence` CLI shell, and the registry/workflow spine.
- **ASSERT ZERO `new_path` COLLISIONS before any copy (HARD REQ).** Build the full proposed copy set, then
  fail (or auto-disambiguate per §5) if any two surviving rows map to the same `new_path`. Never let two
  distinct sources `rclone copyto` the same dest key — that silently overwrites (a real bug in the manual run:
  2,632 files raced, incl. evidence). Add a unit test that two same-basename inputs in one `(Type,sub)` produce
  two distinct dests, and a test that the collision-assert fires on a crafted duplicate.
- Open a **PR** for review; do not merge. The owner runs the tool on the Windows box (R2 mount + `D:/backup`).
