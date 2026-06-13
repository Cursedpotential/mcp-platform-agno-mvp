---
title: Wiki Canon Migration
aliases:
  - Documentation Canon Migration
  - Wiki Migration Playbook
type: guide
status: active
created: 2026-03-30
updated: 2026-03-30
reviewed: 2026-03-30
tags:
  - dial-stack
  - wiki
  - documentation
  - obsidian
  - llm
summary: Controlled playbook for moving all active documentation into the wiki in an organized, source-grounded, Obsidian-friendly format.
---

# Wiki Canon Migration

This guide defines how documentation should move into the wiki over time.

The goal is not to dump files into `docs/wiki/`. The goal is to create a usable, source-grounded knowledge layer for people, Obsidian, and LLM workflows without losing historical context.

## Migration Goals

- make `docs/wiki/` the primary active documentation surface
- preserve stale or superseded context under [[archive/README|Wiki Archive]]
- distinguish `implemented`, `partial`, `planned`, and `historical`
- give every important platform component a stable reference page
- make the vault easy to traverse with backlinks and predictable hubs
- make each page retrievable by LLMs without needing surrounding context

## Source Hierarchy

When sources conflict, use this order:

1. direct user instructions and active operating rules
2. active canon pages:
   - [[architecture/ARCHITECTURE|Architecture]]
   - [../plans/ROADMAP.md](../plans/ROADMAP.md)
   - [../memory/MEMORY.md](../memory/MEMORY.md)
   - [../.audit/2026-03-30-source-classification.md](../.audit/2026-03-30-source-classification.md)
3. verified implementation files in the repo
4. current approved planning material in [[.plannotator/plans/dial-stack-arch|.plannotator]]
5. archived or denied material for historical context only

## Required Front Matter

Every active first-party wiki page should include:

- `title`
- `type`
- `status`
- `created`
- `updated`
- `reviewed`
- `tags`
- `summary`

Reference pages for tools, services, or libraries should also include:

- `repo_version`
- `upstream_version`
- `official_docs`
- `official_repo`
- `official_downloads`

## Required Sections for Platform and Tool Pages

Every important platform or dependency page should cover:

1. what it is
2. current role in `dial-stack`
3. how we are using it right now
4. what we are not using it for
5. repo version posture vs upstream version posture
6. key implementation files or config surfaces
7. expansion paths
8. risks or watch-outs
9. official sources
10. related notes

## Controlled Migration Workflow

1. Inventory the existing docs in the source area.
2. Classify each document as `active`, `planned`, `historical`, or `archive-only`.
3. Merge active truth into the correct wiki location instead of copying raw duplicates.
4. Move stale or superseded versions into mirrored paths under [[archive/README|Wiki Archive]].
5. Add front matter, backlinks, dates, source attribution, and version posture.
6. Update hub pages so the moved notes are discoverable.
7. Verify that active notes do not point back to stale paths.

## Current Migration Tranches

### Tranche 1: Core Platform Canon

Priority:

- ingress and orchestration boundary
- core storage layers
- core protocol and tool layers
- auth, proxy, and compose surfaces
- analyst UI framework notes

### Tranche 2: Active Tool Surfaces

Priority:

- MCP server hubs
- parser and writer tools
- workflow tools
- review queue and admin tooling

### Tranche 3: Parser and Format Notes

Priority:

- `SMS XML`
- `Facebook JSON`
- iMessage and secondary message sources
- all format pages should explicitly state ingest expectations, raw preservation rules, and schema/field coverage

### Tranche 4: Operational and Evidence Guides

Priority:

- evidence handling procedures
- batch processing
- transcript and document handling
- analyst review workflows

### Tranche 5: Research and Mirrored Upstream Material

Priority:

- keep mirrored upstream or research-heavy material clearly separated from first-party canon
- avoid silently rewriting mirrored third-party docs as if they are our own source of truth

## Rules for Mirrored or Third-Party Material

- do not overwrite mirrored upstream docs with local assumptions
- prefer wrapper notes that summarize how `dial-stack` uses an upstream project
- keep raw mirrored research collections isolated from first-party canonical pages
- archive stale local interpretations rather than deleting them outright

## Page Taxonomy

- `hub`: directory or section landing page
- `reference`: tool, service, library, or schema note
- `guide`: process or operator workflow
- `proposal`: future-state recommendation or rollout plan
- `spec`: normative contract or implementation target
- `audit`: point-in-time assessment

## Current Direction

The current active migration direction is:

- wiki-first
- evidence-first
- tool-first
- Obsidian-friendly
- LLM-friendly
- source-attributed
- version-aware

## Related Notes

- [[INDEX|dial-stack Wiki Index]]
- [[guides/INDEX|Guides Hub]]
- [[architecture/ARCHITECTURE|dial-stack Architecture]]
- [[archive/README|Wiki Archive]]
- [[tools/INDEX|Tools Hub]]

