---
title: Semantica
type: reference
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - nlp
  - semantica
  - evidence-analysis
summary: Reference note for Semantica as the custom analysis backbone in dial-stack, including current MVP use, repo implementation anchors, and expansion lanes.
repo_usage_state: core-mvp
repo_version: semantica[all]>=0.2.6 in py-mcp-server requirements
upstream_version: custom internal component; current repo minimum dependency reviewed 2026-03-30
official_docs:
  - "internal: docs/wiki/semantica-research/semantica/"
  - https://www.w3.org/TR/prov-o/
  - https://spacy.io/api/entityrecognizer
  - https://www.sbert.net/
official_downloads:
  - "internal package dependency via semantica[all]>=0.2.6"
---

# Semantica

## At a Glance

- **What it is**: The custom analysis backbone for entity extraction, semantic enrichment, embeddings, graph handoff, and later higher-order conflict analysis.
- **Current role in `dial-stack`**: MVP-critical analysis layer after canonical storage.
- **Why it matters**: It is the main place where message evidence becomes structured analytical output instead of just normalized records.

## How `dial-stack` Uses It

Current local anchors:

- [server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)
- [workflow_tools.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/tools/workflow_tools.py)
- [workflows.json](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/config/workflows.json)
- [requirements.txt](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/requirements.txt)

Current responsibilities:

- NER and entity extraction
- embedding generation
- graph-oriented handoff
- workflow-level analysis orchestration
- initial analysis support for the MVP pipeline

## MVP Use Right Now

For the current message-evidence MVP, Semantica matters because it is part of:

`DuckDB -> PostgreSQL -> Semantica + LanceDB in parallel -> PostgreSQL enrichment`

Current MVP analysis scope:

- NER
- sentiment
- abuse screening

Deferred:

- contradiction detection
- deeper hindsight synthesis
- broader long-horizon conflict modeling

## What We Are Actually Using vs Older Claims

Some older docs describe Semantica as if every advanced analysis lane is already complete.

The current truthful posture is:

- Semantica is real and central
- several tool surfaces are implemented
- some domain-specific detectors and deeper behavioral lanes are still partial or placeholder

That distinction needs to stay explicit in the wiki.

## How We Could Expand Its Use

- stronger post-ingest abuse and behavioral screening
- richer workflow tools for analyst review and triage
- contradiction and narrative-shift lanes after the MVP ingest path is stable
- tighter graph and provenance writeback once Neo4j is hardened
- more case-specific custom classifiers layered on top of the existing NLP foundation

## What We Need to Watch

- avoid overselling placeholder analysis features as complete
- keep all outputs attributable to source evidence and canonical IDs
- ensure enrichment does not silently discard raw message context
- pin and version core Semantica dependencies more explicitly as the stack stabilizes

## Key Repo Files

- [server.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/server.py)
- [workflow_tools.py](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/src/tools/workflow_tools.py)
- [workflows.json](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/config/workflows.json)
- [requirements.txt](C:/Users/matts/Projects/TheBigOne/dial-stack/mcp-servers/py-mcp-server/requirements.txt)

## Sources and Building Blocks

- [W3C PROV-O](https://www.w3.org/TR/prov-o/)
- [spaCy Entity Recognizer](https://spacy.io/api/entityrecognizer)
- [Sentence Transformers](https://www.sbert.net/)
- internal mirrored research under [semantica-research](C:/Users/matts/Projects/TheBigOne/dial-stack/docs/wiki/semantica-research)

## Related Notes

- [[skills/nlp/fastmcp|FastMCP]]
- [[skills/database/postgresql|PostgreSQL]]
- [[skills/database/lancedb|LanceDB]]
- [[skills/database/neo4j|Neo4j]]
- [[INDEX|dial-stack Wiki Index]]
