// Package activities: this file owns chunk_document_activity only — the
// skip-to-chunk capability Activity (D-116 / owner ruling 2026-08-29:
// "if it doesn't need to be parsed and really needs to be chunked and
// ingested, so be it"). It never parses, normalizes, reconciles, or verifies
// anything beyond the completeness proof engine/chunk.Registry already
// produces in-process.
//
// BUILD LANE C1 wiring status (report this alongside the handoff): this
// Activity is registered on the UIW worker (uiwworker.RegisterAll) and fully
// Temporal-callable today, using the exact same uiw.StageRequest ->
// uiw.StageResult wire contract as every one of UniversalImportWorkflow's 26
// canon stages. It is NOT invoked by UniversalImportWorkflow yet.
// stagegraph.ChunkDocument documents exactly why splicing it into
// stagegraph.Stages today is unsafe (the graph has no vocabulary for an
// alternate, mutually-exclusive path — every Stages member must be a
// transitive ancestor of PublishGeneration, proven by graph_test.go). Wiring
// it in cleanly needs two things neither of which this lane forces:
//  1. A workflow.GetVersion-gated branch in uiw/workflow.go (mirroring the
//     integratedPreviewChangeID pattern) so already-running/preserved
//     Temporal histories from before this change keep replaying
//     deterministically — an ungated new branch point breaks replay for any
//     in-flight or archived history.
//  2. A route decision the workflow can read before scheduling
//     select_parser_activity — e.g. a new WorkflowInput field the starter
//     sets, or a "route" field added to select_parser_activity's own result
//     that the workflow inspects — so "chunk-not-parse" is a real decision
//     made once, not inferred structurally.
package activities

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/chunk"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/stagegraph"
	"github.com/Cursedpotential/mcp-platform-agno-mvp/engine/uiw"
)

// Content-chunk derivation modes, matching working.content_chunk's
// derivation_mode CHECK constraint exactly. Only DerivationModeVerbatimSpan
// is implemented: engine/chunk's registered document-markdown chunker always
// emits Chunk.Text as an exact Source[ByteStart:ByteEnd] slice (proven by
// chunk.Result.Validate), never a composed or unverified derivation. A
// caller requesting either of the other two modes fails closed rather than
// silently being downgraded to verbatim_span.
const (
	DerivationModeVerbatimSpan      = "verbatim_span"
	DerivationModeComposed          = "composed"
	DerivationModeUnverifiedDerived = "unverified_derived"
)

// ChunkDocumentSpec is the compact, already-resolved input to
// chunk_document_activity, built from uiw.StageRequest by
// chunkDocumentSpecFrom. OriginalRef names the retained original object to
// chunk directly (source_view "original" — the skip-to-chunk route this lane
// implements). Signature selects the chunk.Registry variant
// (chronology/research_report/strategy_memo/statute_extract).
type ChunkDocumentSpec struct {
	RequestID        string
	Attempt          int32
	SourceVersionRef uiw.Ref
	OriginalRef      uiw.Ref
	Signature        chunk.Signature
	DerivationMode   string
	PolicyID         string
	PolicyVersion    string
}

func (s ChunkDocumentSpec) validate() error {
	if strings.TrimSpace(s.RequestID) == "" || s.SourceVersionRef == "" || s.OriginalRef == "" {
		return fmt.Errorf("%s requires request, source version, and original references", stagegraph.ChunkDocument)
	}
	if s.Attempt < 1 {
		return fmt.Errorf("%s attempt must be positive", stagegraph.ChunkDocument)
	}
	if err := s.Signature.Validate(); err != nil {
		return fmt.Errorf("%s: %w", stagegraph.ChunkDocument, err)
	}
	if s.DerivationMode != DerivationModeVerbatimSpan {
		return fmt.Errorf("%s: unsupported derivation mode %q, only %q is implemented", stagegraph.ChunkDocument, s.DerivationMode, DerivationModeVerbatimSpan)
	}
	if strings.TrimSpace(s.PolicyID) == "" || strings.TrimSpace(s.PolicyVersion) == "" {
		return fmt.Errorf("%s requires policy id and version", stagegraph.ChunkDocument)
	}
	return nil
}

// ChunkGenerationOutcome is the durable result of one chunk_document_activity
// attempt — literally the {generation ref, chunk_count, reassembly verified}
// tuple this Activity is specified to return. It is the return value of
// ChunkRepository.PersistChunkGeneration (a plain Go call, not a Temporal
// wire type); ChunkActivities.ChunkDocument flattens it into the canon
// uiw.StageResult (Ref + ReceiptRef) that every other Activity in this
// codebase returns, so a future gated workflow branch can invoke it through
// the existing r.exec helper unchanged. ChunkCount and ReassemblyVerified
// remain fully durable and independently queryable via that Ref:
// working.content_chunk_generation.chunk_count and
// working.content_chunk_reassembly_receipt.verification_result.
type ChunkGenerationOutcome struct {
	GenerationRef      uiw.Ref
	ReceiptRef         uiw.Ref
	ChunkCount         int64
	ReassemblyVerified bool
}

// ChunkRepository is the PostgreSQL storage boundary for
// chunk_document_activity. ResolveOriginal reads the exact bytes to chunk;
// PersistChunkGeneration is the only write. Implementations must make
// PersistChunkGeneration retry-safe using context.activity_execution and
// context.activity_receipt, exactly like every other repository in this
// package: a repeated idempotency coordinate returns the existing durable
// outcome rather than writing a second time.
type ChunkRepository interface {
	ResolveOriginal(context.Context, ChunkDocumentSpec) ([]byte, error)
	PersistChunkGeneration(context.Context, ChunkDocumentSpec, chunk.Result) (ChunkGenerationOutcome, error)
}

// ChunkActivities implements chunk_document_activity. Registry is the
// injected chunk-stage coordinator (engine/chunk.Registry) — computation —
// kept explicit and separate from Repository — storage — exactly like
// NormalizedPipelineActivities separates its Normalizer from its Store.
type ChunkActivities struct {
	Registry   *chunk.Registry
	Repository ChunkRepository
	Attempt    Attempt
}

func (a ChunkActivities) validate() error {
	if a.Registry == nil {
		return errors.New("chunk activities: registry is required")
	}
	if a.Repository == nil {
		return errors.New("chunk activities: repository is required")
	}
	return nil
}

func (a ChunkActivities) attempt(ctx context.Context) int32 {
	if a.Attempt == nil {
		return 1
	}
	attempt := a.Attempt(ctx)
	if attempt < 1 {
		return 1
	}
	return attempt
}

// ChunkDocument runs the skip-to-chunk route: it resolves the retained
// original object named by req.Refs["original"], chunks it in-memory via the
// injected chunk.Registry (which independently validates completeness —
// contiguous, gap-free, non-overlapping, source/reassembly hashes equal —
// before ever returning a Result, per engine/chunk.Registry.Execute), then
// persists exactly one chunk generation. It never parses or normalizes.
func (a ChunkActivities) ChunkDocument(ctx context.Context, req uiw.StageRequest) (uiw.StageResult, error) {
	if err := a.validate(); err != nil {
		return uiw.StageResult{}, err
	}
	if err := ctx.Err(); err != nil {
		return uiw.StageResult{}, err
	}
	spec, err := chunkDocumentSpecFrom(req, a.attempt(ctx))
	if err != nil {
		return uiw.StageResult{}, err
	}
	if err := spec.validate(); err != nil {
		return uiw.StageResult{}, err
	}

	source, err := a.Repository.ResolveOriginal(ctx, spec)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("%s: resolve original: %w", stagegraph.ChunkDocument, err)
	}
	if err := ctx.Err(); err != nil {
		return uiw.StageResult{}, err
	}

	result, err := a.Registry.Execute(ctx, source, spec.Signature)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("%s: chunk: %w", stagegraph.ChunkDocument, err)
	}

	outcome, err := a.Repository.PersistChunkGeneration(ctx, spec, result)
	if err != nil {
		return uiw.StageResult{}, fmt.Errorf("%s: persist: %w", stagegraph.ChunkDocument, err)
	}
	if outcome.GenerationRef == "" || outcome.ReceiptRef == "" {
		return uiw.StageResult{}, fmt.Errorf("%s: persisted chunk generation lacks result or activity receipt reference", stagegraph.ChunkDocument)
	}
	if !outcome.ReassemblyVerified {
		return uiw.StageResult{}, fmt.Errorf("%s: chunk generation persisted without a verified reassembly receipt", stagegraph.ChunkDocument)
	}

	return uiw.StageResult{
		Stage: stagegraph.ChunkDocument, Status: uiw.StatusSuccess,
		Ref: outcome.GenerationRef, ReceiptRef: outcome.ReceiptRef,
	}, nil
}

// chunkDocumentSpecFrom reads chunk_document_activity's parameters out of
// uiw.StageRequest.Refs, following the same reference-passing convention as
// every neighboring Activity (requiredRawRef, defined in raw_pipeline.go).
// chunk_signature/chunk_derivation_mode/chunk_policy_id/chunk_policy_version
// are short controlled-vocabulary identifiers, not payloads — the same class
// of value StageRequest.DeclaredFormat already carries directly rather than
// by reference — so packing them into the Refs map (Ref is a bare string
// type) adds no file bodies or record content to Temporal history.
func chunkDocumentSpecFrom(req uiw.StageRequest, attempt int32) (ChunkDocumentSpec, error) {
	if strings.TrimSpace(req.RequestID) == "" || req.SourceVersionRef == "" {
		return ChunkDocumentSpec{}, fmt.Errorf("%s requires request and source version references", stagegraph.ChunkDocument)
	}
	original, err := requiredRawRef(req, stagegraph.ChunkDocument, "original")
	if err != nil {
		return ChunkDocumentSpec{}, err
	}
	signatureRef, err := requiredRawRef(req, stagegraph.ChunkDocument, "chunk_signature")
	if err != nil {
		return ChunkDocumentSpec{}, err
	}
	derivationRef, err := requiredRawRef(req, stagegraph.ChunkDocument, "chunk_derivation_mode")
	if err != nil {
		return ChunkDocumentSpec{}, err
	}
	policyIDRef, err := requiredRawRef(req, stagegraph.ChunkDocument, "chunk_policy_id")
	if err != nil {
		return ChunkDocumentSpec{}, err
	}
	policyVersionRef, err := requiredRawRef(req, stagegraph.ChunkDocument, "chunk_policy_version")
	if err != nil {
		return ChunkDocumentSpec{}, err
	}
	return ChunkDocumentSpec{
		RequestID: req.RequestID, Attempt: attempt, SourceVersionRef: req.SourceVersionRef,
		OriginalRef: original, Signature: chunk.Signature(signatureRef), DerivationMode: string(derivationRef),
		PolicyID: string(policyIDRef), PolicyVersion: string(policyVersionRef),
	}, nil
}
