<!-- Byline: Codex · GPT-5 · 2026-08-16 -->

# Horizon Swift MVP synthetic knowledge fixture

This disposable document verifies that the framework-neutral ingest port writes
canonical PostgreSQL rows with a source hash, parser identifier, chunker
identifier, matter scope, and provenance.

## Chonkie runtime proof

This revision is intentionally longer than one small chunk. The operator must
be able to ingest an original file once, preserve its immutable custody hash,
and inspect derived retrieval-sized rows without confusing those rows with a
second authored truth. Each derived row therefore carries the source-record
index, the source-record content hash, the chunk index, the executed chunker
version, and the exact character and token boundaries reported by Chonkie.

Horizon reconstructs knowledge as it became available. Extraction is allowed
to read the full source because extraction forms no belief, but retrieval for
an agent is constrained before ranking by Matter, disclosure eligibility, and
the agent's immutable HorizonContext. A future fact may never enter an
as-lived prompt merely because its embedding is similar. PostgreSQL remains
the canonical custody and approval authority while vector, graph, and future
analytical stores remain governed projections.

The synthetic source also exercises the product boundary. Workbench should
show the parser, the versioned chunker, the custody hash, and every resulting
chunk with provenance. It should not require AgentOS Studio, a command-line
operator, or a framework-owned object. The same neutral receipt must serve the
HTTP upload route and the in-process folder walker.

The Go parser route is selected by format coverage rather than file size. An
SBV-covered export must stay on the Go path unless an explicitly authorized
fallback is enabled and recorded. General knowledge formats that are not
covered by SBV use the registered Python extraction path, then converge on the
same normalization, Chonkie, PostgreSQL, and receipt contracts.

Every test artifact in this fixture is disposable and matter-scoped. It may be
re-created from the checked-in original, but it must not be mistaken for live
case evidence. Production databases, the parked legacy Surreal deployment,
Graphiti, and live corpus material remain outside this proof.

The receipt is the durable report for this operation. It distinguishes the
number of logical parser records from the number of retrieval chunks actually
stored, names the parser engine, records all routing attempts and rejections,
and keeps optional projection failure from undoing a successful canonical
PostgreSQL commit. That distinction makes the test useful even when a source
record expands into several deterministic chunks.

The recursive baseline measures its limit in characters, matching Chonkie's
explicit character tokenizer. The versioned receipt records that unit so an
operator never mistakes a character boundary for a model-token boundary.
