
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
