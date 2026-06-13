# ADR-0020: Multi-domain knowledge engine — domain-separated, any-agent queryable
- Status: Accepted
- Date: 2026-06-11
- Extends: ADR-0010 (one vector collection per embedder) and ADR-0011 (NIM embedder).

## Context
Knowledge is gathered from conversations spanning very different domains: timeline & relationship
history, personal history, platform/engine design decisions, and legal strategy & planning. Any
agent must be able to query it, but the domains MUST stay separated so an agent pulls the right
context (the Legal Team should not retrieve engine-design chatter; the Builder should not retrieve
relationship history). A single undifferentiated corpus would cross-contaminate retrieval.

## Decision
Knowledge is **domain-partitioned**: separate pgvector collections + metadata tags per domain,
queried with domain filters. Initial domains:
- `timeline_relationship`, `personal_history`, `platform_design`, `legal_strategy`.
Each agent family queries only its relevant domains (Legal → legal_strategy + timeline + evidence;
Builder → platform_design; Analysis → timeline + personal). Ingestion routes each conversation/doc
to its domain. Within the embedder dimension contract (ADR-0011), each domain is its own collection
(per ADR-0010). Evidence-scale vectors move to a self-hosted store later (ADR-0021 parking lot).

## Consequences
- Ingestion gains a domain classifier/router; `create_knowledge` is called per domain.
- Retrieval APIs take a domain (or domain set) filter; agents declare their domains.
- `Secrets/` and case-data dirs are still never ingested (security boundary unchanged).
- Phased gathering: (a) build missing components → (b) process evidence vs timelines → (c) legal
  strategy/docs/filings.

## Alternatives considered
- Single corpus with metadata only — rejected: weaker isolation, cross-domain retrieval bleed.
- One collection per agent — rejected: domains are shared across agents; partition by domain, not agent.
