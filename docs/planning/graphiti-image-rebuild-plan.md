
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
