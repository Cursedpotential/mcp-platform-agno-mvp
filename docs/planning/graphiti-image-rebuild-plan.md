# Graphiti: rebuild our own image, retire the hotfix pile

> _Byline: Claude Code · Fable 5 · 2026-07-31_
> **Status:** research complete, build not started — owner decision pending.
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

## Open decisions for the owner

- Approve the rebuild (vs the earlier "second Neo4j container" workaround, which this obsoletes —
  a correct driver makes one Neo4j + N databases work as originally designed in ADR-0036).
- Enable GLiNER2 in the image? (cheaper CPU-local NER, adds ~model download + memory footprint)
- Open the upstream PR under which identity/account?
