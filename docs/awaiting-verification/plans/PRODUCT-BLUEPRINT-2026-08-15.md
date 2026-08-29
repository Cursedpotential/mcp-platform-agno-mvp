# Product Blueprint — Temporal Evidence and Agent Experience Platform

> _Byline: Codex · GPT-5 · 2026-08-15 · ADR-0059 amendment Codex · GPT-5 · 2026-08-18_

## Product promise

The platform shows the difference between what a person could know while events unfolded and what becomes clear with hindsight. It safely ingests all available knowledge once, then creates controlled agent experiences that acquire only authorized knowledge at the chosen pace.

## Product planes

### Knowledge plane

- Intake original files and exports.
- Preserve custody and source identity.
- Parse through Go-primary, Python-fallback coverage routing.
- Normalize into one canonical record spine.
- Derive separate first-party and acquired-third-party message projections without duplicating
  authored truth; preserve actual third-party participants with the owner absent.
- Preserve occurrence, source availability, and zero-to-many realization links as distinct axes.
- Run horizon-blind governed extraction.
- Review candidates before promotion.
- Build rebuildable graph and vector projections.

### Experience plane

- Design an ignorant, hindsight, or custom knowledge walk.
- Pin an immutable corpus/policy manifest.
- Advance knowledge by time, step, schedule, or owner-selected activation.
- Rewalk and rebatch without altering prior runs.
- Resume a healthy walk from an exact same-identity checkpoint; seal terminally drifted state and
  start a separately linked rewalk.
- Persist agent observations and belief changes.
- Compare the two experiences and produce the gaslighting/deceit delta.

### Engineering plane

- Run persistent OpenCode workspaces.
- Select models/providers per agent, session, run, or next turn.
- Execute code inside isolated jobs.
- Review diffs, traces, approvals, cost, failures, and work products.

## Primary Workbench surfaces

1. Evidence intake and custody.
2. Import/parser progress and rejection reconciliation.
3. Semantica VIP intelligence, governed findings/candidates, conflicts, provenance, and approvals.
4. Canonical knowledge browser.
5. Horizon-run designer.
6. Ignorant-versus-hindsight comparison.
7. Belief evolution and Graphiti provenance.
8. Agent/team workflow and handoff graph.
9. Model/provider route selector.
10. OpenCode workspace lifecycle and diffs.
11. Approval inbox.
12. Traces, costs, schedules, evals, projection health, backup, and restore.

## Memory taxonomy

| Memory class | Authority | Purpose |
|---|---|---|
| Canonical knowledge | PostgreSQL/R2 | What the source corpus contains |
| Horizon context | Immutable PostgreSQL manifest | What this run may see |
| Belief events | Append-only PostgreSQL ledger | What the agent concluded and why |
| Belief graph | Graphiti/Neo4j | Semantic and temporal recall inside one run |
| Session history | PostgreSQL | Conversation and run continuity |
| Owner preferences | Curated PostgreSQL memory | Stable preferences and instructions |
| Project memory | Docs and governed memory records | Architecture, decisions, status |
| Work products | R2/PostgreSQL manifest | Created reports, exports, code, diagrams |

## Success criteria

- A future first-party fact is absent until occurrence; an acquired-third-party source is absent
  until acquisition; plural realization links never backdate either boundary.
- A healthy checkpoint resumes with identical state/trace/belief/retrieval references, while a
  terminal snapshot yields zero active recall and an exact linked rewalk.
- An old run can be replayed after new evidence arrives.
- The owner can switch an approved model for the next turn without restarting the platform.
- The actual provider/model/fallback/cost is visible after every response.
- Go parses large covered inputs with bounded memory and exact custody equivalence.
- Graphiti demonstrates observed writes, temporal invalidation, per-run isolation, provenance, communities, and recoverability.
- The owner can complete intake → extraction → approval → walk → delta → export through the Workbench.
