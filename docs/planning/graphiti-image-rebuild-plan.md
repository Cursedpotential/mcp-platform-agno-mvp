# Graphiti: rebuild our own image, retire the hotfix pile

> _Byline: Claude Code · Fable 5 · 2026-07-31 (merged with the as-built record: Claude Code · Opus 5 · 2026-08-01)_
> **Status:** ~~research complete, build not started — owner decision pending~~ →
> **BUILT, DEPLOYED AND VERIFIED 2026-07-31.** `ghcr.io/cursedpotential/graphiti-mcp:0.29.3`
> @ `sha256:fc64fd33…` is live on ovh-files, case lane writes the `memory` DB (proven), all three
> owner questions resolved. **Read the AS-BUILT section at the foot before acting on §§1–8** —
> everything above it is the pre-build research and is preserved for history, not as instructions.
> Supersedes the "patch the vendored image + monitor for drift" idea from the same session.

## Why this exists

The owner's call (2026-07-31): *"I don't believe you're using the right image and we should be
able to customize our own image… not to mention all the side hot fixes and stuff, it's all fucked
up."* Both halves are correct. This documents what was verified against upstream, and what a
rebuild buys.

## 1. We are running the wrong image, badly out of date

| | Ours | Upstream |
|---|---|---|
| Image | `zepai/knowledge-graph-mcp:**latest**` | compose uses `zepai/knowledge-graph-mcp:**standalone**` |
| Digest built | **2026-03-11** | current |
| `graphiti-core` | ~March vintage | **v0.29.3** (2026-07-27) |
| MCP server | unknown | **1.0.2** |

`:latest` is also **unpinned** — any redeploy can silently pull a different image. Same class of
hazard as the Weaviate `:latest` we pinned earlier this session.

## 2. The database bug — confirmed upstream, still unfixed on `main`

`mcp_server/src/services/factories.py`, `DatabaseDriverFactory.create_config`, neo4j branch:

```python
return {
    'uri': uri,
    'user': username,
    'password': password,
    # Note: database and use_parallel_runtime would need to be passed
    # to the driver after initialization if supported
}
```

…and `graphiti_mcp_server.py` then builds `Graphiti(uri=…, user=…, password=…)` with no database.
The FalkorDB branch *does* pass `database` and constructs a driver explicitly.

**It is purely a wiring gap, not a design limit:**
- `mcp_server/config/config.yaml` DOES define `providers.neo4j.database: ${NEO4J_DATABASE:neo4j}`
- upstream's own `docker-compose-neo4j.yml` DOES set `NEO4J_DATABASE=${NEO4J_DATABASE:-neo4j}`
- `examples/quickstart/README.md` even documents the symptom: *"If encountering a 'Graph not found'
  error, modify the driver constructor in the script to specify the correct database name — the
  Neo4j driver defaults to using `neo4j` as the database name."*
- and `graphiti-core` has supported the fix since **v0.17.0**:

```python
driver = Neo4jDriver(uri=…, user=…, password=…, database="my_custom_database")
graphiti = Graphiti(graph_driver=driver)
```

So: config field exists, env var exists, core supports it — one function drops it on the floor.
**This is a clean upstream PR** (~6 lines), which would delete our fork entirely.

## 3. The hotfix pile a rebuild retires

Currently stacked on the stale image:

| Hotfix | Why it exists | Survives a rebuild? |
|---|---|---|
| `graphiti-hostfix` nginx | image's FastMCP locks `allowed_hosts` to localhost → 421 on tailnet IP | **likely deletable** — current config exposes `server.host: "0.0.0.0"` and no allowed_hosts lock; verify on the new build |
| `graphiti-portkeyfix` nginx | graphiti_core's OpenAI client can't send `x-portkey-config` headers | keep for now (upstream client still has no header hook) |
| mounted `config.yaml` | image ignores `CONFIG_PATH` | **deletable** — bake config into our image |
| database patch (proposed) | §2 above | **deletable** — fix at source in our build |

Two of four sidecars/mounts disappear; the remaining one is a genuine upstream limitation.

## 4. Building our own is a supported path

`mcp_server/docker/` ships `Dockerfile.standalone`, `build-standalone.sh`, `build-with-version.sh`.

`Dockerfile.standalone` essentials:
- base `python:3.11-slim-bookworm`
- installs `graphiti-core[neo4j,falkordb]==${GRAPHITI_CORE_VERSION}` — **version is a build arg**
  (default 0.29.1 → we pin **0.29.3**)
- `uv sync --no-group dev --extra providers --extra azure`
- `CMD ["uv","run","--no-sync","main.py"]`, `EXPOSE 8000`, healthcheck on `/health`

`providers` extra pulls: `google-genai`, `anthropic`, `groq`, `voyageai`, `sentence-transformers`.

## 5. GLiNER2 — CPU-local entity extraction (relevant: this box has NO GPU)

`examples/gliner2/`: GLiNER2 runs **NER locally on CPU**; the LLM is still used for edge/fact
extraction, dedup and summarization. `pip install graphiti-core[gliner2]`; default model
`fastino/gliner2-large-v1` (205M base / 340M large), weights auto-download. `GLiNER2Client`
accepts any Graphiti `LLMClient`, so it composes with our Portkey-routed LLM.

**Why it matters:** entity extraction is the highest-volume LLM call in ingestion. Moving it
on-box cuts per-episode cost and removes a provider dependency from the hot path — without a GPU.
Not in `mcp_server`'s extras, so it requires our own build to enable.

## 6. Ingestion behaviour worth knowing (dense vs normal)

`examples/quickstart/dense_vs_normal_ingestion.py`: **no API difference** — `add_episode()` is
identical. Graphiti decides internally from entity density, tunable by env:

| Var | Default | Meaning |
|---|---|---|
| `CHUNK_MIN_TOKENS` | 1000 | below this, never chunk |
| `CHUNK_DENSITY_THRESHOLD` | 0.15 | entities-per-token cutoff |
| `CHUNK_TOKEN_SIZE` | 3000 | target chunk |
| `CHUNK_OVERLAP_TOKENS` | 200 | overlap |

Low density → one LLM call (cheap/fast). High density → auto-chunked (more calls, reliable
extraction). **Directly relevant to evidence ingestion**, which is entity-dense.

## 7. Zep platform: what is NOT self-hostable

Zep's **Memory MCP Server** (tools `search_graph`, `get_user_summary`,
`list_accessible_graphs`, `search_graph_in`, `add_memory`, `add_memory_to_graph`) runs on
**managed cloud or BYOC and is Enterprise-plan gated**. Its identity model maps an IdP claim
(`sub` by default) to a Zep user → that user's isolated graph, with ~5-minute access tokens.

Conceptually that is the same lane-isolation we are building — but it is **not available to
self-host on our footing**, so the per-instance/per-database approach stands. Zep's proprietary
extraction/reranker/embedding models and Observations are likewise cloud-side.

## 8. Proposed build (not started)

1. Vendor `mcp_server/` at a pinned upstream ref into `docker/graphiti/`.
2. Apply the ~6-line driver fix (`Neo4jDriver(database=…)` → `graph_driver=`), keep it as a
   discrete patch file so it can become the upstream PR verbatim.
3. Build with `GRAPHITI_CORE_VERSION=0.29.3`, add the `gliner2` extra.
4. Bake `config.yaml`; drop the `CONFIG_PATH` mount.
5. Verify whether `hostfix` can be dropped; keep `portkeyfix`.
6. Publish to GHCR **by digest**, deploy `data-graphiti-case` on it first (the case lane is empty,
   so it is the zero-risk canary), verify writes land in the `memory` database, then cut the dev
   instance over.
7. Open the upstream PR; if merged, delete our patch and track upstream tags.

**Rollback at every step:** the current `data-graphiti` instance is untouched until step 6 passes.
## Open decisions for the owner — ALL RESOLVED 2026-07-31

> _Resolution block: Claude Code · Opus 5 · 2026-08-01. The three questions below were answered by
> the build itself (see AS-BUILT). Kept, struck through, rather than deleted._

- ~~Approve the rebuild (vs the earlier "second Neo4j container" workaround, which this obsoletes —
  a correct driver makes one Neo4j + N databases work as originally designed in ADR-0036).~~
  **APPROVED + BUILT.** Steps 1–6 of §8 all executed; canary green.
- ~~Enable GLiNER2 in the image? (cheaper CPU-local NER, adds ~model download + memory footprint)~~
  **YES — enabled and verified.** The image installs
  `graphiti-core[anthropic,google-genai,groq,gliner2,sentence-transformers,voyageai,tracing,neo4j-opensearch,neptune]==0.29.3`;
  `gliner2` and `BGERerankerClient` both import in-image, and 2.0 GB of the 5.02 GB image is
  pre-warmed model weights.
- ~~Open the upstream PR under which identity/account?~~ **NO PR — owner call.** The patch is instead
  durably preserved in three places (repo / build recipe / running image) with a build-time guard
  that fails loudly if the upstream anchors move. See "Follow-ups closed" item 3.

**Correction to §8 above:** steps 1–6 are DONE, not proposed. Step 7 (upstream PR) was declined.
**Correction to §3 above:** the table predicted `graphiti-hostfix` was "likely deletable" — it was
tested and is **still required** (upstream's FastMCP DNS-rebinding lock is live in 0.29.3). Both
nginx sidecars stay. Only the `config.yaml` mount and the database patch were retired.


---

## AS-BUILT (2026-07-31) — canary green

> _Byline: Claude Code · Fable 5 · 2026-07-31_

**Image:** `ghcr.io/cursedpotential/graphiti-mcp:0.29.3`
@ `sha256:fc64fd3303d6a89134b49bca25aba33ad24b4e99c455a79a8e9a4ef900e8d62b` (5.02 GB;
2.0 GB of that is pre-warmed model weights). Deployed **by digest**, not by tag.

**Upstream pin:** `getzep/graphiti@4f62cfe7a2d519e55bfdf2dc4a2fd06649dc00b3` + our
2-hunk patch, applied at build time with a guard that fails the build loudly if the
anchors ever move.

### Verification results

| Check | Result |
|---|---|
| `graphiti-core` version in image | **0.29.3** ✅ |
| `falkordb` absent from site-packages | **confirmed absent** ✅ |
| Patch present in image | both hunks ✅ |
| `gliner2` imports (CPU-local NER) | ✅ |
| `BGERerankerClient` imports (local reranker, no API key) | ✅ |
| `GRAPHITI_TELEMETRY_ENABLED` | `false` ✅ |
| **Decisive: case episode routing** | `memory` 1 → **4** nodes; `neo4j` **508 → 508 unchanged** ✅ |
| `case-salem-kinzel` nodes in `memory` DB | 3 ✅ |
| Custom entity types extracting | `Location`, `Organization` labels present ✅ |
| `grc doctor --lane case` / `--lane platform` | both **PASS** ✅ |
| Telemetry egress attempts in logs | **0** ✅ |

**The bug is fixed.** Before: case episodes landed in the dev database (twice, leaving
9 stray `case-*` nodes). After: they land in `memory` and the dev graph does not move.

### Bonus — the stale image was costing capability

The rebuilt server exposes **13 tools vs the old image's 9**. New: `summarize_saga`,
`build_communities`, `add_triplet`, `get_episode_entities`. `build_communities` is
directly relevant to the Observations follow-on (community detection over facts).

### Deployment

New Coolify app `data-graphiti-case` (uuid `wi3vzgd4hekbddvqj8nkn33j`) on **ovh-files**,
watch paths scoped to `compose.data-graphiti-case.yaml` + `docker/graphiti-mcp/**`.
The old ovh-data app (`mgfmunojgfp92k9uqd9td3np`) is **stopped**, not deleted.

### Build gotchas hit (all fixed, recorded so they aren't rediscovered)

1. `python:3.11-slim` has **no `patch` binary** — added to apt.
2. **`mcp_server/.python-version` pins `3.10`** and that, not `requires-python`, is what
   uv reads to select an interpreter. With `UV_PYTHON_DOWNLOADS=never` it failed the
   build. Both raised to 3.11 (also correct: the `gliner2` extra requires ≥3.11).
3. `requires-python` is `">=3.10,<4"` — a guard grep for `">=3.11"` with a closing
   quote fails. Match without it.

### Still open (deliberately not done this run)

- Dev lane (`data-graphiti`, 508 nodes) still on the old image — **untouched by design**.
- 9 stray `case-*` nodes remain in the dev database, awaiting `delete_episode` cleanup.
- `graphiti-hostfix` sidecar retained; not yet tested whether the new image makes it
  redundant.
- Upstream PR not opened (owner undecided).

---

## Follow-ups closed (2026-07-31, same day)

**1. Stray `case-*` nodes — cleaned, nothing destroyed beyond the two probes.**
`delete_episode` removed the 2 probe episodes (dev graph 508 → 506) but does **not**
cascade to derived entities (Graphiti allows entities to be shared across episodes), so
7 entity nodes survived. Inspection showed their content was *infrastructure* — "case
memory", "DozerDB memory database", "platform build graph", "case config" — i.e. residue
of the plumbing test, **not case facts or PII**. Their content genuinely belongs in the
dev graph; only the `group_id` was wrong. So they were **relabelled** to `group_id:
"platform"` with `regrouped_from` + `regrouped_at` stamps rather than deleted — the
honest fix, fully reversible, and it respects the never-delete rule. Result: **0**
`case-*` nodes in the dev database; total 506; case lane (`memory`) intact at 4.

**2. `graphiti-hostfix` sidecar — TESTED, still required. Do not remove.**
Probed the new image directly (bypassing the sidecar):

| `Host:` header sent | Result |
|---|---|
| `localhost:8000` (what hostfix injects) | **200** |
| `100.91.190.107:8073` (tailnet, what a real client sends) | **421** |
| arbitrary (`evil.example.com`) | **421** |

The upstream FastMCP DNS-rebinding lock is **still active in graphiti-core 0.29.3 /
MCP server 1.0.2**: `server.host: 0.0.0.0` does not disable it and the
`FASTMCP_TRANSPORT_SECURITY` env is still ignored. The plan speculated this sidecar
might be redundant after the rebuild — **it is not**. Both nginx sidecars stay.

**3. The patch is durably preserved (no upstream PR — owner call).**
- `docker/graphiti-mcp/patches/0001-neo4j-database-selection.patch` committed and pushed
  to `origin/main` (blob `c0487449`).
- The Dockerfile applies it behind a guard that **fails the build** if the anchors move,
  so a silent regression is impossible.
- `/app/mcp/.upstream-ref` inside the image records the exact upstream SHA it applies to.

Three independent copies: the repo, the build recipe, and the running image.
