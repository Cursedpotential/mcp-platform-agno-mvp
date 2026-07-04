# Agent-Context Merge Plan — Case Bible ⇄ Agno MVP (progressive disclosure)

> _Byline: Claude Code · Opus 4.8 · 2026-06-29_
> **Status: PLAN — discovery complete, no files rewritten yet.** Phases 1–2 are
> drafted below and gated on owner review. This doc exists to rescue the merge
> thread that previously lived only in a separate chat history.

## 0. Why this doc exists

The work to **fold the Case Bible vault and the Agno MVP platform into one coherent
agent-context surface** — and to restructure the `AGENTS.md` / `CLAUDE.md` files on
both sides with **progressive disclosure** — was happening in a separate chat and was
**never written to disk**. This is the reconstruction. It is the single source of
truth for that effort going forward.

## 1. The relationship (the thing being merged)

- **Agno MVP platform** (`Agno-MCP-Platform/`, the active build) is the **consumer**.
- **Case Bible** (the Obsidian "sorted" vault) is the **producer/substrate**: it is
  simultaneously
  1. the **agent context** for the application,
  2. the **evidence + knowledge store** (the vault), and
  3. the **application's own docs + Wiki** (its `Platform/` domain — wiki currently STALE).
- Data gradient: **raw** R2 bucket (consolidated local+cloud dump, dupes + file-recovery
  carves with lost metadata) → **dedup/sort** → **sorted** vault = the Case Bible.

So "merge" does **not** mean physically combining two git repos. It means: **one
canonical, layered agent-context surface** spanning both, where the platform's
`AGENTS.md` knows about and routes into the vault, and both sides follow the same
progressive-disclosure discipline.

### 1a. Sources feeding the merge (owner, 2026-06-29)

Everything below is dumped into the **R2 `casebible-raw` bucket**, then
**sorted → deduped → classified → placed** into the **R2 `casebible-sorted` bucket**:

- **≥ 2 Google Drives** (Takeout / drive-download dumps)
- **Multiple local drives**
- **The actual Case Bible** (`C:\Users\matts\OneDrive\Case Bible`)
- **The D:\Backup dump** (lands as `_backup_import/` — currently full of software/venv junk)
- **iCloud — DEFERRED** ("skin that cat later"; rclone + iCloud don't cooperate)

### 1b. Current raw-bucket reality (from local catalog `D:\casebible\casebible.duckdb` → `r2_files`, 590,560 objects)

The raw bucket is (expectedly) a mess:
- `_backup_import/` = **501,215 objects (85%)** (the D:\Backup dump) — **MIXED**: lots of
  important content AND a full `text-generation-webui` install (conda pkgs, `site-packages`,
  `.pyc`). **NOT a blanket-delete** — must classify by content.
- `_system_backup/` = 10,807 — mostly venv/software artifacts.
- `.obsidian/` + `.smart-env/` = 3,272 — Obsidian vault config (**KEEP**, see ruleset).
- `General_Code_&_Repos/` = 1,028 — the owner's code (**KEEP** as code backup, see ruleset).
- **Merge-collision duplicates** from combining drives: `Takeout Data` vs `Takeout Data1`,
  `AI_Chats` vs `AI_Chats1`, `Legal_Knowledge_Base_Obsidian` vs `…1`.
- Inconsistent top-level naming for the same concept: `Evidence`, `court`, `EXHIBIT`,
  `Evidence_&_Timelines`.

### 1b-i. Classification ruleset — KEEP vs quarantine (owner, 2026-06-29)

The vault is an **Obsidian-based, AI-context-digestible** vault. Classification is
**content/path-based, NOT top-level-prefix-based** (because `_backup_import` is mixed).

**KEEP:**
- **The owner's own code** — repos, different iterations, snippets. Important: keep a code
  **backup** in the vault. (Placement TBD — `Platform/` vs an `Archive/Code/` area; owner to confirm.)
- **`.obsidian/`** (and vault config) — it's an Obsidian vault; these belong and aid AI digestion.

**QUARANTINE (the "fuckery" — software artifacts, never evidence/knowledge):**
- Installed third-party software & dependencies: `site-packages/`, `__pycache__/`, `*.pyc`/`*.pyo`,
  `node_modules/`, `.venv/`/`venv*/`, conda `pkgs/`, `*.dist-info/`, `installer_files/`,
  `text-generation-webui/` install trees, model/weight caches, `*.so`/`*.dll`/binaries.
- These are what "all the software shit needs to go" means. They go to
  `casebible-quarantine/.to_be_deleted/` (preserved, recoverable — **no hard deletes**).

> Engineering implication: the classify/dedupe pass needs a **software-artifact detector**
> (the path patterns above) to peel junk OUT of the mixed backup dirs while preserving the
> owner's real code + documents + evidence within the same trees.

### 1c. ⭐ TOP PRIORITY (owner, 2026-06-29): structure the sorted bucket FIRST, then undo the fuckery

Before any bulk sort, the **`casebible-sorted` bucket must be given a proper, enforced
structure**, and its **current mis-structure ("the fuckery") undone**. The canonical
structure = the architect-spec domains (see §1d). Junk classes from §1b become hard
**exclusion rules** so they never reach sorted. Execution of any bucket move/quarantine is
**SORT-lane + owner-gated** (R2 Class-A ops are billable; no deletes — quarantine to
`casebible-quarantine/.to_be_deleted/`).

### 1c-i. Cataloging approach: prefer Cloudflare R2 Data Catalog (Apache Iceberg) (owner, 2026-06-29)

Use **R2's native Data Catalog (managed Apache Iceberg REST catalog)** for the buckets where
possible, rather than the ad-hoc local DuckDB (`casebible.duckdb`) as the long-term source.
- **Nuance:** R2 Data Catalog catalogs **Iceberg tables**, not loose objects. The evidence
  files (jpg/pdf/csv/…) remain plain R2 objects (listed via S3/rclone). So the pattern is:
  **materialize our registries AS Iceberg tables in R2 Data Catalog** — the file-level
  registry (`r2_files` md5+path), the **sort ledger** (old→new provenance), and the
  **enrichment** table — so they're queryable directly from R2 by DuckDB, PyIceberg, Spark,
  and the agents, with snapshots/time-travel for free.
- **Access tooling:** DuckDB `iceberg` extension (REST-catalog support) / PyIceberg; the
  `iceberg` skill. Requires enabling Data Catalog per bucket + a catalog token (setup +
  possible $; **gated** — plan before enabling). Local DuckDB stays as the fast offline cache.
- This also gives the SORT/PROCESS lanes and the app **one shared, versioned catalog** instead
  of a local DuckDB that has to be hand-synced.

### 1d. Canonical sorted-bucket structure (architect spec)

Top-level domains, one place for each thing:
**`Inbox/` · `Evidence/` · `Entities/` · `Case Management/` · `Legal/` ·
`Platform/` (=build/project/**wiki**/tooling) · `Legacy/` · `Archive/`**
+ governance files at root (`AGENTS.md`, `INDEX.md`, `Dashboard.md`, `GLOSSARY.md`,
`Tag Guide.md`, `MANIFEST.json`). The `D:\casebible\vault-sorted` scaffold already
embodies this and is the structural template to push to the bucket.

## 2. The engine (installed 2026-06-29)

Skill **`agents-md-progressive-structuring`** → `C:\Users\matts\.claude\skills\`.
It is the "best-of" merge of three earlier skills (per its `SOURCES.md`):
`harness-engineering` (spine) + `agents-md` (authoring discipline) + `progressive-context`
(disclosure layers + content-aware freshness + git hooks). All Phase 1–2 work below
should be driven through this skill.

Skill phase model: **Phase 0** discovery · **Phase 1** canonical `AGENTS.md` + thin
`CLAUDE.md`/`GEMINI.md` shims · **Phase 2** disclosure layers + freshness markers +
hooks · Phases 3–8 = testing / boundary test / lint / CI / golden-principles / GC
(the full harness — **out of scope for this pass**).

## 3. Current-state inventory (Phase 0 — DONE)

### Platform side (git repo `E:\AI_Workspace`)
| File | Lines | Verdict |
|---|---|---|
| `AGENTS.md` (workspace root) | 110 | **STALE** — early-iteration "parts bin" orientation (dev-resources, `agents_factory.py`); says hierarchical AGENTS.md "not built yet"; **no mention of the Case Bible vault**. Needs rewrite to current architecture. |
| `CLAUDE.md` (workspace root) | 30 | Real, current content (working-dir rule, SSOT pointers, Graphiti). **Divergent from root AGENTS.md** — neither is a shim. |
| `Agno-MCP-Platform/AGENTS.md` | 93 | **GOOD / current** — real stack, agent topology, repo layout, doc map. Keep as the model; minor refresh only. |
| `Agno-MCP-Platform/CLAUDE.md` | 1 | Already a `@AGENTS.md`-style shim ✅. |
| `GEMINI.md` | — | Missing (add thin shims where the owner uses Gemini CLI). |

SSOT docs already live in `Agno-MCP-Platform/docs/` (PROJECT_CANON, MEMORY_ARCHITECTURE,
CONVENTIONS, EVIDENCE_MERGE_MAP, BUILD_PLAN, REPO_STRUCTURE, 28 ADRs).

### Vault side — **the canonical vault is the R2 bucket, NOT any local dir**
The owner confirmed (2026-06-29): the **canonical merged/combined Case Bible vault is the
R2 `casebible-sorted` bucket**. Nothing local is the whole vault — local content is being
**moved into the bucket**, and **three cloud drives are also being merged into it**
(e.g. OneDrive + Google Drive + a third — confirm exact set). The local dirs are:

| Location | What it actually is |
|---|---|
| **R2 `casebible-sorted` bucket** | ⭐ **CANONICAL VAULT** — the merged/deduped sorted Case Bible. Fed by local files + the three cloud drives via the SORT pipeline (rclone, ledger). The application consumes THIS. |
| `D:\casebible\vault-sorted` | **Metadata/governance SCAFFOLD only** — 161 KB, 29 `.md` + 11 `.json` (domain `AGENTS.md`, `Dashboard.md`, `INDEX.md`, `MANIFEST.json`, GLOSSARY/Tag Guide). Wiki folded under `Platform/` (matches architect spec). **No evidence payload.** This is the skeleton, not the vault. |
| `D:\casebible\` (parent) | SORT/PROCESS **working area** — `casebible.duckdb` (catalog), `casebible_work.sqlite` (sort work DB), `raw_hashes.txt`, `exports/`, `samples/`, `viz/`. Not the vault. |
| `C:\Users\matts\OneDrive\Case Bible` | **One of the raw/working sources** feeding the merge — top level littered with `$R…` recovery files, loose csv/jpg/pdf/xlsx; scattered domain `AGENTS.md` PLUS a **stray top-level `wiki/`** (`FUCKED.MD`, `_TO_BE_DELETED/`). Upstream of the sort, NOT a clean mirror. |

Per the architect skill, the authoritative domain structure is **Inbox · Evidence · Entities ·
Case Management · Legal · Platform(=build/project/wiki/tooling) · Legacy · Archive** — which the
`D:\casebible\vault-sorted` scaffold matches; it is the structural template for the R2 bucket.

## 4. T0 — Reconcile-first task (owner-gated, BEFORE Phase 1)

The owner chose **"reconcile first, then decide"** on canonical vault placement.
Before any AGENTS.md rewrite on the vault side:

1. **Diff the two mirrors** in full (structure + which domain `AGENTS.md`/`INDEX.md`
   exist + the wiki placement) and produce a written delta to `casebible-coordination/specs/`.
2. **Confirm canonical** = `D:\casebible\vault-sorted` (clean, spec-matching) vs. the
   OneDrive working area. (Strong prior: D: is canonical structure; OneDrive top-level
   `wiki/` + `FUCKED.MD` + `_TO_BE_DELETED` are legacy cruft to quarantine, never delete.)
3. **Decide where the canonical vault docs are edited** so Phase 1 edits land in one place
   and propagate via `cb-sync`, not by hand-editing whichever mirror.
4. Resolve **wiki placement**: top-level `wiki/` (OneDrive) vs `Platform/` (D:, spec) —
   recommend folding wiki under `Platform/` to match the architect spec.

> This is a SORT/PROCESS-territory task (vault), coordinated via the war-room. No deletes —
> quarantine cruft to `.to_be_deleted/` per the hard rule.

## 4a. Vault authoring & sync model (owner, 2026-06-29)

Split by latency vs. canonicality:

- **Docs + Wiki are AUTHORED LOCALLY** (in/near `D:\casebible\`), then **synced UP to the
  R2 `casebible-sorted` bucket**. Rationale: local agents get **fast, low-latency** read
  access to documentation/wiki instead of round-tripping to object storage.
- **The canonical vault `AGENTS.md` files MUST live in the R2 bucket** — they are part of
  the canonical Case Bible any agent reads when pointed at the vault. The **bucket copy is
  authoritative**; local is the editing mirror that syncs up (rclone **copy**, never sync;
  one writer = SORT).
- Net: **edit locally → `cb-sync` up → bucket is the source of truth.** Never hand-edit the
  bucket directly, and never let a local edit diverge from the bucket without syncing.
- **This also resolves the freshness anchor (§6.2):** put the small local authoring scaffold
  (`.md`/`.json`, ~161 KB) under its **own git repo** so the progressive-context freshness
  hooks work on it locally; the bucket receives the stamped, current files on sync.

## 5. Phase 1 (DRAFT — gated on T0 + owner review)

Canonical `AGENTS.md` per scope, with thin per-tool shims (`CLAUDE.md` = `@AGENTS.md`
import or symlink; `GEMINI.md` likewise). Never divergent full copies.

1. **Workspace root `AGENTS.md`** — rewrite to current architecture: the platform↔vault
   consumer relationship, the canonical working dir, pointer to `Agno-MCP-Platform/` and
   to the vault, and a **Context Index** routing into both. Collapse root `CLAUDE.md`
   content into the canonical `AGENTS.md`; make root `CLAUDE.md` a shim.
2. **`Agno-MCP-Platform/AGENTS.md`** — light refresh only (it's already good); add an
   explicit "this app consumes the Case Bible vault" section + vault pointer.
3. **Vault root + domain `AGENTS.md`** (in the canonical mirror from T0) — normalize to the
   architect-spec domains; ensure each domain's `AGENTS.md` + `INDEX.md` is consistent.
4. **Cross-tool shims** — add `GEMINI.md` shims where Gemini CLI is used; keep opencode on
   native `AGENTS.md`.

## 6. Phase 2 (DRAFT — gated)

1. **Disclosure layers** — move verbose content out of always-loaded files into
   reference docs; keep always-loaded `AGENTS.md`/`CLAUDE.md` lean (target <100 lines;
   <200 is the adherence cliff). Build a **Context Index** so `context_for.py` can route
   a source/vault path to its doc.
2. **Content-aware freshness markers** on path-triggered + reference docs (HTML comment,
   git-blob-hash watches). **Anchor (resolved, §4a):** the platform repo uses its own git;
   the vault's freshness operates on the **local authoring scaffold under its own git**, and
   stamped files sync up to the R2 bucket. Two freshness domains, both git-backed locally.
3. **Install git hooks** (`scripts/install_hooks.py`) in the platform repo; chain with any
   existing hooks rather than overwrite.

## 7. Plan B adjustment (the 4-lane loop rig) — to revise AFTER Plan A

The autonomous rig (`C:\Users\matts\casebible-coordination\`: README, AUTONOMY.md, the 4
loop prompts) predates this merge. Once the new context structure lands, adjust:

- **AUTONOMY.md / loop prompts** — point lanes at the canonical `AGENTS.md` surface; the
  "read the whole board each pass" step should also honor the layered context (don't
  re-crawl what the Context Index already routes).
- **README ownership table** — the vault-side `AGENTS.md` restructure is SORT/PROCESS
  territory; the platform-side is PIPELINE. Note the cross-cutting merge task explicitly so
  lanes don't collide on the shared agent-context files.
- **Canonical-mirror rule** — once T0 picks the canonical vault, encode "edit here, sync
  out" so lanes never hand-edit the wrong mirror.
- **Freshness/CI** — if Phase 2 hooks land in the platform repo, the PIPELINE lane owns
  keeping them green.

## 8. Open decisions still needing the owner

1. **Which three cloud drives** merge into the bucket (OneDrive + Google Drive + ? — confirm
   the exact set; some still need OAuth per the R2-route notes).
2. **Wiki placement** — confirm wiki folds under `Platform/` (architect spec) in the bucket.
3. **Phase scope later** — whether to eventually run the full harness (Phases 3–8:
   boundary test, lint rules, CI, golden principles, GC) on the platform repo, or stop at
   progressive disclosure.

> Resolved: canonical vault = **R2 `casebible-sorted` bucket** (not a local dir); authoring
> model = **local-edit → sync-up, bucket authoritative** (§4a); freshness anchor = **local
> scaffold under its own git** (§6.2).

## 8a. TODO / Backlog (owner wants these done; not yet scheduled)

- [ ] **R2 Data Catalog (Iceberg) backbone** — enable Cloudflare R2 Data Catalog and
  **materialize our registries as Iceberg tables in R2**: the file registry (md5+path), the
  **sort ledger** (old→new provenance), and **enrichment**. Plain-English: instead of a local
  DuckDB file that has to be hand-synced, the catalog of what's in the vault lives *in R2
  itself* as versioned tables that DuckDB / PyIceberg / Spark / the agents can all query
  directly, with built-in snapshots + time-travel. Local DuckDB stays as an offline cache.
  (Gated: enabling Data Catalog + token = setup, possible $. PIPELINE-lane infra task.)
- [ ] **Software-artifact detector** for classify/dedupe — subtree-aware (peel install trees:
  `installer_files/`, `conda/pkgs/`, `site-packages/`, `node_modules/`, venvs, model caches)
  out of the mixed `_backup_import` while KEEPING the owner's real code + docs + evidence.
- [ ] **Carve-pile content classification** — the ~413k hash-named recovery files in
  `_backup_import/<ext>/` need content-based keep/junk classification (not path rules).
- [ ] **Code-backup placement** — decide where the owner's code repos/iterations/snippets live
  in the sorted vault (`Platform/` vs `Archive/Code/`).
- [ ] **Inspect live `casebible-sorted` bucket** (read-only) — confirm current structure + fuckery.
- [ ] **Then:** finalize canonical sorted-bucket structure → gated remediation (move/quarantine).

## 9. Execution order (when greenlit)

T0 (reconcile) → Phase 1 (canonical AGENTS + shims) → Phase 2 (disclosure + freshness) →
revise Plan B (loop rig) → optional Phases 3–8.
