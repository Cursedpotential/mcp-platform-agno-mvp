# ADR-0018: Bitemporal evidence memory + disclosure-tier (the multi-pass cognition substrate)
- Status: Accepted
- Date: 2026-06-11
- Extends: ADR-0014 (Graphiti/Neo4j as the evidentiary temporal graph).

## Context
Part 2 (analysis) must replay how a person realizes they were abused, in passes with widening
knowledge: **Pass 1 contemporaneous** (only what was knowable at that moment — where gaslighting
works), **Pass 2/3 assembled hindsight**, **Final pass full disclosure** (incl. facts discovered
later). The legal payoff is the **delta between Pass 1 and the final pass for the same event** —
"what you were led to believe vs what was true vs when you found out" — which is gaslighting/DARVO
made court-legible. This requires the memory to model not just when things happened but when we
*learned* them.

## Decision
Every evidence atom written to Graphiti carries three time/knowledge axes:
- **valid-time** — when the event actually happened.
- **knowledge-time** — when it entered our knowledge (ingestion/discovery).
- **disclosure-tier** — `contemporaneous` | `hindsight` | `discovered`.
A "pass" is a **knowledge horizon**: a filter over the bitemporal graph. Pass N analysis sees only
facts whose knowledge-time ≤ horizon N. Analysis writes *derived* nodes/conclusions per-pass
(referencing evidence by hash + horizon), never mutating evidence. The Pass-1↔final delta is a
first-class queryable artifact. Implemented this round as the substrate; the multi-pass engine that
drives it is Part 2.

## Consequences
- `evidence/store.py` tags every Graphiti episode/entity with the three axes (group/metadata).
- Knowledge-horizon queries ("what was known by time T") are the substrate proof.
- Semantica (pulled forward, ADR-0020-adjacent) tracks per-pass conclusion provenance.
- Evidence stays append-only/immutable; analysis is strictly derived.

## Alternatives considered
- Single-timestamp storage — rejected: can't reconstruct "what did the analyst know at pass N",
  which is the entire mechanism.
- Recompute passes from raw each time without knowledge-time — rejected: loses the discovery
  timeline that *is* the abuse evidence.
