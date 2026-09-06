# Documentation consolidation audit — taxonomy, systems diagnosis, and the move manifest

> _Byline: Claude Code · Opus 5 · 2026-09-05_
> _(Session began 2026-09-05; completed across the 09-05/09-06 boundary. Analyst pass. A second
> agent — the MOVER — executes §9 from this file. A third agent was concurrently renaming names
> inside existing docs; this pass created new files only and edited nothing.)_

**STATUS: ITERATING — NOT DONE. Done only when the owner says so.**

Companions produced by this pass:
- `docs/consolidated/OPEN-WORK-REGISTER-2026-09-05.md` — 101 open items, 21 done-but-never-closed.
- `docs/consolidated/RETIRED-SYSTEMS-KNOWLEDGE.md` — the salvaged facts from retired systems.

---

## 0 · The owner's directive, and what this pass did with it

> *"Clear up that goddamn documentation folder. Ensure that if it's pushed aside or archived or
> moved out of the working space that everything has been completed. Not all been completed — it
> needs to be recompiled into a new document. Clean up anything stale; if it's a system we're no
> longer using but still has relevant information, it needs to be recompiled into the new system.
> Think beyond right now. Think in systems."*

Four instructions, four deliverables:

| Instruction | Deliverable |
|---|---|
| "clear up the folder" | §9 move manifest — machine-readable, executable verbatim |
| "ensure everything has been completed" before moving | The gate in §8: **nothing moves until its open items are in the register** |
| "not all been completed — recompile into a new document" | `OPEN-WORK-REGISTER-2026-09-05.md` |
| "a system we're no longer using but still has relevant information → recompile" | `RETIRED-SYSTEMS-KNOWLEDGE.md` |
| "think in systems" | §2 — the loop, the archetype, and the intervention |

### The size of the thing

| | Files | Bytes |
|---|---|---|
| `docs/` total | **1,337** (1,065 `.md`) | **56.5 MB** |
| `docs/wiki/` | 580 (43%) | 24.5 MB (43%) |
| `docs/reports/` | 151 | 10.1 MB |
| `docs/research/` | 31 | 9.3 MB |
| `docs/planning/` | 157 | 4.2 MB |
| `docs/reviews/` | 137 | 2.2 MB |
| `docs/awaiting-verification/` | 78 | 1.5 MB |
| `docs/adr/` | 63 | 0.34 MB |
| `docs/` root | 60 | ~1.6 MB |
| everything else | 80 | ~2.7 MB |
| **`docs/archive/`** | **1** (its own README) | **1 KB** |

That last row is the finding in miniature. The archive was built on 2026-08-18 and **has never
been used once**.

---

## 1 · First principles — what is a doc FOR in this repository?

Before deciding what to move, decide what a document *is*. Seven types, each with a different
lifecycle. A document that cannot be assigned a type is, by that fact alone, a problem.

| Type | Purpose | Written when | Ends when | Archivable? |
|---|---|---|---|---|
| **CANON** | States current truth. `PROJECT_CANON`, `INDEX`, `REPO_STRUCTURE`, `CONVENTIONS`, `NAMING`, `glossary` | Continuously amended | Never — it is amended, not retired | **Never** |
| **DECISION** | Records an irreversible choice and its reasoning. ADRs, `DECISION_LOG` | At the moment of ruling | Never — superseded in place with a banner | **Never** |
| **REGISTER** | Tracks a live set of open things. `URGENT-TODO`, `DEBT`, `DOC_DEBT`, `SETTLED`, `GUARD-TRIGGER-DISPOSITION`, `CHANGE-ORDER`, `MASTER-TODO`, `COORDINATION` | Once; appended forever | When the set is empty *and* declared closed | **Never while non-empty** |
| **PLAN** | Proposes future work. `docs/plans/**`, `docs/planning/**` | Before the work | When the work lands **or** the premise dies | **Yes — once its open items are in a register** |
| **REVIEW** | Records what was observed at a moment. `docs/reviews/**`, audits, pre-mortems, receipts | After the work | Immediately — a review is a photograph | **Yes — but it is evidence; keep it, don't delete it** |
| **HANDOFF** | Transfers state between sessions. `HANDOFF-*.md`, compact summaries | At a session boundary | When the next session picks it up | **Yes — fastest-decaying type in the tree** |
| **REFERENCE** | Explains a stable external or internal fact. `reference/`, `runbooks/`, `schemas/`, `wiki/` | Once | When the thing it describes changes | **Only if its subject is gone** |

### The lifecycle rule that was missing

Every type above has a natural end **except CANON, DECISION, and REGISTER**. The repo has
excellent discipline for those three and almost none for the other four. PLAN, REVIEW, HANDOFF
and stale REFERENCE accumulate without limit because **nothing in the process says who retires
them or when**. `docs/archive/README.md` states the rule correctly —

> "When a task is completed or superseded, remove it from the active TODO/current handoff and
> move it here **in the same completion change**."

— and that rule has been followed **zero times in 18 days**.

---

## 2 · Systems diagnosis

### 2.1 The loop

```
              ┌─────────────────────────────────────────────┐
              │                                             │
              ▼                                             │
   a decision changes                                       │
              │                                    the next reader cannot
              ▼                                    tell current from stale
   the NEW doc is written                                   ▲
   (fast, satisfying, rewarded)                             │
              │                                             │
              ▼                                             │
   the OLD doc is left in place ──────► doc count grows ────┘
   (retiring it is slow, risky,          (1,337 files)
    unrewarded, and might break
    a link nobody has mapped)
                     │
                     ▼
          SYMPTOMATIC FIX: write an INDEX / a manifest
          / a purgatory folder / a naming register
          to tell readers which docs are current
                     │
                     ▼
          pressure relieved ──► the fundamental fix
          (actually retiring the doc) is never done
                     │
                     ▼
          the index itself becomes one more doc to maintain
          ──► back to the top, with a larger corpus
```

### 2.2 The archetype: **Shifting the Burden**, with a *Fixes that Fail* inner loop

**Shifting the Burden** is the primary structure. The problem symptom is *"readers cannot tell
current truth from stale truth."* The fundamental solution is *retire the stale doc*. The
symptomatic solution is *add a pointer that says which one is current.* The symptomatic solution
works immediately, so it is always the one taken — and each application **atrophies the
fundamental capability further**, because the pointer layer makes the mess survivable.

The evidence is four generations of the same symptomatic fix, none of which retired a single file:

| Gen | Date | Artifact | What it did | Files retired |
|---|---|---|---|---|
| 1 | 2026-06-13 | `docs/DOC_DEBT.md` | A register of undocumented things | 0 |
| 2 | 2026-08-15 | `docs/INDEX.md` + `DOC_CLEANUP_MANIFEST-2026-08-15.md` | "Entry-point repair complete; **quarantine still proposed — no files moved or deleted**" | **0** |
| 3 | 2026-08-18 | `docs/awaiting-verification/` + `docs/archive/` | A purgatory tree where "every item is `UNVERIFIED`" | 0 promoted, 0 archived |
| 4 | 2026-09-01 | `docs/CLAIMED_COMPLETE_LIKELY_LIES/` + `awaiting-verification-inventory-20260901.md` | Full dispositions for 75 files, "report-only; owner rules on each" | **0** |
| 5 | 2026-09-02 | `docs/registers/SETTLED.md` | A keyword→ruling lookup index | 0 (correct — different problem) |

Generation 4 is the one that hurts: **a complete, correct, file-by-file disposition already
exists** and was never executed. This audit is generation 6. Its only claim to being different is
that it ends in an executable manifest and hands it to a different agent.

The **Fixes that Fail** inner loop is the pointer layer itself: each index/manifest/purgatory
folder is a document, so the fix increases the very quantity it was created to manage. Five
navigation artifacts now exist (`INDEX.md`, `HANDOFFS.md`, `AGENT_MEMORY.md`, `SETTLED.md`,
`awaiting-verification/README.md`), plus two brand-new ones from today (`NAMING.md`,
`RENAME-BLAST-RADIUS-2026-09-05.md`).

### 2.3 Why the fundamental fix keeps losing — the actual delay in the loop

It is not laziness. Three real forces:

1. **Retiring a doc has unbounded, unmapped risk.** Nobody knew what pointed at what. This pass
   measured it for the first time: **152 already-broken intra-`docs/` links** and **14 archive
   candidates referenced from live code, tests, SQL, or nested `AGENTS.md` files**. That fear was
   correct — the 2026-08-23 reorg *did* break `AGENTS.md`, `sql/bootstrap/platform_foundation.sql`
   and a test file by removing `docs/pending-review/`, and those pointers are still broken today.
2. **Archiving requires knowing whether the work finished.** Which requires reading the doc,
   cross-checking the decision log, and often checking live state. That is expensive. So it is
   deferred — and the doc stays.
3. **The rule lives in the wrong place.** `docs/archive/README.md` says retire-in-the-same-change.
   Nothing enforces it: no hook, no CI check, no checklist item in `CONVENTIONS.md`.

### 2.4 The leverage point

Not "archive harder." The leverage point is **making the fundamental fix cheap**, i.e. removing
delay (1) and (2) permanently:

- **(1) is now solved, mechanically.** §5 is a per-file inbound-reference map. It is regenerable
  in one command (`rg -l --fixed-strings <basename>` over the live set) and can become a CI check.
- **(2) is solved by the register.** Once an open item lives in
  `OPEN-WORK-REGISTER-2026-09-05.md`, archiving its source document is *information-preserving by
  construction*. That is why the register had to be written before the manifest, not after.
- **(3) needs the owner.** `OW-050`/`OW-051`/`OW-052` — the F2 hook, the F3 cite-before-propose
  test, the F4 recording convention — were designed on 2026-09-02 and **none was implemented**.
  Verified this pass: no `UserPromptSubmit` hook exists in `.claude/settings.json`, and neither
  `AGENTS.md` nor `CONVENTIONS.md` contains the F3/F4 text.

### 2.5 The connection to the ruling already on the books

This is the *documentation* sibling of a defect the repo already diagnosed on the *recall* side.
`docs/reviews/2026-09-02-relitigation-pattern-and-fix.md` §3 found that rulings were being
recorded fine and **recall** was the broken half: "Recall is exhortation, not enforcement… Nothing
intercepts a proposal that re-opens D-xxx." Same shape here: **retirement is exhortation, not
enforcement.** Per the recall rule, this audit does not re-open that diagnosis; it extends it to
document lifecycle and adopts its F1–F5 numbering by reference.

And D-142 (2026-09-05) supplies the owner's own triage principle, which applies to documents
exactly as it applies to schemas:

> Owner: *"trying to preserve shit that isn't actually there is what drove two weeks worth of
> bullshit with the databases… you need to remember that."* Ruling (2): *"no plan, pre-mortem,
> migration step, or 'keep this path for the data' caveat may be written to protect a stock that
> is empty. First question is always 'does that data exist yet?'"*

Applied to docs: **do not preserve a plan that guards work whose subject no longer exists.** Half
the ARCHIVE-CLEAN rows below are justified by that sentence.

---

## 3 · Inversion — what must NEVER be archived

Determined by asking what would break, not by judging quality. Everything below is referenced by
a machine-read or agent-read path.

| Never archive | Why — the exact dependency |
|---|---|
| `docs/DECISION_LOG.md` | `AGENTS.md`, `AGENT_MEMORY.md`, `docs/AGENT_MEMORY.md` (authority + watches), `server/tools/AGENTS.md`, `docs/awaiting-verification/AGENTS.md` |
| `docs/adr/**` (all 63 + README) | `AGENTS.md`, `README.md`, `AGENT_MEMORY.md`, `modules/traceIQ/traceiq-rebuild/AGENTS.md`; ADRs are superseded **in place**, never moved — ADR-0024's "Kept in full for provenance" is the model |
| `docs/PROJECT_CANON.md` | `AGENTS.md`, `README.md`, `AGENT_MEMORY.md`, `docs/AGENT_MEMORY.md` authority list |
| `docs/INDEX.md` | `AGENTS.md`, `README.md`, `AGENT_MEMORY.md`, `docs/AGENT_MEMORY.md` **watches list** — moving it breaks the freshness contract, not just a link |
| `docs/REPO_STRUCTURE.md`, `docs/CONVENTIONS.md`, `docs/DEBT.md`, `docs/COORDINATION.md` | `AGENTS.md` "Further Reading" |
| `docs/NAMING.md` | `AGENTS.md`, `AGENT_MEMORY.md`, `README.md` — **created today**; the rename lane depends on it |
| `docs/agent-memory/README.md` | `AGENTS.md` + `AGENT_MEMORY.md` declare it the memory format/precedence contract |
| `docs/AGENT_MEMORY.md` | The `docs/**` row of the root `AGENT_MEMORY.md` path router |
| `docs/HANDOFFS.md`, `docs/MEMORY_ARCHITECTURE.md` | `docs/AGENT_MEMORY.md` authority **and** watches lists |
| `docs/reference/HASH-TAXONOMY-2026-08-29.md` | Six nested `AGENTS.md` files: root, `server/`, `server/agents/`, `server/contracts/`, `server/evidence/`, `server/timeline/`, `server/tools/`, `server/tools/repair/`, `modules/engine/`, `modules/workbench/web/` |
| `docs/reference/CUSTODY-HASH-CANON.md` | Custody canon; paired with the taxonomy above |
| `docs/registers/SETTLED.md`, `RENAME-BLAST-RADIUS-2026-09-05.md` | `AGENTS.md`, `README.md` point at `docs/registers` |
| `docs/URGENT-TODO.md`, `docs/DOC_DEBT.md`, `docs/GUARD-TRIGGER-DISPOSITION.md`, `docs/CHANGE-ORDER.md`, `docs/MASTER-TODO-2026-08-18.md` | Live registers with non-empty open sets (see §1 lifecycle rule) |
| `docs/design/0061-unified-operator-surface/spec.md` | Companion to **Accepted** ADR-0061; named by `docs/INDEX.md` as the production composition |
| `docs/reviews/2026-08-25-schema-audit/{TIMESKETCH-FORK-CURATION-HANDOFF, TIMESKETCH-WP-E02-IMPLEMENTATION-STATUS, reconciliation-domains/R09-cross-store-reconciliation}.md` | `server/timeline/AGENTS.md` |
| `docs/reviews/2026-09-02-uiw-rehearsal-acquisition-seam.md` | `modules/engine/AGENTS.md` |
| `docs/planning/{operator-console-requirements, port-backlog, agno-chunking-strategy, facade-collapse-plan, gui-integration-spec}.md` | **Cited from live code, SQL, tests and scripts** — see §5. These are reference material by use, whatever their filename suggests. |
| `docs/recovered/**` | The only surviving record of the retired GraphRAG comparison lane; source `.py` files are gone |
| `docs/schema/`, `docs/schemas/` | Machine-consumed contracts (`catalog.json`, OpenAPI, JSON Schema variants) |
| `docs/semantica`, `docs/semantica-benchmarks` | Git **symlinks** (mode 120000) into `server/vendored/semantica/` — moving them breaks the alias |
| `docs/archive/README.md`, `docs/awaiting-verification/{README,AGENTS,CLAUDE}.md` | They govern the trees they sit in |

**Also never archived, for a different reason:** `docs/CLAIMED_COMPLETE_LIKELY_LIES/awaiting-verification-inventory-20260901.md`. It is generation 4's disposition ruling, still awaiting the owner. Archiving it would archive the decision this consolidation depends on.

---

## 4 · Classification — every file, one row

Rows are per-file for the decision-bearing working set and per-cluster for generated trees. Every
one of the 1,337 files is covered by exactly one row; the counts reconcile at the foot.

### 4.1 `docs/` root — 60 files, per-file

| File | Type | Class | Chesterton's fence — why it was put there |
|---|---|---|---|
| `PROJECT_CANON.md` | CANON | KEEP-CANON | The SSOT; §1 is the knowledge-horizon mechanism |
| `DECISION_LOG.md` | DECISION | KEEP-CANON | Append-only ruling ledger, D-001…D-142 |
| `INDEX.md` | CANON | KEEP-CANON | Generation-2 fix: routes current truth |
| `REPO_STRUCTURE.md` · `CONVENTIONS.md` · `glossary.md` · `NAMING.md` | CANON | KEEP-CANON | Named in `AGENTS.md` Further Reading / the rename lane |
| `AGENT_MEMORY.md` | CANON | KEEP-CANON | The `docs/**` memory router, with a freshness watch block |
| `MEMORY_ARCHITECTURE.md` | REFERENCE | KEEP-CANON | Authority row in `docs/AGENT_MEMORY.md` |
| `EVIDENCE_MERGE_MAP.md` | REFERENCE | KEEP-CANON | Cited by `BUILD_PLAN.md` as the capability inventory; annotated as late as 2026-08-23 |
| `OWNER-REVIEW-2026-08-18-verified-todo-audit.md` | REVIEW | KEEP-CANON | Independent verification of MASTER-TODO; cited from `INDEX.md` |
| `URGENT-TODO.md` | REGISTER | KEEP-LIVING | The loud stub/broken register; ~20 rows still OPEN |
| `DEBT.md` | REGISTER | KEEP-LIVING | Activation holds and technical debt |
| `DOC_DEBT.md` | REGISTER | KEEP-LIVING | 9 open rows (OW-062) |
| `CHANGE-ORDER.md` | REGISTER | KEEP-LIVING | Running change order; stalled at CH-21 (OW-060) |
| `COORDINATION.md` | REGISTER | KEEP-LIVING | Multi-chat lane ledger; 4 unchecked items |
| `MASTER-TODO-2026-08-18.md` | REGISTER | KEEP-LIVING | `INDEX.md`: "authoritative production resume ledger"; amended to 2026-08-30 |
| `GUARD-TRIGGER-DISPOSITION.md` | REGISTER | KEEP-LIVING | The 131 guard triggers in four buckets; makes the D-110 flag flip safe |
| `HANDOFFS.md` | REGISTER | KEEP-LIVING | R0–R14 packet router; a **watched** file in `docs/AGENT_MEMORY.md` |
| `BUILD_PLAN.md` | PLAN | KEEP-LIVING | `INDEX.md`'s "forward entry point"; content frozen at 2026-08-23, overdue a refresh |
| `HANDOFF-2026-08-18-evidence-operations-desk-mvp.md` | HANDOFF | KEEP-LIVING | `INDEX.md` Start-here row; body says "NOT COMPLETE — resume at step 1" |
| `HANDOFF-2026-08-29-agno-role-dissection.md` | HANDOFF | KEEP-LIVING | `INDEX.md` Start-here; current AgentOS-cutover authority |
| `HANDOFF-2026-08-29-derived-document-ingest-wiring.md` | HANDOFF | KEEP-LIVING | `INDEX.md` Start-here; WP-10/WP-11 still open (OW-017/018) |
| `UNRESOLVED-QUESTIONS-2026-08-16-surreal-investigation-phase0.md` | REGISTER | KEEP-LIVING | Self-declared "ACTIVE INVENTORY"; S1–S6 resolved by D-064, rest open |
| `n8n-model-and-node-notes.md` | REFERENCE | KEEP-LIVING | Live n8n 2.36.6 working notes with measured model results |
| `INFRASTRUCTURE.md` | REFERENCE | **RECOMPILE** | Predates Temporal, the n8n sandbox, and D-122's secrets broker; still describes the superseded Coolify-env-holds-secrets model |
| `INFRASTRUCTURE.template.md` | REFERENCE | **DUPLICATE** | Sanitized structural mirror of the above, same staleness. Survivor: `INFRASTRUCTURE.md` |
| `DOC_CLEANUP_MANIFEST-2026-08-15.md` | PLAN | **KEEP-LIVING** | Generation-2 artifact; **its five UNRESOLVED questions are OW-003** — do not archive the unexecuted manifest |
| `RULINGS-SHEET-2026-08-09.md` | DECISION | ARCHIVE-CLEAN | Title says "ALL RESOLVED"; recorded as D-042. `2026-09-02-relitigation` §3 names it as the artifact "built once, never maintained" — archive with that lesson attached |
| `ADR_RECONCILIATION.md` | REVIEW | ARCHIVE-CLEAN | Self-bannered "HISTORICAL PROPOSAL SWEEP — SUPERSEDED"; stops at ADR-0022. *(Referenced from `BUILD_PLAN.md` — see §5)* |
| `AGENT_CONTEXT_MERGE_PLAN.md` | PLAN | ARCHIVE-CLEAN | "PLAN — discovery complete, no files rewritten yet"; overtaken by the 2026-08-27 and 2026-09-01 restructures. Its 6 unchecked items are Case-Bible-scope (OW-list P4) |
| `INGESTION-READINESS-2026-08-23.md` | HANDOFF | ARCHIVE-CLEAN | Explicitly "written for tonight"; superseded by the 08-24 handoffs. *(Linked from `INDEX.md` — see §5)* |
| `Codex Goal — Horizon Swift MVP.md` | PLAN | ARCHIVE-CLEAN | Framed around "Waves 4–10, Agno retirement" as future; both ruled/executed (D-107) |
| `HANDOFF-2026-08-18-evidence-desk-backend.md` | HANDOFF | ARCHIVE-CLEAN | STATUS PARTIAL; superseded by the 08-24/27/29 chain |
| `HANDOFF-2026-08-24-ingest-testing.md` | HANDOFF | ARCHIVE-CLEAN | Superseded by the n8n-golive handoff written hours later. *(Referenced from `sql/AGENT_MEMORY.md` — see §5)* |
| `HANDOFF-2026-08-24-n8n-pipeline-golive.md` | HANDOFF | ARCHIVE-CLEAN | "One step from first run" — moot; n8n-as-Temporal-Activities is live (`d0b18f5`), OW-123 |
| `HANDOFF-2026-08-27-platform-development-takeover.md` | HANDOFF | ARCHIVE-CLEAN | Cold-start takeover superseded by the 08-29 pair |
| `create-new-agent.md` · `extend-agent.md` · `improve-agent.md` · `eval-and-improve.md` · `review-and-improve.md` | REFERENCE | ARCHIVE-CLEAN | **Upstream AgentOS template residue** (ADR-0001 "fresh build from skeleton"). They instruct editing `agents/<slug>.py` and link `../app/config.yaml`, `../compose.yaml`, `../railway.json` — none exist. Eval contract salvaged into `RETIRED-SYSTEMS-KNOWLEDGE.md` §5 |
| `COMPACT-SUMMARY-2026-08-18.md` | HANDOFF | **UNCLEAR** | **Diverged fragment** of the same log stream as its `awaiting-verification/summaries/` twin — merge before moving either (OW-146) |
| `COMPACT-SUMMARY-{2026-08-24,-08-29,-08-30,-09-02,-09-03}.md` | HANDOFF | ARCHIVE-CLEAN | PostCompact hook exhaust; 545 KB combined. **Untracked** — plain `mv`. `-09-03` is recent enough to be a working reference; move last |
| `URGENT-TODO.md.bak-{20260824b,c,d}` · `n8n-model-and-node-notes.md.bak-20260824` | — | ARCHIVE-CLEAN | Mechanical editor backups; content-distinct but superseded by the live file. Never delete |
| `TODO-SNAPSHOT-{2026-08-02,-03,-07,-12,-14}.json` | REGISTER | ARCHIVE-CLEAN | Point-in-time TODO dumps. **Untracked** — plain `mv` |
| `wiki.xxh3` | — | KEEP (ignore) | Checksum sidecar; `AGENTS.md` says ignore `*.xxh3` during discovery |
| `semantica` · `semantica-benchmarks` | REFERENCE | KEEP-CANON | Git symlinks into `server/vendored/semantica/` |

### 4.2 `docs/adr/` — 63 files

**All KEEP-CANON. Zero moves.** The tree is the repository's best-maintained asset: every retired
ADR carries a supersession banner, a "why it was reversed" paragraph, and an explicit list of
sub-decisions that survived (ADR-0028's rclone/MD5/quarantine set is the exemplar). Superseded ADRs
stay in place by definition.

### 4.3 Small high-signal directories — per-file

| Path | Files | Class | Note |
|---|---|---|---|
| `docs/agent-memory/README.md` | 1 | KEEP-CANON | Memory format/precedence contract |
| `docs/registers/` | 2 | KEEP-CANON | `SETTLED.md`, `RENAME-BLAST-RADIUS-2026-09-05.md` |
| `docs/reference/` | 4 | KEEP-CANON ×3, KEEP-LIVING ×1 | `parsers.md` (48 KB, byline 2026-07-11) needs a freshness check against the 11 live Go-gateway parsers |
| `docs/runbooks/` | 3 | KEEP-LIVING | `go-live-case-registry.md` is 2026-09-02; `MIGRATION-0036-CONTEXT-IMPORT.md` has **no byline** (OW-066) |
| `docs/schema/` + `docs/schemas/` | 11 | KEEP-CANON | Machine-consumed contracts; `catalog.json` is generated from live DB |
| `docs/design/` | 14 | KEEP-CANON | 2026-08-29/09-01 design sessions + the ADR-0061 spec. `classification-sentiment-test-system.md` has **no byline** (OW-066) |
| `docs/recovered/` | 6 | KEEP-CANON | Decompiled GraphRAG lane; the source `.py` files are gone |
| `docs/blueprint/` | 4 | **RECOMPILE** | 2026-08-11 three-layer blueprint; carries the stale "Milvus — DOWN" node (OW-057). `DOC_CLEANUP_MANIFEST` flagged the `docs/blueprint/` vs `.agents/blueprint/` canonical question in 2026-08-15 and it is **still open** (OW-003) |
| `docs/visualizations/` | 1 | ARCHIVE-CLEAN | Single generated artifact |
| `docs/CLAIMED_COMPLETE_LIKELY_LIES/` | 7 | KEEP-CANON ×4, UNCLEAR ×1, DUPLICATE ×2 | Chesterton's fence: someone parked docs whose completion claims were suspect. Keep the four validation/dispatch/inventory docs; `D-072-D-080-backfill.md` → ARCHIVE-CLEAN (**verified merged**, OW-125); the two 2026-08-30 Workbench "LIVE VERIFIED" claims stay quarantined until re-checked |

### 4.4 Cluster rows

| Cluster | Files | Bytes | Class | Chesterton's fence + disposition |
|---|---|---|---|---|
| `docs/wiki/project-docs/components/infrastructure/semantica/**` | 209 | 21.7 MB | **DUPLICATE** | A wholesale mirror of the vendored Semantica package's own docs, copied at repo genesis so they were browsable in the wiki. **Superseded by `docs/semantica` / `docs/semantica-benchmarks` symlinks**, which are the intended solution. Survivor: the symlinks |
| `docs/wiki/{INDEX.md, project-docs/{architecture,guides,proposals,references,specs}, skills/**, tools/**}` | ~330 | ~2 MB | **UNCLEAR** | `docs/wiki/INDEX.md:1-3` documents **"dial-stack — a production-grade agentic RAG system"** with AI-DIAL Core, Caddy, Dragonfly, LanceDB — a *different product*. Fence: it was imported as donor material for ADR-0022's deferred living wiki (`PROJECT_CANON.md:596` marks `docs/wiki/` "ADR-0022, deferred"). **Owner ruling needed** (OW-063) |
| `docs/wiki/tools/utility/**` | 12 | 24 KB | **DUPLICATE** | 10 byte-identical files vs `docs/wiki/project-docs/components/tools/scripts/**`; both born in the same 2026-06-13 commit. Survivor: `project-docs/components/tools/scripts/` (fits the taxonomy used everywhere else) |
| `docs/wiki/.plannotator/{plans,history}/**` | 105 | 1.2 MB | **UNCLEAR** | Third-party planning-tool cache. `history/` subdirectory names are sanitized paths of **other repositories** (`dial-stack`, `MCP_Tool_Platform`, `TheBigOne`, `Case Bible`). Nobody chose to store those here; it is a side-effect of where the tool ran (OW-065) |
| `docs/wiki/archive/**` | 27 | 265 KB | ARCHIVE-CLEAN | Already the designated stale mirror. **⚠ Contains the P0 credential exposure — OW-001. Redact/rotate before or during the move.** |
| `docs/wiki/_TO_BE_DELETED/repair-2026-03-31/**` | 3 | 4 KB | ARCHIVE-CLEAN | Already a quarantine bucket following the never-delete rule; leave the pattern, relocate the folder |
| `docs/reports/_stale/recovery-run1-203756/**` | 123 | 85 KB | ARCHIVE-CLEAN | Recovery run #1 stubs; many carry `e3b0c44298fc` (SHA-256 of the empty string) = failed recoveries. Superseded by `docs/reports/recovery/`. **Untracked (gitignored)** — plain `mv` |
| `docs/reports/recovery/**` + loose `docs/reports/*` | 27 | 10 MB | KEEP-LIVING | Current recovery output + skill inventories. `docs/reports/README.md`: "everything in this directory except this file is gitignored" — confirmed, 1 of 151 tracked |
| `docs/research/integration-audit-2026-08-24/**` | 28 | 9.1 MB | **RECOMPILE** | The six `lane-*.md` analyses are durable output; the two raw npm catalogs (6.3 MB + 2.0 MB JSONL) are scrape dumps that do not belong in a doc tree. `.duckdb/AGENTS.md` references one — see §5 |
| `docs/research/N8N-CAPABILITY-ASSESSMENT-2026-08-25.md` | 1 | 69 KB | KEEP-LIVING | Carries a stale Milvus claim (OW-057) |
| `docs/planning/` — 2026-09-03 ingest plans | 2 | 76 KB | KEEP-LIVING | Both carry `STATUS: ITERATING — NOT DONE`; amended 2026-09-05 |
| `docs/planning/` — v8.1-era build docs (`BUILD_TODO`, `EXECUTION_PLAN`, `MIGRATION_PLAN_v8`, `TOOL_SOURCES_INVENTORY`, `VERIFIED_AGNO_API`, `DEV_RESOURCES_INDEX`) | 6 | 90 KB | ARCHIVE-CLEAN | Each self-banners "Phases 1–9 are DONE… retained as build history"; ~50 unchecked boxes are ticks never applied to frozen docs (OW-133) |
| `docs/planning/` — superseded design docs (`facade-collapse-plan`, `sbv-fork-plan`, `sbv-mcp-integration-plan`, `repo-restructure-spec`, `graphiti-image-rebuild-plan`, `forensic-db-extension-…-addendum`, `conversation_ingestion_system_design`, `exec-tier-split`, `ovh-data-to-ovh-files-cutover`, `parser-iterations-inventory`, `Claude - chat pipeline for PostgreSQL - Claude.md`) | 11 | 350 KB | ARCHIVE-CLEAN | Each superseded by a named D-number or ADR (D-028, D-131, ADR-0033, D-070, D-069/070). Facts salvaged into `RETIRED-SYSTEMS-KNOWLEDGE.md` |
| `docs/planning/{operator-console-requirements, port-backlog, agno-chunking-strategy, gui-integration-spec}.md` | 4 | 84 KB | **KEEP — code-cited** | Referenced from `server/`, `sql/`, `tests/`, `scripts/`. See §5; do not move |
| `docs/planning/forensic-db-architecture/**` | 35 | 1.6 MB | ARCHIVE-CLEAN | The 91k-word SPEC-1 draft, never merged into canon; "⚠️ DRAFT — HUMAN-IN-THE-LOOP REVIEW REQUIRED". `DOC_CLEANUP_MANIFEST` already proposed quarantining it "only after extracting unique court-safety rationale" — that extraction is still owed |
| `docs/planning/forensic-db-reconciliation/**` | 34 | 1.4 MB | ARCHIVE-CLEAN | Records a real 2026-06-30 migration to a 93-table schema + 512-pattern behavior seed. **D-142 makes this pure history**: that database no longer exists |
| `docs/planning/chat-sample-analysis/**` | 22 | 312 KB | KEEP-CANON | "Nothing decided here — this maps what's actually IN the chats." A completed discovery snapshot over the owner's real corpus; irreplaceable and non-iterating |
| `docs/planning/architecture-directives/**` | 8 | 69 KB | **UNCLEAR** | Its `INDEX.md` says "ACTIVE design directives, not archived history" while every file says DRAFT / DESIGN-ONLY / not-deployed, three months and ~40 ADRs later (OW-107) |
| `docs/planning/goals-archive/**` + `ui-vision/` | 5 | 55 KB | ARCHIVE-CLEAN | Self-declared archive + one static mockup |
| `docs/plans/` — 2026-08-15 pre-mortems (`COURT-READINESS`, `EVIDENCE-CUSTODY-INSPECTION`, `MATTER-ACTIVATION-PREFLIGHT`, `MATTER-WORKBENCH`) | 4 | 20 KB | KEEP-CANON | Still the gating safety analyses for undeployed features (OW-037) |
| `docs/plans/MATTER-FOUNDATION-pre-mortem-2026-08-15.md` | 1 | 6 KB | **RECOMPILE** | STATUS "BUILT, HELD, UNAPPLIED" is **false** — 0026–0030 applied 2026-08-23 (OW-030). Needs a dated correction before it moves |
| `docs/plans/WAVE1-*` (7 files) | 7 | 113 KB | ARCHIVE-CLEAN | Doubly superseded: by their own R0 audit banner and by ADR-0059's per-source-clock redesign. 9 unchecked items registered |
| `docs/plans/R10-*` / `R11` / `R12` (7 files) | 7 | 33 KB | ARCHIVE-CLEAN | Surreal Phase-0 packet; rulings landed as D-064, then superseded by D-107/D-142 |
| `docs/plans/{MCP-GATEWAY-CHAIN-PHASE1, SEMANTICA-SWIFT-SLICE4, WEAVIATE-NATIVE-EVIDENCE-CUTOVER-RUNBOOK, N8N-BUILDER-AGENT-GUIDE, chat-ingest-pipeline}.md` | 5 | 39 KB | KEEP-CANON / KEEP-LIVING | Live activation gates (OW-035, OW-033, OW-015) and the owner's own n8n methodology |
| `docs/plans/{TEMPORAL-INTEGRATION-PLAN-2026-08-23, uiw-preview-contract}.md` | 2 | 21 KB | **RECOMPILE** | Temporal plan says "no decision recorded yet" — D-130 ruled it and it is live (OW-122); uiw-preview predates the rename and the 09-05 chain |
| `docs/plans/chat-ingest-before-after-visual.md` | 1 | 3 KB | ARCHIVE-CLEAN | One-shot explainer for a superseded migration |
| `docs/reviews/2026-09-0*` (current lane) | 13 | 200 KB | KEEP-CANON / KEEP-LIVING | Current truth. `2026-09-05-ingest-day-live-chain.md` is the newest consolidation and **wins over its four sources** |
| `docs/reviews/2026-09-0{4,5}` sources consolidated by the chain doc | 4 | 54 KB | KEEP-LIVING → archive after ratification | Their STATUS headers are already stale within 24 h (OW-042, OW-043) |
| `docs/reviews/2026-08-2*` (top level) | 24 | 190 KB | ARCHIVE-CLEAN ×15, RECOMPILE ×6, KEEP-CANON ×3 | Point-in-time receipts. The six RECOMPILE carry retired-architecture names (Authentik forward-auth, AgentOS, SBV-as-fork) and need superseded banners |
| `docs/reviews/2026-08-25-schema-audit/**` | 54 | 846 KB | ARCHIVE-CLEAN bulk / KEEP-CANON registers | The R00–R14 audit that produced GAP-001…034 against a database torn down twice since. Registers and TIMESKETCH handoffs stay (three are cited by `server/timeline/AGENTS.md`) |
| `docs/reviews/2026-08-23-cross-repo-evidence-audit/**` | 34 | 650 KB | ARCHIVE-CLEAN bulk / KEEP-CANON register | `ISSUES-AND-TODO.md` (47+ ISS ids) is a live register with no disposition pass (OW-069) |
| `docs/reviews/2026-08-31-external-reviews/**` | 5 | — | ARCHIVE-CLEAN | Superseded by `repo-rereview-validation-and-dispatch-2026-09-01.md`, which is the verdict on them |
| `docs/reviews/agent-tooling/**` | 2 | — | ARCHIVE-CLEAN | Two closed one-off hook repairs |
| `docs/awaiting-verification/**` | 78 | 1.5 MB | ARCHIVE-CLEAN ×48, RECOMPILE ×16, UNCLEAR ×4, KEEP-CANON ×3 (its own governance files), UNCLEAR ×1 (`COMPACT-SUMMARY-2026-08-18`) | Generation-3 purgatory. **Its disposition is OW-004 and is owner-gated**; the classification above adopts and refines the 2026-09-01 inventory rather than re-deriving it |
| `docs/archive/README.md` | 1 | 1 KB | KEEP-CANON | Governs the destination tree |

### 4.5 Reconciliation of counts

Files inside a cluster inherit that cluster's class; per-file rows override.

| Class | Files | Dominated by |
|---|---|---|
| KEEP-CANON | 156 | `adr/` 63 · `chat-sample-analysis/` 22 · `design/` 14 · `schema`+`schemas` 11 · `recovered/` 6 · canon/register roots |
| KEEP-LIVING | 69 | live registers at root · `reports/recovery` + loose reports 27 · current `reviews/2026-09-0*` |
| RECOMPILE | 59 | `research/integration-audit` 28 · `awaiting-verification` 16 · `reviews/2026-08-2*` 6 · `blueprint/` 4 |
| ARCHIVE-CLEAN | 486 | `reports/_stale` 123 · `reviews/` subdir bulk ~70 · `awaiting-verification` 48 · `planning/` ~60 · `wiki/archive` 27 · `plans/` ~20 |
| DUPLICATE | 224 | **`wiki/…/semantica/` mirror 209** · `wiki/tools/utility` 12 · 3 singles |
| UNCLEAR | 343 | **dial-stack wiki remainder ~224** · **plannotator cache 105** · `architecture-directives` 8 · 6 singles |
| **Total** | **1,337** | |

Three clusters — the Semantica mirror (209), the dial-stack wiki remainder (~224), and the
plannotator cross-project cache (105) — are **538 files, 40% of `docs/` by count and roughly 24 MB
by size.** None of them is this product's documentation. All three need **one owner ruling each**,
not more analysis. That is the shortest path from 1,337 files to something a person can read.

---

## 5 · Second-order effects — exactly what breaks, per file

Measured, not guessed. Two classes.

### 5.1 Breakage that already exists (pre-dating this consolidation)

These are the scar tissue of the 2026-08-23 reorg and are the empirical case for §6's pre-mortem.

| Broken pointer | Named from | Fix |
|---|---|---|
| `docs/pending-review/` (directory removed) | `AGENTS.md:354`; `sql/bootstrap/platform_foundation.sql:23,30,101`; `tests/test_0048_context_fingerprint_uiw_repair.py:19` | Repoint to `docs/awaiting-verification/` — the plan now lives at `docs/awaiting-verification/plans/apply-0036-set-role-patch.md` (OW-054) |
| `docs/reports/damaged-artifacts.jsonl` | `server/tools/repair/AGENTS.md:57`; `server/tools/repair/quarantine.py:53` | Verify intent — the dir is gitignored, so absence may be correct (OW-055) |
| `docs/reviews/2026-08-27-workbench-auth-rotation.md` | `modules/workbench/AGENT_MEMORY.md:9` | Locate or remove the row (OW-056) |
| 152 relative `.md` links inside `docs/**` | ~90 in `docs/wiki/**`, ~20 in `docs/awaiting-verification/**` | Sweep after the move (OW-053) |

### 5.2 Breakage this manifest would cause — and the required update, per file

**Every row here is a required edit paired with its move.** A move without its edit is a defect.

| File moved | Referenced from | Required update |
|---|---|---|
| `docs/INGESTION-READINESS-2026-08-23.md` | `docs/INDEX.md` "Start here" table row | Remove the row, or repoint to `docs/archive/2026/handoffs/` |
| `docs/ADR_RECONCILIATION.md` | `docs/BUILD_PLAN.md` | Repoint to the archive path |
| `docs/HANDOFF-2026-08-24-ingest-testing.md` | `sql/AGENT_MEMORY.md` | Repoint |
| `docs/create-new-agent.md`, `docs/extend-agent.md`, `docs/INFRASTRUCTURE.template.md` | `docs/registers/RENAME-BLAST-RADIUS-2026-09-05.md` | Update the path column (that register is a path inventory — it *must* stay accurate) |
| `docs/planning/sbv-fork-plan.md` | `docs/COORDINATION.md`; `docs/adr/0033-server-package-layout-repack.md` | **ADR citations are historical record — do NOT rewrite the ADR.** Add the new path in a dated footnote instead; update `COORDINATION.md` |
| `docs/planning/repo-restructure-spec.md` | `docs/adr/0033-server-package-layout-repack.md` | Same — footnote, not rewrite |
| `docs/planning/parser-iterations-inventory.md` | `docs/DECISION_LOG.md` | **Never rewrite the decision log.** Leave the citation; the archive path is discoverable via this audit |
| `docs/planning/BUILD_TODO.md` | `docs/planning/*` siblings only (no live referent) | None |
| `docs/planning/{EXECUTION_PLAN, MIGRATION_PLAN_v8, TOOL_SOURCES_INVENTORY, VERIFIED_AGNO_API, DEV_RESOURCES_INDEX}.md` | no live referent | None |
| `docs/planning/{graphiti-image-rebuild-plan, sbv-mcp-integration-plan, ovh-data-to-ovh-files-cutover, conversation_ingestion_system_design, forensic-db-extension-…, exec-tier-split-2026-07-19}.md` | no live referent | None |
| `docs/{AGENT_CONTEXT_MERGE_PLAN, RULINGS-SHEET-2026-08-09, Codex Goal — Horizon Swift MVP, HANDOFF-2026-08-18-evidence-desk-backend, HANDOFF-2026-08-24-n8n-pipeline-golive, HANDOFF-2026-08-27-platform-development-takeover}.md` | no live referent | None |
| `docs/improve-agent.md`, `docs/eval-and-improve.md`, `docs/review-and-improve.md` | no live referent | None |
| `docs/research/integration-audit-2026-08-24/npm-community-node-catalog.jsonl` | `.duckdb/AGENTS.md` | Repoint **before** moving, or leave the two raw catalogs in place |
| **`docs/planning/operator-console-requirements.md`** | `tests/test_custody.py`, `tests/test_knowledge_handle.py`, `sql/0006_*.sql`, `sql/0007_*.sql`, `server/api/run_routes.py`, `server/api/inspect_routes.py`, `server/evidence/custody.py`, `modules/workbench/api/app/types/inspect.py` | **DO NOT MOVE.** Eight live code/SQL/test citations |
| **`docs/planning/port-backlog.md`** | `server/analysis/patterns.py`, `server/tools/gateway/__init__.py`, `scripts/annotate-plans.sh`, `docs/HANDOFFS.md` | **DO NOT MOVE** |
| **`docs/planning/agno-chunking-strategy.md`** | `server/analysis/chunking_policy.py`, `server/analysis/chonkie_chunkers.py`, `docs/adr/0050-*.md`, `docs/DECISION_LOG.md` | **DO NOT MOVE** |
| **`docs/planning/facade-collapse-plan.md`** | `server/agents/AGENTS.md`, `docs/BUILD_PLAN.md`, `docs/COORDINATION.md`, `docs/DECISION_LOG.md` | **DO NOT MOVE** |
| **`docs/planning/gui-integration-spec.md`** | `scripts/annotate-plans.sh`, `docs/HANDOFFS.md`, `docs/DECISION_LOG.md` | **DO NOT MOVE** — also UNCLEAR (OW-100) |

### 5.3 Non-obvious second-order effects

1. **`docs/AGENT_MEMORY.md` has a freshness `watches` block** naming `INDEX.md`, `PROJECT_CANON.md`, `DECISION_LOG.md`, `HANDOFFS.md` with a `watches_hash: 8b31043`. Editing `INDEX.md` (which §9 requires) **invalidates that hash**. The mover must refresh `last_verified` / `watches_hash` in the same change or the memory router silently reports stale.
2. **`docs/reports/**` and `docs/recovered/**` are gitignored.** `git mv` fails on untracked paths. 150 of 151 report files and 5 of 6 recovered files need a plain `mv`. Getting this wrong looks like a permissions error and invites a retry loop.
3. **`docs/semantica` and `docs/semantica-benchmarks` are symlinks (mode 120000).** Never move; a copy or a naive move breaks the alias into `server/vendored/`.
4. **Archiving does not remove secrets from git history** (OW-001). The move is not the remediation.
5. **A concurrent agent is editing `AGENTS.md`, `INDEX.md`, `README.md`, `PROJECT_CANON.md` and ~30 others** for the rename. The mover must re-read before editing and stage by explicit path — never `git add -A`.

---

## 6 · Pre-mortem — it is 2026-09-20 and this consolidation made things worse. Why?

| # | Failure | Likelihood | Mechanism | Countermeasure in this plan |
|---|---|---|---|---|
| 1 | **Nothing moved.** A sixth artifact joined the pile. | **HIGH — it is the base rate: 5 for 5** | The manifest reads as a proposal, the owner is busy, the session ends | §9 is executable verbatim by a different agent; Batch A needs **no owner input** |
| 2 | **An unfinished plan was archived and its tasks vanished.** | HIGH without the gate | Archiving is only safe if the open items were extracted, and extraction is expensive | The register is the **precondition**, not the report. §8 check 3 is mechanical |
| 3 | **Lossy recompilation** — a decision got paraphrased into something subtly different. | MEDIUM | Summarising is the natural writing mode | `RETIRED-SYSTEMS-KNOWLEDGE.md` **quotes with `path:line`** and never paraphrases a decision |
| 4 | **A live pointer broke**, exactly as `docs/pending-review/` did. | MEDIUM | Nobody maps inbound references before moving | §5.2 is a per-file map; §8 check 2 re-runs it |
| 5 | **Code-cited planning docs were archived** because their directory looked historical. | MEDIUM-HIGH | `docs/planning/` *sounds* archivable | Five files carry an explicit **DO NOT MOVE** in §5.2 and are excluded from §9 |
| 6 | **The `COMPACT-SUMMARY-2026-08-18` split lost the `09:23`–`10:38` entries.** | MEDIUM | Two files, same name, diverged content — a de-dupe reflex deletes one | OW-146; §9 **excludes both** pending a merge |
| 7 | **Secrets were spread, not contained** — the credential file was archived and forgotten. | MEDIUM | Archiving feels like handling it | OW-001 is P0 and §9 Batch C **blocks** that path until the owner rules |
| 8 | **The register itself became the seventh competing ledger.** | MEDIUM | A new ledger duplicating `URGENT-TODO`/`DEBT` drifts within a week | The register's Scope Boundary makes P4 explicit **pointer rows**, not copies |
| 9 | **An "already done" item was archived and it was not actually done.** | LOW-MEDIUM | Trusting a STATUS line | Three corrections were caught this pass by **reading the code, not the doc** (OW-142, OW-126/127, OW-128) |
| 10 | **A rename-lane conflict** clobbered the concurrent agent's edits. | MEDIUM | Two agents editing `INDEX.md` in one worktree | §8 check 6: re-read before editing; stage by explicit path; never `git add -A` |
| 11 | **`git mv` failed on gitignored trees** and the mover force-deleted instead. | LOW | Untracked-path error misread | §5.3(2) and §9's Batch D use plain `mv`; **never** `rm` |
| 12 | **The freshness watch broke silently.** | LOW-MEDIUM | `watches_hash` not refreshed after editing `INDEX.md` | §5.3(1); §8 check 5 |

**The single most likely failure is #1.** Everything else assumes something happened.

---

## 7 · Kepner-Tregoe decision table for the hard cases

Weights: **Preserve information** ×5 · **Reduce reader confusion** ×4 · **Avoid breakage** ×4 · **Owner effort** ×3 · **Reversibility** ×2. Scores 1–5.

### Case A — `docs/wiki/` (580 files, 24.5 MB, another product's wiki)

| Option | Preserve ×5 | Confusion ×4 | Breakage ×4 | Owner effort ×3 | Revers. ×2 | Total |
|---|---|---|---|---|---|---|
| Leave in place | 5 (25) | 1 (4) | 5 (20) | 5 (15) | 5 (10) | **74** |
| Move whole tree → `docs/archive/2026/wiki-dial-stack-donor/` | 5 (25) | 5 (20) | 4 (16) | 4 (12) | 5 (10) | **83** |
| Split: keep platform-relevant, archive dial-stack | 4 (20) | 4 (16) | 3 (12) | 1 (3) | 3 (6) | **57** |
| Delete | 1 (5) | 5 (20) | 3 (12) | 5 (15) | 1 (2) | **54** — *violates never-delete; listed only for completeness* |
| **Move to a workspace sibling, out of the repo** | 5 (25) | 5 (20) | 3 (12) | 2 (6) | 4 (8) | **71** |

**Recommendation: move the whole tree to `docs/archive/2026/wiki-dial-stack-donor/` (83).** It stays in the repo, stays findable for ADR-0022's eventual build, stops competing with real docs, and is one command. The split option loses badly on owner effort for a marginal gain. **Owner-gated (OW-063)** because it touches 43% of `docs/`.

### Case B — `docs/awaiting-verification/` (78 files, purgatory since 2026-08-18)

| Option | Preserve ×5 | Confusion ×4 | Breakage ×4 | Owner effort ×3 | Revers. ×2 | Total |
|---|---|---|---|---|---|---|
| Leave as purgatory | 5 (25) | 1 (4) | 5 (20) | 5 (15) | 5 (10) | **74** |
| Execute the 2026-09-01 inventory verbatim (13 archive / 37 quarantine / 25 keep) | 5 (25) | 5 (20) | 4 (16) | 3 (9) | 4 (8) | **78** |
| Move the whole tree to archive as-is | 5 (25) | 4 (16) | 4 (16) | 5 (15) | 5 (10) | **82** |
| Verify all 78 first, then dispose | 5 (25) | 5 (20) | 5 (20) | 1 (3) | 4 (8) | **76** |

**Recommendation: move the whole tree to `docs/archive/2026/awaiting-verification/` as-is (82)**, preserving its `README.md` UNVERIFIED banner in place. Rationale: the tree is *already* declared unverified, so archiving changes nothing about its epistemic status — it only stops it competing for attention in the working set. The 2026-09-01 per-file inventory travels with it and remains executable later at zero cost. This is the cheap move that generation 3 and 4 both missed. **Owner-gated (OW-004).**

### Case C — the five `docs/*-agent.md` AgentOS template files

| Option | Preserve ×5 | Confusion ×4 | Breakage ×4 | Owner effort ×3 | Revers. ×2 | Total |
|---|---|---|---|---|---|---|
| Leave | 5 (25) | 1 (4) | 5 (20) | 5 (15) | 5 (10) | **74** |
| **Archive, after salvaging the eval contract** | 5 (25) | 5 (20) | 5 (20) | 5 (15) | 5 (10) | **90** |
| Rewrite for the current stack | 5 (25) | 5 (20) | 5 (20) | 1 (3) | 4 (8) | **76** |

**Recommendation: archive (90).** They actively mislead — they instruct editing `agents/<slug>.py` and link three files that do not exist. Their one durable fact (the `AgentAsJudgeEval` / `ReliabilityEval` contract) is salvaged into `RETIRED-SYSTEMS-KNOWLEDGE.md` §5. **This is Batch A — no owner input needed.**

### Case D — `docs/planning/` docs cited from live code

| Option | Preserve ×5 | Confusion ×4 | Breakage ×4 | Owner effort ×3 | Revers. ×2 | Total |
|---|---|---|---|---|---|---|
| **Leave in place, reclassify as REFERENCE** | 5 (25) | 3 (12) | 5 (20) | 5 (15) | 5 (10) | **82** |
| Archive + update all 19 code citations | 5 (25) | 4 (16) | 2 (8) | 2 (6) | 3 (6) | **61** |
| Move to `docs/reference/` + update citations | 5 (25) | 5 (20) | 2 (8) | 2 (6) | 3 (6) | **65** |

**Recommendation: leave in place (82).** Chesterton's fence, decisively: code cites them because
they *are* the rationale record for that code. A doc under `docs/planning/` that eight code sites
depend on is misfiled, not stale — and misfiling is a cheaper problem than a broken citation.
Reclassify in `REPO_STRUCTURE.md` when convenient.

---

## 8 · Proof checklist the MOVER must satisfy

Run **all** of these and paste the output. Do not report success from any subset.

```bash
cd E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform

# 1 — INDEX.md has no dead links
rg -o '\]\(([^)]+)\)' -r '$1' docs/INDEX.md | while read -r l; do
  case "$l" in http*|\#*) continue;; esac
  t="docs/${l%%#*}"; [ -e "$t" ] || echo "DEAD in INDEX.md: $l"
done

# 2 — no AGENTS.md / AGENT_MEMORY.md / CLAUDE.md / README.md / hook path is broken
rg -o --no-filename 'docs/[A-Za-z0-9_./-]+\.(md|json|yaml|html|sql|csv|jsonl)' \
   AGENTS.md AGENT_MEMORY.md CLAUDE.md README.md \
   $(git ls-files '*AGENTS.md' '*AGENT_MEMORY.md' | grep -v vendored | grep -v modules/forks) \
   .claude/settings.json .claude/settings.local.json 2>/dev/null \
 | sort -u | while read -r p; do [ -e "$p" ] || echo "BROKEN REF: $p"; done

# 3 — every archived file's open items are in the register
#     for each basename moved, it must appear in the register OR have zero open-work rows
for f in $(git log -1 --name-only --diff-filter=R --format= | grep '^docs/archive/'); do
  b=$(basename "$f")
  rg -q --fixed-strings "$b" docs/consolidated/OPEN-WORK-REGISTER-2026-09-05.md \
    || echo "UNREGISTERED ARCHIVE: $f"
done

# 4 — each archived filename appears only in archive/, the audit, the register, or the glossary
for b in <each moved basename>; do
  rg -l --fixed-strings "$b" . -g '!.git' -g '!.claude/memories/**' \
     -g '!modules/forks/**' -g '!server/vendored/**' \
   | grep -vE 'docs/archive/|2026-09-05-docs-consolidation-audit|OPEN-WORK-REGISTER|RETIRED-SYSTEMS-KNOWLEDGE|RENAME-BLAST-RADIUS|docs/NAMING.md' \
   && echo "^^ residual references to $b"
done

# 5 — the docs memory freshness watch was refreshed if INDEX.md changed
git diff --name-only HEAD~1 | grep -q '^docs/INDEX.md$' \
  && rg -n 'watches_hash|last_verified' docs/AGENT_MEMORY.md

# 6 — nothing was deleted, and only intended paths were staged
git log -1 --diff-filter=D --name-only --format= | grep . && echo "!!! DELETIONS PRESENT — ABORT"
git log -1 --name-only --format= | grep -v '^docs/' && echo "!!! NON-docs PATH STAGED — REVIEW"

# 7 — the broken-link count did not increase
#     baseline at audit time: 152 broken intra-docs links
```

**Additional gates, non-mechanical:**

8. **`docs/archive/README.md` gained a `2026/` section** describing what landed and pointing at this audit.
9. **No file under `docs/wiki/archive/.planning/`** moved before OW-001 is ruled.
10. **Neither `COMPACT-SUMMARY-2026-08-18.md`** moved before OW-146's merge.
11. **`git status` shows no modification** to files the rename lane is holding, unless deliberately coordinated.

---

## 9 · MOVE MANIFEST

Destination convention: `docs/archive/<yyyy>/<category>/<filename>`, per
`docs/archive/README.md`'s lifecycle categories. **Batches are ordered; do not reorder.**

### Batch A — safe now, no owner input, no reference updates required

```
git mv docs/create-new-agent.md docs/archive/2026/agentos-template/create-new-agent.md
git mv docs/extend-agent.md docs/archive/2026/agentos-template/extend-agent.md
git mv docs/improve-agent.md docs/archive/2026/agentos-template/improve-agent.md
git mv docs/eval-and-improve.md docs/archive/2026/agentos-template/eval-and-improve.md
git mv docs/review-and-improve.md docs/archive/2026/agentos-template/review-and-improve.md
git mv docs/AGENT_CONTEXT_MERGE_PLAN.md docs/archive/2026/plans/AGENT_CONTEXT_MERGE_PLAN.md
git mv docs/RULINGS-SHEET-2026-08-09.md docs/archive/2026/plans/RULINGS-SHEET-2026-08-09.md
git mv "docs/Codex Goal — Horizon Swift MVP.md" "docs/archive/2026/plans/Codex Goal — Horizon Swift MVP.md"
git mv docs/HANDOFF-2026-08-18-evidence-desk-backend.md docs/archive/2026/handoffs/HANDOFF-2026-08-18-evidence-desk-backend.md
git mv docs/HANDOFF-2026-08-24-n8n-pipeline-golive.md docs/archive/2026/handoffs/HANDOFF-2026-08-24-n8n-pipeline-golive.md
git mv docs/HANDOFF-2026-08-27-platform-development-takeover.md docs/archive/2026/handoffs/HANDOFF-2026-08-27-platform-development-takeover.md
git mv docs/URGENT-TODO.md.bak-20260824b docs/archive/2026/backups/URGENT-TODO.md.bak-20260824b
git mv docs/URGENT-TODO.md.bak-20260824c docs/archive/2026/backups/URGENT-TODO.md.bak-20260824c
git mv docs/URGENT-TODO.md.bak-20260824d docs/archive/2026/backups/URGENT-TODO.md.bak-20260824d
git mv docs/n8n-model-and-node-notes.md.bak-20260824 docs/archive/2026/backups/n8n-model-and-node-notes.md.bak-20260824
git mv docs/planning/BUILD_TODO.md docs/archive/2026/planning/BUILD_TODO.md
git mv docs/planning/EXECUTION_PLAN.md docs/archive/2026/planning/EXECUTION_PLAN.md
git mv docs/planning/MIGRATION_PLAN_v8.md docs/archive/2026/planning/MIGRATION_PLAN_v8.md
git mv docs/planning/TOOL_SOURCES_INVENTORY.md docs/archive/2026/planning/TOOL_SOURCES_INVENTORY.md
git mv docs/planning/VERIFIED_AGNO_API.md docs/archive/2026/planning/VERIFIED_AGNO_API.md
git mv docs/planning/DEV_RESOURCES_INDEX.md docs/archive/2026/planning/DEV_RESOURCES_INDEX.md
git mv docs/planning/graphiti-image-rebuild-plan.md docs/archive/2026/planning/graphiti-image-rebuild-plan.md
git mv docs/planning/sbv-mcp-integration-plan.md docs/archive/2026/planning/sbv-mcp-integration-plan.md
git mv docs/planning/ovh-data-to-ovh-files-cutover.md docs/archive/2026/planning/ovh-data-to-ovh-files-cutover.md
git mv docs/planning/exec-tier-split-2026-07-19.md docs/archive/2026/planning/exec-tier-split-2026-07-19.md
git mv docs/planning/conversation_ingestion_system_design.md docs/archive/2026/planning/conversation_ingestion_system_design.md
git mv docs/planning/forensic-db-extension-and-reconciliation-addendum.md docs/archive/2026/planning/forensic-db-extension-and-reconciliation-addendum.md
git mv "docs/planning/Claude - chat pipeline for PostgreSQL - Claude.md" "docs/archive/2026/planning/Claude - chat pipeline for PostgreSQL - Claude.md"
git mv docs/planning/goals-archive docs/archive/2026/planning/goals-archive
git mv docs/plans/chat-ingest-before-after-visual.md docs/archive/2026/plans/chat-ingest-before-after-visual.md
git mv docs/plans/WAVE1-pre-mortem-2026-08-14.md docs/archive/2026/plans/WAVE1-pre-mortem-2026-08-14.md
git mv docs/plans/WAVE1-subplan-2026-08-14.md docs/archive/2026/plans/WAVE1-subplan-2026-08-14.md
git mv docs/plans/WAVE1-W1.2-pre-mortem-2026-08-14.md docs/archive/2026/plans/WAVE1-W1.2-pre-mortem-2026-08-14.md
git mv docs/plans/WAVE1-W1.3-pre-mortem-2026-08-14.md docs/archive/2026/plans/WAVE1-W1.3-pre-mortem-2026-08-14.md
git mv docs/plans/WAVE1-W1.4-pre-mortem-2026-08-14.md docs/archive/2026/plans/WAVE1-W1.4-pre-mortem-2026-08-14.md
git mv docs/plans/WAVE1-W1.5-pre-mortem-2026-08-14.md docs/archive/2026/plans/WAVE1-W1.5-pre-mortem-2026-08-14.md
git mv docs/plans/R10-PHASE0-P0.1-CONTRACTS-pre-mortem-2026-08-16.md docs/archive/2026/plans/R10-PHASE0-P0.1-CONTRACTS-pre-mortem-2026-08-16.md
git mv docs/plans/R10-PHASE0-P0.2-QUESTIONS-pre-mortem-2026-08-16.md docs/archive/2026/plans/R10-PHASE0-P0.2-QUESTIONS-pre-mortem-2026-08-16.md
git mv docs/plans/R10-PHASE0-P0.3-EVALUATION-pre-mortem-2026-08-16.md docs/archive/2026/plans/R10-PHASE0-P0.3-EVALUATION-pre-mortem-2026-08-16.md
git mv docs/plans/R10-PHASE0-P0.4-HORIZON-CANARY-pre-mortem-2026-08-16.md docs/archive/2026/plans/R10-PHASE0-P0.4-HORIZON-CANARY-pre-mortem-2026-08-16.md
git mv docs/plans/R10-PHASE0-P0.5-OWNER-PACKET-pre-mortem-2026-08-16.md docs/archive/2026/plans/R10-PHASE0-P0.5-OWNER-PACKET-pre-mortem-2026-08-16.md
git mv docs/plans/R11-PHASE0-OWNER-RULINGS-pre-mortem-2026-08-16.md docs/archive/2026/plans/R11-PHASE0-OWNER-RULINGS-pre-mortem-2026-08-16.md
git mv docs/plans/R12-PHASE1-DISPOSABLE-SLICE-pre-mortem-2026-08-16.md docs/archive/2026/plans/R12-PHASE1-DISPOSABLE-SLICE-pre-mortem-2026-08-16.md
git mv docs/reviews/2026-08-31-external-reviews docs/archive/2026/reviews/2026-08-31-external-reviews
git mv docs/reviews/agent-tooling docs/archive/2026/reviews/agent-tooling
git mv docs/CLAIMED_COMPLETE_LIKELY_LIES/D-072-D-080-backfill.md docs/archive/2026/plans/D-072-D-080-backfill.md
```

**Batch A reference updates: NONE.** Verified by inbound-reference scan over `AGENTS.md`,
`AGENT_MEMORY.md`, `CLAUDE.md`, `README.md`, all nested `AGENTS.md`, `docs/INDEX.md`, the canon
and register set, `docs/adr/`, `server/`, `modules/`, `sql/`, `scripts/`, `tests/`, and
`.claude/settings*.json`.

### Batch B — safe, but each move REQUIRES its paired edit

```
git mv docs/INGESTION-READINESS-2026-08-23.md docs/archive/2026/handoffs/INGESTION-READINESS-2026-08-23.md
#   EDIT docs/INDEX.md — remove or repoint the "Ingestion readiness" row in the Start-here table
git mv docs/ADR_RECONCILIATION.md docs/archive/2026/reviews/ADR_RECONCILIATION.md
#   EDIT docs/BUILD_PLAN.md — repoint the ADR_RECONCILIATION.md reference
git mv docs/HANDOFF-2026-08-24-ingest-testing.md docs/archive/2026/handoffs/HANDOFF-2026-08-24-ingest-testing.md
#   EDIT sql/AGENT_MEMORY.md — repoint the reference
git mv docs/planning/sbv-fork-plan.md docs/archive/2026/planning/sbv-fork-plan.md
#   EDIT docs/COORDINATION.md — repoint
#   DO NOT EDIT docs/adr/0033-*.md — append a dated footnote with the new path instead
git mv docs/planning/repo-restructure-spec.md docs/archive/2026/planning/repo-restructure-spec.md
#   DO NOT EDIT docs/adr/0033-*.md — dated footnote only
git mv docs/planning/parser-iterations-inventory.md docs/archive/2026/planning/parser-iterations-inventory.md
#   DO NOT EDIT docs/DECISION_LOG.md — the citation stays; the new path is discoverable here
git mv docs/INFRASTRUCTURE.template.md docs/archive/2026/reference/INFRASTRUCTURE.template.md
#   EDIT docs/registers/RENAME-BLAST-RADIUS-2026-09-05.md — update the path column
#   NOTE: also update that register for the five agentos-template files moved in Batch A
git mv docs/planning/forensic-db-architecture docs/archive/2026/planning/forensic-db-architecture
#   PRECONDITION: extract the unique court-safety rationale first (owed since DOC_CLEANUP_MANIFEST 2026-08-15)
git mv docs/planning/forensic-db-reconciliation docs/archive/2026/planning/forensic-db-reconciliation
#   NOTE: docs/planning/forensic-db-reconciliation/BEHAVIORAL_DETECTION_EXPLAINED.md and
#         migrations/0008_behavior_seed_pattern_analyzer.sql are cited elsewhere — grep and repoint
```

### Batch C — OWNER-GATED. Do not execute without an explicit ruling.

```
# OW-063 — 43% of docs/ by file count. KT recommendation: move whole (score 83).
git mv docs/wiki docs/archive/2026/wiki-dial-stack-donor
#   BLOCKED BY OW-001: docs/wiki/archive/.planning/** contains git-tracked credential literals.
#   Rotate/redact FIRST. Archiving does not remove them from git history.
#   EDIT docs/registers/RENAME-BLAST-RADIUS-2026-09-05.md and sweep the ~90 intra-wiki broken links.

# OW-004 — KT recommendation: move whole, as-is (score 82). README's UNVERIFIED banner travels with it.
git mv docs/awaiting-verification docs/archive/2026/awaiting-verification
#   BLOCKED BY OW-146 until COMPACT-SUMMARY-2026-08-18 is merged.
#   EDIT docs/INDEX.md ("Pending historical review" row) and AGENTS.md:354 (docs/pending-review/ → new path).

# OW-065 — cross-project planning-tool cache; belongs to whichever repo the tool calls home.
git mv docs/wiki/.plannotator docs/archive/2026/plannotator-cross-project-cache
#   Subsumed by the docs/wiki move above if that is approved first.

# OW-064 — 10 byte-identical files. Survivor: project-docs/components/tools/scripts/
git mv docs/wiki/tools/utility docs/archive/2026/duplicates/wiki-tools-utility
#   Subsumed by the docs/wiki move above if that is approved first.

# OW-107 — the directory claims ACTIVE; every file inside says DRAFT/not-deployed. Owner: active or archive?
git mv docs/planning/architecture-directives docs/archive/2026/planning/architecture-directives
```

### Batch D — untracked / gitignored: plain `mv`, NOT `git mv`

```
mkdir -p docs/archive/2026/summaries docs/archive/2026/snapshots
mv docs/COMPACT-SUMMARY-2026-08-24.md docs/archive/2026/summaries/
mv docs/COMPACT-SUMMARY-2026-08-29.md docs/archive/2026/summaries/
mv docs/COMPACT-SUMMARY-2026-08-30.md docs/archive/2026/summaries/
mv docs/COMPACT-SUMMARY-2026-09-02.md docs/archive/2026/summaries/
#   HOLD docs/COMPACT-SUMMARY-2026-09-03.md — still a working reference; move last, after ratification.
#   EXCLUDE docs/COMPACT-SUMMARY-2026-08-18.md — see OW-146.
mv docs/TODO-SNAPSHOT-2026-08-02.json docs/archive/2026/snapshots/
mv docs/TODO-SNAPSHOT-2026-08-03.json docs/archive/2026/snapshots/
mv docs/TODO-SNAPSHOT-2026-08-07.json docs/archive/2026/snapshots/
mv docs/TODO-SNAPSHOT-2026-08-12.json docs/archive/2026/snapshots/
mv docs/TODO-SNAPSHOT-2026-08-14.json docs/archive/2026/snapshots/
mv docs/reports/_stale docs/archive/2026/reports-stale
#   docs/reports/** is gitignored (1 of 151 files tracked). git mv WILL fail here.
```

### Explicitly NOT in any batch — do not move

```
docs/planning/operator-console-requirements.md   # 8 live code/SQL/test citations
docs/planning/port-backlog.md                    # 4 live citations
docs/planning/agno-chunking-strategy.md          # 4 live citations incl. ADR-0050
docs/planning/facade-collapse-plan.md            # server/agents/AGENTS.md
docs/planning/gui-integration-spec.md            # scripts/annotate-plans.sh + UNCLEAR (OW-100)
docs/planning/chat-sample-analysis/**            # KEEP-CANON — irreplaceable discovery over the real corpus
docs/adr/**                                      # inversion rule
docs/semantica, docs/semantica-benchmarks        # symlinks
docs/recovered/**                                # sole surviving GraphRAG record
docs/DOC_CLEANUP_MANIFEST-2026-08-15.md          # its 5 UNRESOLVED questions are still open (OW-003)
docs/CLAIMED_COMPLETE_LIKELY_LIES/awaiting-verification-inventory-20260901.md  # the pending disposition ruling
docs/COMPACT-SUMMARY-2026-08-18.md               # OW-146 merge first
docs/wiki/archive/.planning/**                   # OW-001 P0 until ruled
```

### Manifest totals

| Batch | Moves | Files affected | Owner input |
|---|---|---|---|
| A | 46 commands | 52 | **None** |
| B | 9 commands | ~80 | None, but 6 paired edits |
| C | 5 commands | ~660 | **Required** |
| D | 11 commands | ~130 | None |

**Batch A alone removes 52 files from the working set and requires no decision from anyone.**
That is the answer to pre-mortem failure #1: there is no excuse for zero movement.

---

## 10 · UNCLEAR list — owner decisions, with a recommendation for each

| # | Question | Recommendation | Register |
|---|---|---|---|
| 1 | **The credential literals in five tracked docs.** Rotate, redact-in-place, or accept as dead? | **Redact in place with a dated correction, and rotate anything still in use.** They describe another project's `.env`; the values are probably dead, but "probably" is not a standard for a git-tracked secret. Archiving does not fix git history. | OW-001 |
| 2 | **`docs/wiki/` — 580 files of another product's wiki.** | **Move whole to `docs/archive/2026/wiki-dial-stack-donor/`** (KT score 83). It is genuine donor material for ADR-0022's deferred wiki, so it must not be lost — but it must stop competing with real docs. | OW-063 |
| 3 | **`docs/awaiting-verification/` — 78 files in purgatory since 2026-08-18.** | **Move whole, as-is** (KT score 82), README banner intact. It is already declared UNVERIFIED; archiving changes nothing epistemically and everything about attention. The 2026-09-01 per-file inventory travels with it. | OW-004 |
| 4 | **`docs/planning/architecture-directives/` says ACTIVE; its files say DRAFT/not-deployed.** | **Ask the owner directly: active or archive?** Three months and ~40 ADRs have passed. If active, its files need status refreshes; if not, archive. It cannot stay both. | OW-107 |
| 5 | **The `docs/blueprint/` vs `.agents/blueprint/` canonical question**, open since 2026-08-15. | **Pick `docs/blueprint/` and delete nothing.** It is already referenced and already carries a supersession banner. Then fix its stale Milvus node. | OW-003, OW-057 |
| 6 | **The six evidence-release questions (R1–R6)** — authentication methods, redaction meaning, who may release, custody-`released` vs legal release. | **Rule these before any court-facing export work.** They are the only genuinely unruled *product* questions found in the entire purgatory tree, and they gate the court-readiness lane. | OW-140 |
| 7 | **The F2 recall hook (`UserPromptSubmit`)**, designed 2026-09-02, never implemented. | **Approve it.** It is the mechanical fix for the re-litigation loop diagnosed in this repo's own review, and it costs one settings edit. F3 and F4 are doc edits that need no approval at all. | OW-050/051/052 |
| 8 | **The two 2026-08-30 Workbench docs in `CLAIMED_COMPLETE_LIKELY_LIES/`** claiming "LIVE VERIFIED". | **Re-verify or re-label.** The folder name is a judgement; either promote them with evidence or leave them quarantined with a dated note saying why. | — |
| 9 | **`docs/reviews/2026-08-29-nocodb-quarantine-receipt.md` — "OWNER DELETE PENDING".** | **Rule it.** One line closes a nine-day-old hold. | OW-026 |
| 10 | **Whether the migration ledger should be backfilled** for migrations already live. | **Backfill it.** D-142's golden-clone-template ruling (OW-028) needs a ledger that describes the whole schema, not just going-forward rows. | OW-013 |
| 11 | **`docs/research/integration-audit-2026-08-24/`'s two raw npm catalogs (8.3 MB of JSONL).** | **Move them out of `docs/` to a data or scratch path** and repoint `.duckdb/AGENTS.md`. Scrape dumps are not documentation. | — |
| 12 | **`docs/CLAIMED_COMPLETE_LIKELY_LIES/` as a directory name.** | **Keep it.** It is honest, it is doing its job, and renaming it would soften a signal the owner deliberately made loud. | — |

---

## 11 · What would actually break the loop

The manifest fixes today's corpus. It does not fix the structure that produced it. Three
interventions, in leverage order:

1. **Make retirement part of the definition of done.** Add to `docs/CONVENTIONS.md`: *a change
   that supersedes a document moves that document to `docs/archive/<yyyy>/` in the same commit,
   after its open items are in a register.* This is `docs/archive/README.md`'s existing rule,
   relocated to where it will actually be read. (Pairs with OW-052's F4 edit.)
2. **Make the reference map mechanical.** The §5.2 scan is one `rg` loop. As a CI check —
   *"no tracked file references a path that does not exist"* — it converts the fear that blocks
   retirement into a build failure, permanently. It would also have caught the still-broken
   `docs/pending-review/` pointer 13 days ago.
3. **Cap the type that decays fastest.** HANDOFF documents (including compact summaries) are the
   highest-volume, shortest-lived type. A standing rule — *compact summaries older than 14 days
   move to `docs/archive/<yyyy>/summaries/` automatically* — would have removed 545 KB from the
   working set without a single judgement call.

Absent those, generation 7 arrives in about three weeks.

---

## 12 · What this pass did not do

Declared, not hidden — the same discipline the register demands.

- **251 unchecked checkboxes** in `docs/reviews/**` and `docs/CLAIMED_COMPLETE_LIKELY_LIES/**` were counted, not individually triaged (OW-070).
- **GAP-001…034** and **ISS-001…047+** were read at register level; individual dispositions were not hand-verified (OW-067, OW-069).
- The two largest planning clusters (`forensic-db-architecture/` 1.6 MB, `forensic-db-reconciliation/` 1.4 MB) were classified from front-matter and STATUS files, not read in full.
- `docs/CHANGE-ORDER.md` (54 KB) and `HANDOFF-2026-08-29-derived-document-ingest-wiring.md` (127 KB) were read by targeted grep, not linearly.
- **Nothing was moved, edited, or deleted.** No `git mv` was run. The only new files are this audit and the two documents under `docs/consolidated/`.
