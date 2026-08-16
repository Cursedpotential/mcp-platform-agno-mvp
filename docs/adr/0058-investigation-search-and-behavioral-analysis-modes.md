# ADR-0058 — Investigation search and behavioral-analysis modes

> _Byline: Codex · GPT-5 · 2026-08-15_

- **Status:** Accepted (owner approval 2026-08-15)
- **Decision:** D-063
- **Relates:** ADR-0045, ADR-0053, ADR-0056, ADR-0057

## Context

The owner needs to search for known evidence, reconstruct partially known events,
surface missed corroboration and patterns, and analyze curated groups of events or
communications without sending an unbounded corpus to an agent. Behavioral analysis
must support both hindsight and what was knowable so far. Internal analytical language
may use diagnostic-adjacent pattern vocabulary while case-prep exports need
conduct-first, evidence-supported wording.

## Decision

1. The Workbench will expose three investigation intents: **Find Evidence**,
   **Reconstruct Event**, and **Discover Patterns**.
2. Every investigation or behavioral-analysis run uses an immutable scope manifest:
   Matter, people/roles, zero or more non-contiguous date ranges, selected events,
   conversation groups, sources, locations, exclusions, horizon mode, source versions,
   and bounded expansion budgets.
3. Behavioral analysis runs in two distinct stages: closed-set analysis of the frozen
   owner-selected scope, then separately logged outward discovery. Discovered material
   never silently changes the original scope; the owner may accept it into a new revision.
4. Mode is mandatory and immutable per run:
   - **as-lived-so-far:** only material visible through the selected horizon may influence
     analysis or query generation;
   - **hindsight:** all authorized current evidence may be used;
   - **paired comparison:** runs the same policy in both modes and produces the
     behavioral realization delta.
5. Internal analysis may use lenses such as narcissistic-pattern, borderline-pattern,
   DARVO, gaslighting, triangulation, splitting, coercive control, and reactive behavior.
   Lenses generate queries and organize findings; they are not diagnoses.
6. Observed conduct, repetition, evidence quality, functional impact, contradictions,
   alternatives, and limitations remain separate from lens labels. Diagnostic status
   is a separate sourced field.
7. Case-prep export transforms shorthand into conduct-first language unless a diagnosis
   itself is relevant and properly authenticated.
8. Findings remain candidates until governed review promotes facts, events, or work product.

## Alternatives considered

### Analyze the whole corpus in one run

- **Pros:** minimal scope setup.
- **Cons:** unbounded cost, poor reproducibility, context loss, and false patterns.
- **Why rejected:** curated scopes plus bounded expansion are safer and more useful.

### Silently expand the curated group

- **Pros:** simpler result presentation.
- **Cons:** makes the analysis irreproducible and hides what the agent introduced.
- **Why rejected:** baseline and discoveries must remain distinguishable.

### Ban diagnostic-adjacent vocabulary everywhere

- **Pros:** lowest wording risk.
- **Cons:** removes useful research and search shorthand from the private platform.
- **Why rejected:** internal lenses are valuable when separated from diagnosis and export.

## Consequences

### Positive

- Large, discontinuous evidence sets become bounded and reproducible.
- The agent can search for missed recurrence and disconfirming examples.
- Paired runs directly expose what became legible only with hindsight.
- Internal analysis remains expressive while case preparation remains disciplined.

### Negative

- Scope builders, run manifests, expansion review, and export transformations are required.
- Pattern taxonomies need versioning and calibration.

### Risks and mitigations

- **Pathologizing:** distinguish lens, observed behavior, and authenticated diagnosis.
- **Confirmation bias:** require symmetric analysis, contradiction search, alternatives,
  and source independence.
- **Future leakage:** enforce horizon filters before lexical, vector, graph, and geo ranking.
- **False causal claims:** label correlation, sequence, contradiction, and causation separately.
