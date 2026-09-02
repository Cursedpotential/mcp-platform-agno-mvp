# Temporal Evidence and Agent Experience Platform

> _Byline: Claude Code · Sonnet 5 · 2026-08-09 (docs/registers true-up — plan-link fix;
> drift-fix 2026-08-12 Claude Code · Kimi K3: stack line LiteLLM→Portkey/Weaviate per ADR-0040/0042; deploy section marked pre-4-box)_
> _Current-entry-point repair: Codex · GPT-5 · 2026-08-15._

A pro se family-law evidence, analysis, and legal-strategy platform. The current backend
runs through an **Agno 2.8.7 / AgentOS adapter**; the accepted target is a
**framework-neutral platform API and custom Workbench**. Agno remains available during
the strangler migration and is not yet retired. AG2 is a bounded coordination candidate,
not the approved replacement.

> **Start here:** [`docs/PROJECT_CANON.md`](docs/PROJECT_CANON.md) — the durable source of
> truth (vision, decisions, roadmap, access, gotchas). Orientation for agents:
> [`AGENTS.md`](AGENTS.md). Current document map: [`docs/INDEX.md`](docs/INDEX.md).
> Decisions: [`docs/adr/`](docs/adr/). Active plan:
> [`docs/BUILD_PLAN.md`](docs/BUILD_PLAN.md). Debt register: [`docs/DEBT.md`](docs/DEBT.md).

## Why this exists

> _Mission section added 2026-09-02 (Claude Code · Opus 5), from an owner working session.
> Stated generally on purpose: the case specifics belong in the case record, not the repo._

Coercive control works by capturing the narrative. *That never happened. You're
remembering it wrong. You're the unstable one.* Its power is the power to **narrate
another person** — to take childhood trauma, family tragedy, private grief, past
struggles, and the people they love most, and repackage each one as evidence of who they
are. You do not defeat that by arguing better. You defeat it with a record that the person
telling the story cannot revise.

Everything in this platform follows from that one fact.

**Decontextualization is the weapon. Sequence is the remedy.**
Every mechanism of this kind of abuse works the same way: lift one act out of its chain
and it means the opposite of what it meant. An angry message, isolated, is proof of
volatility. In sequence — after months of blocked access, after the fourth cancelled
exchange — it is an ordinary human response to sustained provocation. That is the
reactive-abuse trap: the person who finally snaps manufactures the only clean exhibit the
other side needs. So the core operation here is not search or storage. It is **restoring
sequence to acts that were stripped of it** — which is why per-record custody and
chunk-level provenance are worth the engineering. Not to prove a message is authentic, but
to prove what came before it.

**The volume is a symptom, not an accident.**
Coercive control leaves an enormous trail precisely because it is continuous and low-grade:
thousands of small acts, none individually actionable. That is *why* it works, and why it
is nearly unprovable — the abuse is invisible at the resolution a courtroom operates at. A
judge can hold one screenshot, not forty thousand messages. The real product is therefore
**resolution translation**: making a pattern that exists only at scale legible at human
scale without flattening it into "they fought a lot." Nuance is the abuse. Nuance is also
unpresentable. That tension is the engineering problem, and it is why naive summarization
is dangerous here in a way it is not in other domains.

**Immutability is the counter-move, not a compliance feature.**
A record that can be edited is just another version of events, and against a skilled
narrator another version loses. Immutability is the only property that makes this record
unfalsifiable by the person who lies — including by us. See D-128.

**The horizon delta exonerates the past self.**
"Why didn't you see it?" is itself a weapon; it implies complicity or stupidity. The
ignorant agent answers it: given only what was knowable at the time, the conclusion reached
was reasonable. This is why the walk must actually run forward rather than be a filter
applied afterward — a retrospective query proves nothing about what a person could have
known. The delta is a defense of the person, not merely an indictment of the other party.

**Bitemporality is the defense against weaponized history.**
A fact from twenty years ago, introduced today to characterize someone, is a different
object from a contemporaneous one. Separating when something happened, when it became
knowable, and when it was deployed is what stops decontextualized history from functioning
as character evidence. The clocks are the rebuttal.

**The attack becomes data.**
The cruelest move available is to take what most deserves compassion — a family tragedy, a
childhood trauma, an illness, a death — and convert it into evidence of unfitness. There is
no technical answer to that cruelty. There is one to the record of it: each deployment is
itself an event, with a timestamp and a pattern. Captured faithfully, it stops being only a
wound and becomes an exhibit about the person wielding it.

**It has to be able to tell you you're wrong.**
This is the requirement most easily lost, and the one that protects the whole enterprise.
The lasting damage of gaslighting is that you stop trusting your own read — so the person
using this tool is, by construction, the person least able to judge their own evidence. A
tool that only ever returns *confirmed abuse* is worthless in court and corrosive to use;
the first move against it is "you built a machine to agree with you," and if it cannot
return a null result, that objection is correct. **The ignorant/hindsight architecture is
falsifiable by design: if the delta is empty, there was no deceit at that horizon.** Protect
that property. The moment it is "improved" into always finding something, it stops being
evidence and becomes advocacy.

**The record does not narrate.**
The strongest position against someone who characterizes everything is to characterize
nothing — to produce the record and let it speak. In front of a judge who has seen a
hundred high-conflict custody matters and is tired of both parents, the party who is not
spinning is the one who is believed. That posture is a design constraint, not a style
preference, and it reaches into the schema: ADR-0059 forbids inventing the owner as a
participant in an acquired third-party conversation. Do not put words in anyone's mouth.
The system does not get to narrate its user either.

## The three-part arc
1. **Evidence** — custody (sha256 + manifest) → parse → normalize → store → court-ready export,
   over a polyglot tool mesh (named workflows per evidence type + composable atomic tools).
2. **Analysis** — multi-pass psychological/abuse analysis over a **bitemporal** graph; the
   delta between the contemporaneous read and full-disclosure read is the abuse made legible.
3. **AI Legal Team** — agents (ported from the owner's Gemini Gems personas) that turn the
   processed evidence + knowledge base into strategy, motions, and filings.

## Current runtime and accepted target

| Concern | Current | Accepted target |
|---|---|---|
| Runtime | Agno/AgentOS adapter and existing agent teams | Framework-neutral contracts with adapter-by-adapter cutover |
| Product UI | Custom Next.js/FastAPI Workbench, expanding locally | Workbench is the primary product; no AgentOS clone |
| Knowledge | One canonical ingest plane, including locally built Knowledge browsing | Ingest everything once; apply horizon limits only when agents retrieve/replay |
| Semantics | Semantica wiring is configuration-only | Semantica VIP service; its findings may remain governed candidates |
| Memory | Existing Graphiti reads/writes are incomplete | PostgreSQL belief-event authority with per-run Graphiti projection |
| Models/workspace | Portkey plus existing OpenCode Copilot integration | Request-scoped provider routes plus persistent OpenCode control and isolated jobs |

Current infrastructure includes PostgreSQL 18 (pg_duckdb + pgvector + PostGIS, dual
evidence/analysis schema) · Neo4j + Graphiti (bitemporal temporal graph) · Portkey model
gateway (Ollama Cloud primary, NVIDIA embed/rerank/backup; LiteLLM RETIRED 2026-07-29,
ADR-0042) · Weaviate vectors (locked ADR-0040) · OpenCode · Cloudflare R2 (blob storage)
· isolated agent sandbox · Kasm desktop · n8n (separate server). See the canon for the
verified service map; working-tree features are not implied to be deployed.

## Develop

Python development is `uv`-managed on the workstation; do not use bare
`python`, `pip`, or `pytest`. The authoritative commands are in `AGENTS.md`:

```bash
uv run ruff check server tests
uv run ruff format --check server tests
uv run mypy server
uv run pytest -q
```

Go work under `modules/forks/sbv` (a submodule of `sbv-forensic`) requires the
`fts5` build tag; use its Makefile targets. `deploy/compose.yaml` (moved from
root in the 2026-09-01 restructure) is mirrored to the VPS and is production-facing,
not a disposable local-only stack. Deployment runs through the current Coolify
fleet and requires explicit owner review; do not infer a deploy from a local
build or documentation change.
